from __future__ import annotations

import json
from typing import Any

from redis import Redis

from creator_agent.config import Settings


QUEUE_KEY = "yca:tasks:queue"
EVENTS_KEY = "yca:task_events"
MONITOR_LAST_RUN_KEY = "yca:monitor:last_run"


class RedisTaskQueue:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def status(self) -> dict[str, Any]:
        if not self.settings.redis_url:
            return {
                "configured": False,
                "status": "skipped",
                "message": "Redis URL is not configured.",
                "queued_count": 0,
            }
        try:
            client = self._client()
            client.ping()
            return {
                "configured": True,
                "status": "ok",
                "message": "Redis queue is reachable.",
                "queued_count": client.llen(QUEUE_KEY),
            }
        except Exception as exc:
            return {
                "configured": True,
                "status": "failed",
                "message": f"Redis queue is not reachable: {exc}",
                "queued_count": 0,
            }

    def enqueue(self, task_id: str) -> bool:
        if not task_id or not self.settings.redis_url:
            return False
        try:
            client = self._client()
            client.rpush(QUEUE_KEY, task_id)
            return True
        except Exception:
            return False

    def dequeue(self, timeout_seconds: int = 0) -> str | None:
        if not self.settings.redis_url:
            return None
        try:
            client = self._client()
            if timeout_seconds > 0:
                item = client.blpop(QUEUE_KEY, timeout=timeout_seconds)
                if not item:
                    return None
                return self._decode(item[1])
            item = client.lpop(QUEUE_KEY)
            return self._decode(item)
        except Exception:
            return None

    def remove(self, task_id: str) -> None:
        if not task_id or not self.settings.redis_url:
            return
        try:
            self._client().lrem(QUEUE_KEY, 0, task_id)
        except Exception:
            return

    def push_event(self, payload: dict[str, Any]) -> None:
        if not self.settings.redis_url:
            return
        try:
            self._client().lpush(EVENTS_KEY, json.dumps(payload, ensure_ascii=False))
        except Exception:
            return

    def get_monitor_last_run(self) -> str:
        if not self.settings.redis_url:
            return ""
        try:
            return self._decode(self._client().get(MONITOR_LAST_RUN_KEY)) or ""
        except Exception:
            return ""

    def set_monitor_last_run(self, value: str) -> None:
        if not value or not self.settings.redis_url:
            return
        try:
            self._client().set(MONITOR_LAST_RUN_KEY, value)
        except Exception:
            return

    def _client(self) -> Redis:
        return Redis.from_url(self.settings.redis_url, socket_connect_timeout=1, socket_timeout=5, decode_responses=True)

    def _decode(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)
