"""In-memory message queue for agent communication in FILM_DRAMA mode."""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict, deque

from .data_structures import HandoffMessage

logger = logging.getLogger(__name__)


class InMemoryMessageQueue:
    """In-memory message queue for agent communication.

    Suitable for single-process scenarios where all agents run in the same process.
    For distributed scenarios, use Redis or a similar pub/sub system.
    """

    # Capacity limits to prevent unbounded growth
    MAX_GLOBAL_QUEUE_SIZE = 1000
    MAX_PER_RECIPIENT_QUEUE = 100

    def __init__(self):
        self._queues: Dict[str, deque] = defaultdict(deque)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._global_queue: deque = deque()

    async def send(self, message: HandoffMessage) -> bool:
        """Send a message to a recipient's queue.

        Args:
            message: The HandoffMessage to send

        Returns:
            True if sent successfully
        """
        if message.recipient == "broadcast":
            # Enforce capacity limit on global queue
            while len(self._global_queue) >= self.MAX_GLOBAL_QUEUE_SIZE:
                self._global_queue.popleft()  # O(1) operation
            self._global_queue.append(message)
            logger.debug(f"Broadcast message from {message.sender}: {message.id}")
            return True

        queue = self._queues[message.recipient]
        async with self._locks[message.recipient]:
            # Enforce capacity limit per recipient
            while len(queue) >= self.MAX_PER_RECIPIENT_QUEUE:
                queue.popleft()  # O(1) operation
            queue.append(message)

        logger.debug(f"Message sent to {message.recipient}: {message.id}")
        return True

    async def receive(
        self,
        recipient: str,
        timeout: Optional[float] = None
    ) -> Optional[HandoffMessage]:
        """Receive a message for a recipient.

        Args:
            recipient: The recipient agent name
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            The received HandoffMessage or None if timeout
        """
        start_time = datetime.now()

        while True:
            # Use the SAME lock instance as send() for consistency
            async with self._locks[recipient]:
                # Check recipient's private queue
                if self._queues[recipient]:
                    return self._queues[recipient].popleft()

                # Check global queue for broadcasts (protected by same lock)
                for i, msg in enumerate(self._global_queue):
                    if msg.recipient == "broadcast" or msg.recipient == recipient:
                        del self._global_queue[i]
                        return msg

            # Check timeout BEFORE sleeping to avoid race condition
            if timeout is not None:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed >= timeout:
                    return None

            # Wait a bit before checking again (non-blocking)
            await asyncio.sleep(0.05)

    async def broadcast(self, message: HandoffMessage) -> bool:
        """Broadcast a message to all agents.

        Args:
            message: The message to broadcast

        Returns:
            True if broadcast successfully
        """
        message.recipient = "broadcast"
        return await self.send(message)

    def get_pending(self, recipient: str) -> List[HandoffMessage]:
        """Get all pending messages for a recipient without removing them.

        Args:
            recipient: The recipient agent name

        Returns:
            List of pending messages
        """
        pending = list(self._queues.get(recipient, []))
        pending.extend([m for m in self._global_queue if m.recipient == recipient])
        return pending

    def clear(self) -> None:
        """Clear all queues."""
        self._queues.clear()
        self._global_queue.clear()

    def size(self) -> int:
        """Get total number of messages in all queues."""
        total = len(self._global_queue)
        for queue in self._queues.values():
            total += len(queue)
        return total


class AgentMessageQueue:
    """Message queue wrapper for a single agent.

    Provides a clean interface for individual agents to use
    the shared message queue.
    """

    def __init__(self, agent_name: str, shared_queue: Optional[InMemoryMessageQueue] = None):
        self.agent_name = agent_name
        self._shared_queue = shared_queue or InMemoryMessageQueue()
        self._private_queue: List[HandoffMessage] = []

    async def send(self, message: HandoffMessage) -> bool:
        """Send a message."""
        if message.recipient == self.agent_name:
            # Self-message, add to private queue
            self._private_queue.append(message)
            return True
        return await self._shared_queue.send(message)

    async def receive(self, timeout: Optional[float] = None) -> Optional[HandoffMessage]:
        """Receive a message addressed to this agent."""
        # Check private queue first
        if self._private_queue:
            return self._private_queue.pop(0)

        # Check shared queue
        return await self._shared_queue.receive(self.agent_name, timeout=timeout)

    def get_pending(self) -> List[HandoffMessage]:
        """Get all pending messages for this agent."""
        pending = list(self._private_queue)
        pending.extend(self._shared_queue.get_pending(self.agent_name))
        return pending
