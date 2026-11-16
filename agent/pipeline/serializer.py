"""WebSocket wire format for the hosted/tunnel transport (simple, no protobuf):
- binary frames = raw PCM16 mono little-endian (client->server at 16 kHz, server->client at the
  pipeline output rate announced in the 'audio_format' JSON message),
- text frames = JSON app messages (same messages the WebRTC data channel carries).
"""
from __future__ import annotations

import json

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InputTransportMessageFrame,
    OutputAudioRawFrame,
    OutputTransportMessageFrame,
    OutputTransportMessageUrgentFrame,
)
from pipecat.serializers.base_serializer import FrameSerializer

IN_RATE = 16000


class RawPCMSerializer(FrameSerializer):
    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            return bytes(frame.audio)
        if isinstance(frame, (OutputTransportMessageFrame, OutputTransportMessageUrgentFrame)):
            return json.dumps(frame.message, ensure_ascii=False)
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, (bytes, bytearray)):
            if len(data) < 2:
                return None
            n = len(data) - (len(data) % 2)
            return InputAudioRawFrame(audio=bytes(data[:n]), sample_rate=IN_RATE, num_channels=1)
        try:
            msg = json.loads(data)
        except (ValueError, TypeError):
            return None
        return InputTransportMessageFrame(message=msg) if isinstance(msg, dict) else None
