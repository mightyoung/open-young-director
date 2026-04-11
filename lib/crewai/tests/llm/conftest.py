"""Pytest configuration for llm tests.

Disables event-based fixtures to avoid circular imports with crewai package.
"""

import pytest


# Override the reset_event_state fixture from the main conftest to be a no-op
@pytest.fixture
def reset_event_state():
    """Disabled for llm tests to avoid circular imports."""
    pass


# Override the cleanup_event_handlers fixture to be a no-op
@pytest.fixture
def cleanup_event_handlers():
    """Disabled for llm tests to avoid circular imports."""
    pass
