"""In-memory event bus for SSE pub/sub."""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL = 30  # seconds
CONNECTION_TIMEOUT = 600  # 10 minutes


class EventBus:
    """Simple in-memory pub/sub for alert event streaming."""

    def __init__(self) -> None:
        self._subscribers: dict[str, asyncio.Queue[dict[str, Any]]] = {}

    def subscribe(self) -> tuple[str, asyncio.Queue[dict[str, Any]]]:
        """Create a new subscriber. Returns (subscriber_id, queue)."""
        subscriber_id = str(uuid.uuid4())
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers[subscriber_id] = queue
        logger.debug("Subscriber %s connected (total: %d)", subscriber_id, len(self._subscribers))
        return subscriber_id, queue

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(subscriber_id, None)
        logger.debug(
            "Subscriber %s disconnected (total: %d)", subscriber_id, len(self._subscribers)
        )

    async def publish(self, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        dead: list[str] = []
        for sub_id, queue in list(self._subscribers.items()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(sub_id)
                logger.warning("Subscriber %s queue full, removing", sub_id)

        for sub_id in dead:
            self._subscribers.pop(sub_id, None)

    async def stream(self, subscriber_id: str) -> AsyncIterator[str]:
        """Yield SSE-formatted events for a subscriber."""
        queue = self._subscribers.get(subscriber_id)
        if not queue:
            return

        start = time.monotonic()
        try:
            while time.monotonic() - start < CONNECTION_TIMEOUT:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                except TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            self.unsubscribe(subscriber_id)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


event_bus = EventBus()
