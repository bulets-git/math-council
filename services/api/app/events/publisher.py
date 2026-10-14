import json
import logging
from datetime import datetime, timezone
from typing import Any
import uuid
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger("events.publisher")


class EventPublisher:
    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._mock_events: list[dict[str, Any]] = []

    async def get_redis(self) -> aioredis.Redis | None:
        if self._redis is None and settings.REDIS_URL:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
                await self._redis.ping()
            except Exception:
                logger.warning("Redis is unreachable. EventPublisher falling back to in-memory event stream.")
                self._redis = None
        return self._redis

    async def publish(self, run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Publishes an event to Redis channel 'run:{run_id}:events'."""
        payload = {
            "event_type": event_type,
            "run_id": str(run_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        channel = f"run:{run_id}:events"
        self._mock_events.append(payload)

        try:
            r = await self.get_redis()
            if r:
                await r.publish(channel, json.dumps(payload, ensure_ascii=False))
        except Exception as err:
            logger.warning("Failed to publish event to Redis: %s", err)

        return payload

    def get_published_events(self, run_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
        if run_id:
            return [e for e in self._mock_events if e["run_id"] == str(run_id)]
        return list(self._mock_events)

    def clear_events(self):
        self._mock_events.clear()


event_publisher = EventPublisher()
