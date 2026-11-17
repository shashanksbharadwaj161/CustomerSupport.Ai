"""Call transports: SmallWebRTC (local) and FastAPI WebSocket (tunnel), chosen by TRANSPORT config."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, WebSocket
from loguru import logger

from agent.brain import CallContext
from agent.pipeline.session import CallSession, Hooks
from api.state import AppState


def make_session(state: AppState, profile_id: str | None, transport: str, app) -> CallSession:
    prof, version_id = app.state.profiles.resolve(profile_id)
    call_id = state.new_call(prof.get("_id"), version_id, transport)
    ctx = CallContext(call_id=call_id, profile=prof["config"])
    kb = app.state.knowledge.context_for(prof["config"]) if getattr(app.state, "knowledge", None) else {}
    ctx.brief, ctx.kb_text = kb.get("brief"), kb.get("kb_text")
    voices = state.voices()
    persona = prof["config"]["voices"].get("persona_set", "warm_female")
    for lang in prof["config"]["languages"]["enabled"]:
        vid = prof["config"]["voices"].get("by_language", {}).get(lang) or voices.for_persona(persona, lang)
        if vid:
            ctx.voice_by_lang[lang] = vid
    hooks = Hooks(provider=state.provider, model=state.cfg.llm_model,
                  guard=getattr(app.state, "guard", None), retriever=getattr(app.state, "retriever", None),
                  on_turn=state.log_turn, on_turn_update=state.update_turn, on_guard=state.log_guard,
                  on_call_end=state.end_call)
    sess = CallSession(ctx=ctx, engines=state.engines, voices=voices, hooks=hooks, transport=transport)
    from api.voices import ensure_reference
    sess.ensure_reference = lambda v: ensure_reference(state, v)
    state.active_calls[call_id] = {"transport": transport, "profile_id": prof.get("_id")}
    return sess


def router(app) -> APIRouter:
    r = APIRouter()
    from pipecat.transports.base_transport import TransportParams
    from pipecat.transports.smallwebrtc.request_handler import (
        IceCandidate, SmallWebRTCPatchRequest, SmallWebRTCRequest, SmallWebRTCRequestHandler)
    from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport

    handler = SmallWebRTCRequestHandler()
    tasks: set[asyncio.Task] = set()

    def allowed(kind: str) -> None:
        t = app.state.app.cfg.transport
        if t not in ("both", kind):
            raise HTTPException(409, f"Transport '{kind}' is disabled (TRANSPORT={t}).")

    def busy() -> bool:
        st = app.state.app
        return len(st.active_calls) >= st.cfg.max_calls

    @r.post("/api/calls/offer")
    async def offer(request: Request):
        allowed("smallwebrtc")
        app.state.auth.check_request(request)
        app.state.auth.rate_limit(request, "call_start")
        body = await request.json()
        if not body.get("pc_id") and busy():
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "busy", "busy": True, "max_calls": app.state.app.cfg.max_calls}, status_code=503)
        req_data = body.get("requestData") or body.get("request_data") or {}
        req = SmallWebRTCRequest(sdp=body["sdp"], type=body["type"], pc_id=body.get("pc_id"),
                                 restart_pc=body.get("restart_pc"), request_data=req_data)

        async def on_conn(conn):
            from agent.pipeline.run import run_call
            transport = SmallWebRTCTransport(webrtc_connection=conn, params=TransportParams(
                audio_in_enabled=True, audio_out_enabled=True, audio_out_sample_rate=24000))
            sess = make_session(app.state.app, req_data.get("profile_id"), "smallwebrtc", app)
            t = asyncio.create_task(run_call(transport, sess, max_call_seconds=app.state.app.cfg.max_call_seconds))
            tasks.add(t)
            t.add_done_callback(tasks.discard)

        return await handler.handle_web_request(req, on_conn)

    @r.patch("/api/calls/offer")
    async def ice(request: Request):
        app.state.auth.check_request(request)
        body = await request.json()
        cands = [IceCandidate(candidate=c.get("candidate"), sdp_mid=c.get("sdp_mid") or c.get("sdpMid"),
                              sdp_mline_index=c.get("sdp_mline_index", c.get("sdpMLineIndex")))
                 for c in body.get("candidates", [])]
        await handler.handle_patch_request(SmallWebRTCPatchRequest(pc_id=body["pc_id"], candidates=cands))
        return {"ok": True}

    def ws_refusal(websocket: WebSocket) -> int | None:
        """CORS does not cover WebSockets: check Host, Origin, role token and rate limit ourselves (DEPLOY.md)."""
        from api.auth import client_ip
        a = app.state.auth
        if not a.host_ok(websocket.headers.get("host")):
            return 4421
        if not a.origin_ok(websocket.headers.get("origin"), websocket.headers.get("host")):
            return 4403
        if not a.token_ok(a.token_from(websocket), "visitor"):
            return 4401
        if not a.rate_limit_key(client_ip(websocket), "call_start"):
            return 4429
        return None

    @r.websocket("/api/ws-check")
    async def ws_check(websocket: WebSocket):
        """Get-ready screen: proves a WebSocket survives the tunnel and the passcode works. Echoes one message."""
        reason = ws_refusal(websocket)
        if reason:
            await websocket.close(code=reason)
            return
        await websocket.accept()
        try:
            msg = await asyncio.wait_for(websocket.receive_text(), timeout=10)
            await websocket.send_text(msg)
        except Exception:
            pass
        await websocket.close()

    @r.websocket("/api/calls/ws")
    async def ws(websocket: WebSocket):
        from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
        from agent.pipeline.run import run_call
        from agent.pipeline.serializer import RawPCMSerializer
        st: AppState = app.state.app
        if st.cfg.transport not in ("both", "websocket"):
            await websocket.close(code=4409)
            return
        reason = ws_refusal(websocket)
        if reason:
            await websocket.close(code=reason)
            return
        if busy():
            await websocket.accept()
            await websocket.send_text('{"type": "shaon", "event": "busy"}')
            await websocket.close(code=4503)
            return
        await websocket.accept()
        transport = FastAPIWebsocketTransport(websocket, FastAPIWebsocketParams(
            audio_in_enabled=True, audio_out_enabled=True, add_wav_header=False, serializer=RawPCMSerializer(),
            audio_in_sample_rate=16000, audio_out_sample_rate=24000, session_timeout=60 * 30, allowed_origins=[]))
        sess = make_session(st, websocket.query_params.get("profile_id"), "websocket", app)
        try:
            await run_call(transport, sess, max_call_seconds=st.cfg.max_call_seconds)
        except Exception:
            logger.exception("websocket call failed")

    return r
