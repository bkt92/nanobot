"""Async message queue for decoupled channel-agent communication."""

import asyncio
from typing import Callable, Awaitable

from nanobot.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._subscribers: list[Callable[[InboundMessage | OutboundMessage, str], Awaitable[None]]] = []

    def subscribe(self, callback: Callable[[InboundMessage | OutboundMessage, str], Awaitable[None]]) -> None:
        """Subscribe to all message events for monitoring."""
        self._subscribers.append(callback)

    async def _notify(self, msg: InboundMessage | OutboundMessage, msg_type: str) -> None:
        """Notify all subscribers of a message event."""
        for subscriber in self._subscribers:
            try:
                await subscriber(msg, msg_type)
            except Exception as e:
                # Don't let subscriber errors break the message flow
                pass

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        await self.inbound.put(msg)
        await self._notify(msg, "inbound")

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        await self.outbound.put(msg)
        await self._notify(msg, "outbound")

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
