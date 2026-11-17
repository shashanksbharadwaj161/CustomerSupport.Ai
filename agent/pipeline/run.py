"""Build and run the voice pipeline for one call on a given Pipecat transport."""
from __future__ import annotations

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.audio.vad_processor import VADProcessor

from agent.pipeline.services import BrainProcessor, RouterSTT, RouterTTS
from agent.pipeline.session import CallSession

OUT_RATE = 24000


def build_task(transport, session: CallSession, idle_timeout_secs: float = 300) -> PipelineTask:
    vad = VADProcessor(vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.6)))
    pipeline = Pipeline([
        transport.input(), vad, RouterSTT(session), BrainProcessor(session), RouterTTS(session, out_rate=OUT_RATE),
        transport.output(),
    ])
    return PipelineTask(pipeline, params=PipelineParams(audio_in_sample_rate=16000, audio_out_sample_rate=OUT_RATE),
                        enable_rtvi=False, idle_timeout_secs=idle_timeout_secs)


async def call_timer(task, seconds: float, notify) -> None:
    """Hard limit per call: tell the client why, give it a moment to receive the message, then end the call."""
    import asyncio

    await asyncio.sleep(seconds)
    try:
        await notify()
        await asyncio.sleep(1.0)
    finally:
        await task.cancel()


async def run_call(transport, session: CallSession, idle_timeout_secs: float = 300, max_call_seconds: float | None = None) -> None:
    import asyncio

    from pipecat.frames.frames import OutputTransportMessageUrgentFrame

    task = build_task(transport, session, idle_timeout_secs)

    @transport.event_handler("on_client_disconnected")
    async def _gone(*_):
        await task.cancel()

    timer = None
    if max_call_seconds:
        async def notify():
            await task.queue_frames([OutputTransportMessageUrgentFrame(message={
                "type": "shaon", "event": "ended", "reason": "max_length", "seconds": max_call_seconds})])
        timer = asyncio.create_task(call_timer(task, max_call_seconds, notify))
    try:
        await PipelineRunner(handle_sigint=False).run(task)
    finally:
        if timer:
            timer.cancel()
        session.hooks.on_call_end(session.ctx.call_id, {"languages_used": sorted(session.languages_used),
                                                         "end_reason": "max_length" if timer and timer.done() and not timer.cancelled() else None})
