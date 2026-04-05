"""TaskRegistry - Inspired by Claude Code's Task architecture.

Manages the lifecycle, state, and output tracking of narrative tasks (writing,
reviewing, evolving). Enables self-healing and mission-level monitoring.
"""

from __future__ import annotations

from enum import Enum
import logging
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class NarrativeTask:
    """Representation of a unit of work in the novel pipeline."""
    def __init__(self, task_type: str, description: str, metadata: dict[str, Any] | None = None):
        self.id = f"{task_type[:1]}-{str(uuid.uuid4())[:8]}"
        self.task_type = task_type
        self.description = description
        self.status = TaskStatus.PENDING
        self.start_time = time.time()
        self.end_time: float | None = None
        self.metadata = metadata or {}
        self.error_log: list[str] = []
        self.retry_count = 0
        self.max_retries = 3

    def _preview(self, value: Any, max_chars: int = 240) -> str:
        text = str(value)
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3]}..."

    def start(self):
        self.status = TaskStatus.RUNNING
        logger.info(f"Task Started: {self.id} | {self.description}")

    def complete(self, result: Any = None):
        self.status = TaskStatus.COMPLETED
        self.end_time = time.time()
        if result is not None:
            self.metadata["result_preview"] = self._preview(result)
        logger.info(f"Task Completed: {self.id} in {self.end_time - self.start_time:.2f}s")

    def fail(self, error: str):
        self.error_log.append(error)
        if self.retry_count < self.max_retries:
            self.status = TaskStatus.RETRYING
            self.retry_count += 1
            logger.warning(f"Task Retrying: {self.id} | Attempt {self.retry_count} | Error: {error}")
        else:
            self.status = TaskStatus.FAILED
            self.end_time = time.time()
            logger.error(f"Task Failed: {self.id} | Final Error: {error}")

    def duration_seconds(self) -> float | None:
        if self.end_time is None:
            return None
        return round(self.end_time - self.start_time, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "task_type": self.task_type,
            "description": self.description,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds(),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_log": list(self.error_log),
            "metadata": dict(self.metadata),
        }

class TaskRegistry:
    """Global registry for monitoring and managing narrative tasks."""
    def __init__(self):
        self.tasks: dict[str, NarrativeTask] = {}

    def create_task(self, task_type: str, description: str, metadata: dict[str, Any] | None = None) -> NarrativeTask:
        task = NarrativeTask(task_type, description, metadata)
        self.tasks[task.id] = task
        return task

    def get_dashboard_summary(self) -> dict[str, int]:
        summary = {status.value: 0 for status in TaskStatus}
        for task in self.tasks.values():
            summary[task.status.value] += 1
        return summary

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable snapshot of the current task dashboard."""
        summary = self.get_dashboard_summary()
        tasks = [task.to_dict() for task in self.tasks.values()]
        active_tasks = [
            task.to_dict()
            for task in self.tasks.values()
            if task.status in {TaskStatus.RUNNING, TaskStatus.RETRYING, TaskStatus.FAILED}
        ]
        return {
            "summary": summary,
            "tasks": tasks,
            "active_tasks": active_tasks,
        }

    def print_status(self):
        """CLI representation of the current mission state."""
        summary = self.get_dashboard_summary()
        print(f"\n--- MISSION DASHBOARD ---")
        print(f"Pending: {summary['pending']} | Running: {summary['running']} | "
              f"Done: {summary['completed']} | Failed: {summary['failed']}")
        for tid, task in self.tasks.items():
            if task.status in [TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.RETRYING]:
                print(f"[{task.status.value.upper()}] {tid}: {task.description}")
