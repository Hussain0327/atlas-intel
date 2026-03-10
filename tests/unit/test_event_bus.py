"""Unit tests for EventBus pub/sub."""

import asyncio

import pytest

from atlas_intel.services.event_bus import EventBus


class TestEventBus:
    def test_subscribe_unsubscribe(self):
        bus = EventBus()
        sub_id, queue = bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(sub_id)
        assert bus.subscriber_count == 0

    async def test_publish_to_subscribers(self):
        bus = EventBus()
        sub_id, queue = bus.subscribe()

        await bus.publish({"type": "alert", "title": "test"})

        event = queue.get_nowait()
        assert event["type"] == "alert"
        assert event["title"] == "test"

        bus.unsubscribe(sub_id)

    async def test_publish_to_multiple_subscribers(self):
        bus = EventBus()
        sub1_id, q1 = bus.subscribe()
        sub2_id, q2 = bus.subscribe()

        await bus.publish({"type": "test"})

        assert q1.get_nowait()["type"] == "test"
        assert q2.get_nowait()["type"] == "test"

        bus.unsubscribe(sub1_id)
        bus.unsubscribe(sub2_id)

    async def test_publish_drops_full_queues(self):
        bus = EventBus()
        sub_id, queue = bus.subscribe()

        # Fill the queue (max 100)
        for i in range(100):
            await bus.publish({"i": i})

        assert bus.subscriber_count == 1

        # This should drop the subscriber
        await bus.publish({"overflow": True})
        assert bus.subscriber_count == 0

    async def test_stream_yields_events(self):
        bus = EventBus()
        sub_id, queue = bus.subscribe()

        # Put event and check stream
        await bus.publish({"type": "alert"})

        chunks = []
        async for chunk in bus.stream(sub_id):
            chunks.append(chunk)
            break  # Take one event and stop

        assert len(chunks) == 1
        assert "alert" in chunks[0]

    async def test_stream_heartbeat(self):
        """Test that stream yields heartbeat on timeout."""
        import atlas_intel.services.event_bus as eb

        original_heartbeat = eb.HEARTBEAT_INTERVAL
        eb.HEARTBEAT_INTERVAL = 0.1  # 100ms for test speed

        bus = EventBus()
        sub_id, queue = bus.subscribe()

        chunks = []
        async for chunk in bus.stream(sub_id):
            chunks.append(chunk)
            if len(chunks) >= 1:
                break

        eb.HEARTBEAT_INTERVAL = original_heartbeat
        assert any("heartbeat" in c for c in chunks)

    def test_unsubscribe_nonexistent(self):
        bus = EventBus()
        bus.unsubscribe("nonexistent-id")  # Should not raise

    async def test_stream_nonexistent_subscriber(self):
        bus = EventBus()
        chunks = []
        async for chunk in bus.stream("nonexistent"):
            chunks.append(chunk)
        assert chunks == []
