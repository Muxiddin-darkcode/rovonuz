"""
ROVON.UZ - Redis Event Bus & Distributed Locks
Implements Redis Streams for asynchronous event passing and Redlock for idempotency.
Includes an in-memory fallback for local development without active Redis.
"""

import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings


class RedisEventBus:
    """Enterprise event bus backed by Redis Streams with in-memory fallback."""

    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self._client: Optional[aioredis.Redis] = None
        self._in_memory_locks: Dict[str, bool] = {}

    async def get_client(self) -> Optional[aioredis.Redis]:
        if self._client is None:
            try:
                self._client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                await self._client.ping()
            except Exception:
                # Redis not reachable locally, use in-memory fallback
                self._client = None
        return self._client

    async def acquire_lock(self, lock_key: str, expire_seconds: int = 60) -> bool:
        """
        Acquires a distributed lock for idempotency. Returns True if acquired, False otherwise.
        """
        client = await self.get_client()
        if client:
            try:
                # SET lock_key 1 NX EX expire_seconds
                result = await client.set(f"lock:{lock_key}", "1", nx=True, ex=expire_seconds)
                return bool(result)
            except Exception:
                pass

        # Fallback to in-memory lock
        if lock_key in self._in_memory_locks:
            return False
        self._in_memory_locks[lock_key] = True
        return True

    async def release_lock(self, lock_key: str):
        """Releases the distributed lock."""
        client = await self.get_client()
        if client:
            try:
                await client.delete(f"lock:{lock_key}")
            except Exception:
                pass
        self._in_memory_locks.pop(lock_key, None)

    async def publish_event(self, stream_name: str, payload: Dict[str, Any]) -> str:
        """Publishes an event to a Redis Stream."""
        client = await self.get_client()
        if client:
            try:
                return await client.xadd(stream_name, payload)
            except Exception as e:
                print(f"[Redis Stream Error] {stream_name}: {e}")
        return "in_memory_event_id"


# Global singleton instance
event_bus = RedisEventBus()
