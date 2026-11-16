"""Voices: registry listing, preview synthesis, adding persona reference clips (consent required), personas."""
from __future__ import annotations

import asyncio
import io
import json
import re
import uuid

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from agent.engines import ENGINE_INFO, installed
from api.db import dumps, now

SAMPLE = {
    "en": "Hello, I am your AI assistant. Our branch opens at ten in the morning on Saturday.",
    "ja": "こんにちは、AIアシスタントです。土曜日の支店は午前十時に開きます。",
    "hi": "नमस्ते, मैं आपकी एआई सहायक हूँ। शनिवार को हमारी शाखा सुबह दस बजे खुलती है।",
    "bn": "নমস্কার, আমি আপনার এআই সহকারী। শনিবার আমাদের শাখা সকাল দশটায় খোলে।",
    "kn": "ನಮಸ್ಕಾರ, ನಾನು ನಿಮ್ಮ ಎಐ ಸಹಾಯಕ. ಶನಿವಾರ ನಮ್ಮ ಶಾಖೆ ಬೆಳಿಗ್ಗೆ ಹತ್ತು ಗಂಟೆಗೆ ತೆರೆಯುತ್ತದೆ.",
}


def wav_bytes(audio: np.ndarray, sr: int) -> bytes:
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.asarray(audio, dtype=np.float32), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def voice_status(v: dict) -> str:
    eng = v["engine"]
    if not installed(eng):
        return "pending"
    return "ready" if ENGINE_INFO[eng].get("verified_here") else "pending"


def ensure_reference(st, voice) -> None:
    """OmniVoice clone voices with `ref_from`: generate the reference clip with that (model) voice, once."""
    rid = voice.params.get("ref_from")
    if not rid or voice.params.get("ref_audio"):
        return
    path = st.cfg.data_dir / "voices" / "refs" / f"{rid}.wav"
    cat = st.voices()
    rv = cat.voice(rid)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        s = st.engines.get_tts(rv.engine).synthesize(cat.ref_text[rv.language], rv)
        path.write_bytes(wav_bytes(s.audio, s.sample_rate))
    voice.params["ref_audio"] = str(path)
    voice.params["ref_text"] = cat.ref_text[rv.language]


def register(app: FastAPI) -> None:
    st = app.state.app

    @app.get("/api/voices/personas")
    def personas():
        return st.voices().persona_sets

    @app.post("/api/voices/preview")
    async def preview(request: Request):
        app.state.auth.rate_limit(request, "voice_preview")
        body = await request.json()
        cat = st.voices()
        v = cat.voice(str(body.get("voice_id", "")))
        if not v:
            raise HTTPException(404, "unknown voice")
        text = (body.get("text") or SAMPLE.get(v.language, SAMPLE["en"]))[:300]
        if not installed(v.engine):
            raise HTTPException(503, f"PENDING: engine '{v.engine}' is not installed on this machine "
                                     f"({ENGINE_INFO[v.engine].get('pending') or 'install it, see docs/RUNBOOK.md'}).")
        try:
            def work():
                ensure_reference(st, v)
                return st.engines.get_tts(v.engine).synthesize(text, v)
            s = await asyncio.wait_for(asyncio.to_thread(work), timeout=180)
        except asyncio.TimeoutError:
            raise HTTPException(504, "synthesis timed out")
        except Exception as e:
            from agent.logscrub import scrub
            raise HTTPException(503, f"PENDING: {v.engine} could not synthesize here: {scrub(str(e))[:200]}")
        headers = {"X-Voice-Engine": v.engine, "X-Demo-Only": "1" if v.demo_only else "0",
                   "X-Audio-Seconds": f"{len(s.audio) / s.sample_rate:.2f}"}
        return Response(wav_bytes(s.audio, s.sample_rate), media_type="audio/wav", headers=headers)

    @app.post("/api/voices")
    async def add_voice(request: Request):
        """Add a persona reference clip for OmniVoice cloning (DEMO ONLY). Consent is mandatory."""
        form = await request.form()
        if str(form.get("consent", "")).lower() not in ("true", "1", "yes", "on"):
            raise HTTPException(400, "Only consenting speakers or model-generated clips: confirm consent.")
        lang = str(form.get("language", ""))
        if lang not in ("en", "ja", "hi", "bn", "kn"):
            raise HTTPException(400, "language must be one of en, ja, hi, bn, kn")
        transcript = str(form.get("transcript", "")).strip()
        if len(transcript) < 5:
            raise HTTPException(400, "The transcript of the clip is required (stored with it).")
        f = form.get("clip")
        if f is None or not hasattr(f, "read"):
            raise HTTPException(400, "clip file required (wav/webm/ogg, 3-10 s)")
        data = await f.read()
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(400, "clip too large (5 MB max)")
        name = re.sub(r"[^\w\- ]", "", str(form.get("display_name", "") or "Persona"))[:40] or "Persona"
        vid = "user_" + uuid.uuid4().hex[:8]
        d = st.cfg.data_dir / "voices"
        d.mkdir(parents=True, exist_ok=True)
        raw = d / f"{vid}.upload"
        raw.write_bytes(data)
        wav = d / f"{vid}.wav"
        try:
            from agent.audio import load_audio, write_wav
            audio = load_audio(str(raw), 24000)
            dur = len(audio) / 24000
            if not 2.0 <= dur <= 15.0:
                raise HTTPException(400, f"clip must be 3-10 seconds (got {dur:.1f} s)")
            write_wav(str(wav), audio, 24000)
        finally:
            raw.unlink(missing_ok=True)
        source = str(form.get("source", "consenting_speaker"))
        st.db.execute("INSERT INTO voices(id,language,engine,display_name,persona_tag,reference_path,reference_text,params_json,license,demo_only,source,created_at) "
                      "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (vid, lang, "omnivoice", f"{name} ({lang}, clone)", str(form.get("persona_tag", "") or "custom"), str(wav), transcript,
                       dumps({}), "CC-BY-NC weights: DEMO ONLY", 1, source, now()))
        return {"id": vid, "demo_only": True, "duration_s": round(dur, 2)}

    @app.delete("/api/voices/{vid}")
    def delete_voice(vid: str):
        r = st.db.one("SELECT reference_path FROM voices WHERE id=?", (vid,))
        if not r:
            raise HTTPException(404, "only user-added voices can be deleted")
        if r["reference_path"]:
            import pathlib
            pathlib.Path(r["reference_path"]).unlink(missing_ok=True)
        st.db.execute("DELETE FROM voices WHERE id=?", (vid,))
        return {"ok": True}
