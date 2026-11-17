"""Pipecat processors: router STT, brain, router TTS."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

import numpy as np
from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ErrorFrame,
    Frame,
    InputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
    StartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.settings import STTSettings, TTSSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.services.tts_service import TTSService
from pipecat.utils.time import time_now_iso8601

from agent.lang import dominant_language
from agent.pipeline.session import CallSession

CHUNK_SECONDS = 0.2


def msg(event: str, **data) -> OutputTransportMessageUrgentFrame:
    return OutputTransportMessageUrgentFrame(message={"type": "shaon", "event": event, **data})


class RouterSTT(SegmentedSTTService):
    """Utterance-level STT: language ID + routing per language (PLAN.md section 6)."""

    def __init__(self, session: CallSession, **kw):
        super().__init__(sample_rate=16000, trailing_silence_secs=0.3,
                         settings=STTSettings(model=None, language=None), **kw)  # model/language are routed per turn
        self.session = session
        self.last_info: dict | None = None
        self._stop_times: list[float] = []

    @property
    def wants_wav_segments(self) -> bool:
        return False

    @property
    def segment_sample_rate(self) -> int:
        return 16000

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            self._stop_times.append(time.perf_counter())  # one per queued segment, consumed FIFO in run_stt
        await super().process_frame(frame, direction)

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        t_stop = self._stop_times.pop(0) if self._stop_times else time.perf_counter()
        pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        if len(pcm) < 16000 * 0.25:  # under 250 ms: VAD blip, ignore
            return
        try:
            info = await asyncio.to_thread(self.session.transcribe_turn, pcm)
        except Exception as e:
            logger.exception("STT failed")
            await self.push_frame(msg("error", stage="stt", detail=f"{type(e).__name__}: {e}"[:200]))
            yield ErrorFrame(f"STT failed: {e}")
            return
        if not info["text"]:
            await self.push_frame(msg("stt_empty", stt_ms=info["stt_ms"]))
            return
        info["audio_s"] = round(len(pcm) / 16000, 2)
        info["t_stop"] = t_stop
        self.last_info = info
        f = TranscriptionFrame(info["text"], "caller", time_now_iso8601(), info["lang"])
        f.result = info
        yield f


class RouterTTS(TTSService):
    """Speaks each sentence with the voice for the language of its SCRIPT (never the model's claim)."""

    def __init__(self, session: CallSession, out_rate: int = 24000, **kw):
        super().__init__(push_start_frame=True, push_stop_frames=True, sample_rate=out_rate,
                         settings=TTSSettings(model=None, voice="router", language=None), **kw)
        self.session = session

    def can_generate_metrics(self) -> bool:
        return False

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        s = self.session
        lang = dominant_language(text)[0] or s.ctx.current_lang
        voice = s.voice_for(lang)
        t0 = time.perf_counter()
        synth = None
        tried = []
        for v in [voice, *s.fallback_voices(lang)]:
            if v is None:
                continue
            try:
                if v.params.get("ref_from") and s.ensure_reference:
                    await asyncio.to_thread(s.ensure_reference, v)  # OmniVoice: model-generated reference clip
                eng = await asyncio.to_thread(s.engines.get_tts, v.engine)
                synth = await asyncio.to_thread(eng.synthesize, text, v)
                voice = v
                break
            except Exception as e:  # engine missing / weights missing: try the next fallback voice
                tried.append(f"{v.id}: {type(e).__name__}")
                logger.warning(f"TTS {v.engine} unavailable for {lang}: {e}")
        if synth is None:
            await self.push_frame(msg("tts_unavailable", lang=lang, text=text,
                                      detail="No working TTS voice for this language on this machine (see Settings > Engines)."))
            return
        ms = round((time.perf_counter() - t0) * 1000)
        if s.tts_first_ms is None:
            s.tts_first_ms = ms
        await self.push_frame(msg("tts", lang=lang, voice=voice.id, engine=voice.engine, demo_only=voice.demo_only, fallbacks=tried,
                                  gen_ms=ms, audio_s=round(len(synth.audio) / synth.sample_rate, 2)))
        pcm = (np.clip(synth.audio, -1, 1) * 32767).astype(np.int16).tobytes()
        step = int(synth.sample_rate * CHUNK_SECONDS) * 2
        for i in range(0, len(pcm), step):
            yield TTSAudioRawFrame(audio=pcm[i:i + step], sample_rate=synth.sample_rate, num_channels=1,
                                   context_id=context_id)


class BrainProcessor(FrameProcessor):
    """Runs a TurnEngine turn per final transcription; sends transcript/state/latency to the client."""

    def __init__(self, session: CallSession, **kw):
        super().__init__(**kw)
        self.session = session
        self._turn_task: asyncio.Task | None = None
        self._bot_speaking = False
        self._greeted = False
        self._first_audio_ms: int | None = None
        self._turn_id: int | None = None

    async def _flush_latency(self):
        """Send/store first-audio latency once both the measurement and the turn row exist."""
        s = self.session
        if self._first_audio_ms is None or self._turn_id is None:
            return
        s.hooks.on_turn_update(self._turn_id, {"first_audio_ms": self._first_audio_ms, "tts_ms": s.tts_first_ms})
        await self._send(msg("latency", turn_id=self._turn_id, first_audio_ms=self._first_audio_ms, tts_ms=s.tts_first_ms))
        self._turn_id = None

    async def _send(self, frame):
        await self.push_frame(frame, FrameDirection.DOWNSTREAM)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        s = self.session
        if isinstance(frame, TranscriptionFrame) and direction == FrameDirection.DOWNSTREAM:
            info = getattr(frame, "result", None) or {"text": frame.text, "lang": frame.language}
            if self._turn_task and not self._turn_task.done():
                self._turn_task.cancel()
            self._turn_task = self.create_task(self._run_turn(info))
            return  # do not forward caller text to TTS
        if isinstance(frame, InputTransportMessageFrame):
            await self._on_client_message(frame.message)
        if isinstance(frame, VADUserStartedSpeakingFrame):
            await self._send(msg("state", state="listening"))
            if self._bot_speaking or (self._turn_task and not self._turn_task.done()):
                if self._turn_task and not self._turn_task.done():
                    self._turn_task.cancel()
                await self.broadcast_interruption()  # barge-in
                await self._send(msg("interrupted"))
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            await self._send(msg("state", state="thinking"))
        elif isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
            await self._send(msg("state", state="speaking"))
            if s.t_user_stopped is not None and self._first_audio_ms is None:
                self._first_audio_ms = round((time.perf_counter() - s.t_user_stopped) * 1000)
                s.t_user_stopped = None
                await self._flush_latency()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            await self._send(msg("state", state="idle"))
        await self.push_frame(frame, direction)

    async def _on_client_message(self, m: dict):
        s = self.session
        kind = m.get("type")
        if kind == "ready" and not self._greeted:
            self._greeted = True
            lang = s.ctx.current_lang
            greet = s.ctx.profile["persona"]["greeting"].get(lang) or s.ctx.profile["persona"]["greeting"]["en"]
            await self._send(msg("hello", call_id=s.ctx.call_id, lang=lang, transport=s.transport,
                                 languages=s.enabled, voices=s.ctx.voice_by_lang, provider=s.hooks.provider().name))
            await self._send(msg("transcript", role="agent", text=greet, lang=lang, greeting=True))
            s.hooks.on_turn(s.ctx.call_id, {"role": "agent", "language": lang, "text": greet, "lang_reason": "greeting"})
            s.tts_first_ms = None
            await self._send(TTSSpeakFrame(greet))
        elif kind == "override_lang":
            lang = m.get("lang")
            s.ctx.override_lang = lang if lang in s.enabled else None
            await self._send(msg("override", lang=s.ctx.override_lang))
        elif kind == "set_voice":
            lang, vid = m.get("lang"), m.get("voice")
            if lang and vid and s.voices.voice(vid):
                s.ctx.voice_by_lang[lang] = vid  # applies from the next sentence
                await self._send(msg("voice", lang=lang, voice=vid))

    async def _run_turn(self, info: dict):
        s = self.session
        lang = info["lang"]
        s.tts_first_ms = None
        self._first_audio_ms, self._turn_id = None, None
        s.t_user_stopped = info.get("t_stop")  # end of THIS turn's speech (not a later utterance)
        row = {"role": "user", "language": lang, "text": info["text"], "stt_ms": info.get("stt_ms"),
               "lang_reason": info.get("reason"), "engine_json": {"stt": info.get("engines"), "lid": info.get("lid_probs"),
                                                                  "lid_ms": info.get("lid_ms"), "audio_s": info.get("audio_s"),
                                                                  "routing": info.get("routing"), "fallbacks": info.get("fallbacks")}}
        s.hooks.on_turn(s.ctx.call_id, row)
        await self._send(msg("transcript", role="user", text=info["text"], lang=lang, reason=info.get("reason"), fallbacks=info.get("fallbacks"), routing=info.get("routing"),
                             stt_ms=info.get("stt_ms"), lid=info.get("lid_probs"), engines=info.get("engines")))

        async def emit(kind: str, data: dict):
            if kind == "sentence":
                await self._send(msg("transcript", role="agent", text=data["text"], lang=data["lang"],
                                     handoff=data.get("handoff", False)))
                await self._send(TTSSpeakFrame(data["text"]))
            else:
                await self._send(msg(kind, **data))

        try:
            meta = await s.engine().respond(info["text"], lang, emit)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            from agent.logscrub import scrub
            logger.exception("turn failed")
            detail = scrub(f"{type(e).__name__}: {e}")[:240]
            await self._send(msg("error", stage="llm", detail=detail))
            meta = {"reply": s.ctx.profile["guardrails"]["handoff_message"].get(lang, ""), "handoff": True,
                    "error": detail, "guard": [], "sources": []}
            await emit("sentence", {"text": meta["reply"], "lang": lang, "handoff": True})
        turn_id = s.hooks.on_turn(s.ctx.call_id, {
            "role": "agent", "language": meta.get("reply_lang", lang), "text": meta.get("reply", ""),
            "llm_ms": meta.get("llm_ms"), "llm_ttft_ms": meta.get("llm_ttft_ms"), "guard_ms": meta.get("guard_ms"),
            "sources_json": meta.get("sources"), "guardrail_json": meta.get("guard"),
            "engine_json": {"provider": meta.get("provider"), "model": meta.get("model"), "model_served": meta.get("model_served"),
                            "model_fallback": meta.get("model_fallback"), "tools": meta.get("tools"),
                            "retrieval_ms": meta.get("retrieval_ms")}})
        self._turn_id = turn_id
        await self._flush_latency()
        await self._send(msg("turn_meta", turn_id=turn_id, stt_ms=info.get("stt_ms"), llm_ttft_ms=meta.get("llm_ttft_ms"),
                             llm_ms=meta.get("llm_ms"), guard_ms=meta.get("guard_ms"), lid_ms=info.get("lid_ms"),
                             handoff=meta.get("handoff", False), provider=meta.get("provider"), model=meta.get("model"),
                             model_served=meta.get("model_served"), model_fallback=meta.get("model_fallback")))
