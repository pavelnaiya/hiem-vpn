import asyncio
import json
from typing import Set
from backend.logger import log

class EventBus:
    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()
        self.loop: asyncio.AbstractEventLoop = None

    def push(self, data: dict):
        if self.loop and not self.loop.is_closed():
            async def _broadcast():
                for q in list(self.subscribers):
                    await q.put(data)
            asyncio.run_coroutine_threadsafe(_broadcast(), self.loop)
        else:
            log.warning("EventBus: Loop not running, dropped event")

event_bus = EventBus()

async def heartbeat_loop():
    """Keeps SSE connections alive by pushing a ping every 30s."""
    while True:
        event_bus.push({"type": "ping"})
        await asyncio.sleep(30)
