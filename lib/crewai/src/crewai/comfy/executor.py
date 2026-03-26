"""Embedded ComfyUI workflow executor for CrewAI.

This module provides a wrapper around ComfyUI's PromptExecutor,
allowing workflows to be executed directly without a separate server.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class MockServer:
    """Minimal server mock for embedded ComfyUI execution.

    Provides only the interface required by PromptExecutor:
    - client_id: Client identifier
    - last_node_id: Last executed node
    - send_sync(): Send sync event messages
    """

    def __init__(self):
        self.client_id: str | None = None
        self.last_node_id: str | None = None
        self._messages: list[tuple[str, dict, str | None]] = []

    def send_sync(self, event: str, data: dict, sid: str | None = None) -> None:
        """Store sync messages for later retrieval."""
        self._messages.append((event, data, sid))
        logger.debug(f"MockServer received: {event} - {data}")


class ComfyWorkflowExecutor:
    """Embedded ComfyUI workflow executor.

    Wraps ComfyUI's PromptExecutor to allow workflow execution
    directly within Python without requiring a separate server.

    Usage:
        executor = ComfyWorkflowExecutor()
        result = executor.execute(workflow)
    """

    def __init__(
        self,
        comfy_path: str | None = None,
        models_dir: str | None = None,
    ):
        """Initialize the executor.

        Args:
            comfy_path: Path to ComfyUI installation (for finding models).
                       If None, uses default locations.
            models_dir: Explicit models directory. Overrides comfy_path setting.
        """
        self.comfy_path = comfy_path
        self.models_dir = models_dir
        self._server: MockServer | None = None
        self._executor: Any | None = None
        self._initialized = False

    def _setup_path(self) -> None:
        """Add ComfyUI to sys.path if needed."""
        if self.comfy_path and self.comfy_path not in sys.path:
            sys.path.insert(0, self.comfy_path)
            logger.info(f"Added {self.comfy_path} to sys.path")

    def _init_executor(self) -> None:
        """Initialize the PromptExecutor with a mock server."""
        if self._initialized:
            return

        self._setup_path()

        try:
            from execution import PromptExecutor

            self._server = MockServer()
            self._executor = PromptExecutor(self._server)
            self._initialized = True
            logger.info("ComfyWorkflowExecutor initialized successfully")
        except ImportError as e:
            logger.error(f"Failed to import ComfyUI modules: {e}")
            raise RuntimeError(
                "ComfyUI modules not found. Ensure ComfyUI is properly copied "
                "or provide the correct comfy_path."
            ) from e

    @property
    def executor(self) -> Any:
        """Get the underlying PromptExecutor instance."""
        if not self._initialized:
            self._init_executor()
        return self._executor

    async def execute_async(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Execute a workflow asynchronously.

        Args:
            workflow: Workflow definition as dict with node_id -> {class_type, inputs}

        Returns:
            Dict with 'outputs' and 'meta' keys containing execution results

        Example workflow:
            {
                "1": {"class_type": "CheckpointLoaderSimple", "inputs": {...}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {...}},
                ...
            }
        """
        if not self._initialized:
            self._init_executor()

        prompt_id = str(uuid.uuid4())

        try:
            await self._executor.execute_async(workflow, prompt_id)
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            raise

        result = getattr(self._executor, "history_result", {})
        if not result:
            logger.warning(f"No history result for prompt_id: {prompt_id}")
            return {"outputs": {}, "meta": {}}

        return result

    def execute(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Execute a workflow synchronously.

        Args:
            workflow: Workflow definition dict

        Returns:
            Execution results dict
        """
        return asyncio.run(self.execute_async(workflow))

    def get_node_classes(self) -> dict[str, type]:
        """Get available node classes from NODE_CLASS_MAPPINGS.

        Returns:
            Dict mapping node names to node classes
        """
        if not self._initialized:
            self._init_executor()

        try:
            import nodes

            return nodes.NODE_CLASS_MAPPINGS
        except ImportError:
            logger.error("Failed to import nodes module")
            return {}

    def list_available_nodes(self) -> list[str]:
        """List all available node class names.

        Returns:
            List of node class names (e.g., ["KSampler", "CheckpointLoaderSimple", ...])
        """
        classes = self.get_node_classes()
        return sorted(classes.keys())
