"""
In-process WebSocket hub for pushing events to connected users.

Events are JSON objects with a ``type`` field:
  {"type": "message", "message": {...}}
  {"type": "points", "amount": 2, "reason": "chat", "balance": 120}
  {"type": "friend_added", "user": {...}}

Single-process only; with several workers, swap for Redis pub/sub or similar.
"""

import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections[user_id].discard(websocket)
        if not self._connections[user_id]:
            del self._connections[user_id]

    def is_online(self, user_id: int) -> bool:
        return user_id in self._connections

    async def send(self, user_id: int, event: dict[str, Any]) -> None:
        payload = jsonable_encoder(event)
        for websocket in list(self._connections.get(user_id, ())):
            try:
                await websocket.send_json(payload)
            except Exception:
                logger.debug("Dropping dead websocket for user %s", user_id)
                self.disconnect(user_id, websocket)


hub = ConnectionManager()
