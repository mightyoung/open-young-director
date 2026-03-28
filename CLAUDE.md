# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **crewAI-based monorepo** for the young-writer content generation system. It extends crewAI with:

- **Content Generation**: Content creation pipelines via `crewai/content/` and `create_content.py`
- **Knowledge Base**: Vector storage and knowledge retrieval via `knowledge_base/`
- **A2A Protocol**: Agent-to-agent communication via `crewai/a2a/`

The framework is built on crewAI (independent of LangChain).

## Project Structure

```
lib/
├── crewai/               # Core framework
│   └── src/crewai/
│       ├── a2a/               # Agent-to-agent protocol (push, polling, streaming)
│       ├── agent/              # Agent core implementation
│       ├── agents/             # Agent execution, adapters (OpenAI, LangGraph)
│       ├── cli/                # CLI commands (create/run/chat/etc.)
│       │   └── templates/      # Project templates (crew, flow, tool)
│       ├── content/            # Content generation pipelines
│       ├── crew/                # Crew orchestration
│       ├── crews/               # Crew output handling
│       ├── flow/                # Flow DSL (@start, @listen, @router)
│       │   ├── async_feedback/  # Async feedback mechanisms
│       │   ├── human_feedback/ # Human-in-the-loop support
│       │   └── persistence/    # Flow state persistence
│       ├── knowledge/           # Knowledge base with vector storage
│       ├── llm/                 # LLM integration (OpenAI, Anthropic, Azure, etc.)
│       ├── memory/              # Agent memory systems
│       ├── mcp/                 # MCP (Model Context Protocol) integration
│       ├── tasks/               # Task definitions and outputs
│       └── tools/               # Base tool interfaces
├── crewai-tools/          # Tool integrations (RAG, search, etc.)
│   └── src/crewai_tools/
│       └── tools/              # 70+ tool implementations
├── crewai-files/          # File processing utilities
├── knowledge_base/         # Separate knowledge base workspace
└── devtools/               # Development utilities
```

## Development Commands

```bash
# Setup
uv lock && uv sync

# Install pre-commit hooks
pre-commit install

# Run tests (parallel by default)
uv run pytest .

# Run a specific test file
uv run pytest lib/crewai/tests/agents/test_agent.py

# Type checking
uvx mypy lib/crewai/src

# Lint
uv run ruff check lib/crewai/src

# Format
uv run ruff format lib/crewai/src

# Build packages
uv build
```

## Architecture Notes

### Core Concepts

- **Agent**: An AI agent with `role`, `goal`, and `backstory` that uses tools to accomplish tasks
- **Task**: A work item with description, expected output, and assigned agent
- **Crew**: A team of agents executing tasks, either `Process.sequential` or `Process.hierarchical`
- **Flow**: A Python class using decorators (`@start`, `@listen`, `@router`) for event-driven control flow
- **Content Pipeline**: Custom content generation via `crewai/cli/create_content.py` and `crewai/content/`

### Agent Adapters

The `agents/agent_adapters/` directory contains pluggable adapter implementations:
- `openai_agents/` - Uses OpenAI's agent API
- `langgraph/` - Integration with LangGraph for state management

### A2A Protocol

The `a2a/` module implements the Agent-to-Agent protocol with:
- **Push notifications** - Real-time agent communication
- **Polling** - Event subscription with configurable intervals
- **Streaming** - Streaming updates for long-running tasks
- Authentication via `auth/` (OAuth2, JWT, API key support)

### Tool System

Tools are defined in `crewai-tools` with a base `BaseTool` class. Tools can be:
- Built-in (file read/write, web search, RAG)
- Custom (user-defined via `crewai_tools`)

### CLI

The `crewai` CLI (entry point in `crewai/cli/cli.py`) supports:
- `crewai create crew <name>` - Scaffold new crew project
- `crewai create flow <name>` - Scaffold new flow
- `crewai create content <type>` - Scaffold content generation
- `crewai run` - Execute a crew
- `crewai chat <crew>` - Interactive crew chat
- `crewai login/logout` - Authentication

## Testing

Tests use pytest with VCR for HTTP recording/playback to avoid external API calls during tests. Test files are in `lib/*/tests/` directories, mirroring the source structure. Network access is blocked by default (`--block-network`).

Key fixtures in `conftest.py`:
- `cleanup_event_handlers` - Prevents event handler pollution between tests
- `reset_event_state` - Resets event system state for test isolation
- `setup_test_environment` - Sets `CREWAI_TESTING=true` and temp storage

Run tests with: `uv run pytest .` (parallel by default with `-n auto`)
