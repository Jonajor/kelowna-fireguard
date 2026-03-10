"""WebSocket Manager — Real-time push to connected clients."""

import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"[WS] Connected. Total: {len(self.active)}")
        await ws.send_json({"type": "connected", "clients": len(self.active)})

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"[WS] Disconnected. Total: {len(self.active)}")

    async def broadcast(self, event_type: str, data: dict):
        message = {"type": event_type, "data": data}
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

    @property
    def client_count(self):
        return len(self.active)


manager = ConnectionManager()
