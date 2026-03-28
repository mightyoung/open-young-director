# FILM_DRAMA Mode Handoff Implementation Plan

## Overview

This document provides a detailed implementation plan for the FILM_DRAMA mode in the knowledge base system. The FILM_DRAMA mode simulates a film/TV production environment where multiple character agents interact through a handoff mechanism to generate novel chapters with distinct character perspectives.

## Table of Contents

1. [Core Data Structures and Interface Design](#1-core-data-structures-and-interface-design)
2. [DirectorAgent Responsibilities and API](#2-directoragent-responsibilities-and-api)
3. [CharacterAgent Responsibilities and API](#3-characteragent-responsibilities-and-api)
4. [SceneSimulator (Scene Filming Flow)](#4-scenesimulator-scene-filming-flow)
5. [Message Passing Mechanism](#5-message-passing-mechanism)
6. [File Structure](#6-file-structure)
7. [Phased Implementation Steps](#7-phased-implementation-steps)

---

## 1. Core Data Structures and Interface Design

### 1.1 Core Enums and Constants

```python
# agents/film_drama/enums.py
"""Enums and constants for FILM_DRAMA mode."""

from enum import Enum


class MessageType(Enum):
    """Handoff message types for agent communication."""
    # Director -> Character: Scene assignment
    HANDOFF = "handoff"
    # Character -> Director: Scene completion
    RESPONSE = "response"
    # Director -> Character: Modification request
    REVISE = "revise"
    # Character -> Character: Direct interaction (simulated by Director)
    DIALOGUE = "dialogue"
    # Director -> All: Scene setup
    SETUP = "setup"
    # Director -> All: Scene wrap
    WRAP = "wrap"
    # Any -> Any: Heartbeat/ping
    PING = "ping"
    # Director -> Non-main: Simulate NPC response
    NPC_SIMULATE = "npc_simulate"


class AgentRole(Enum):
    """Agent roles in FILM_DRAMA mode."""
    DIRECTOR = "director"
    MAIN_CHARACTER = "main_character"  # 韩林、柳如烟、叶尘等
    SUPPORTING_CHARACTER = "supporting_character"  # 太虚宗主等
    NPC_SIMULATED = "npc_simulated"  # Director模拟的非主要角色


class SceneStatus(Enum):
    """Scene processing status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BeatType(Enum):
    """Plot beat types for scene structuring."""
    OPENING = "opening"  # 开场
    DEVELOPMENT = "development"  # 发展
    CONFLICT = "conflict"  # 冲突
    CLIMAX = "climax"  # 高潮
    RESOLUTION = "resolution"  # 解决
    TRANSITION = "transition"  # 过渡
```

### 1.2 Core Dataclasses

```python
# agents/film_drama/data_structures.py
"""Core data structures for FILM_DRAMA mode."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


@dataclass
class HandoffMessage:
    """Message passed between agents during handoff."""
    id: str
    msg_type: str
    sender: str
    recipient: str
    scene_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    reply_to: Optional[str] = None


@dataclass
class PlotBeat:
    """A single beat in a scene's plot progression."""
    beat_id: str
    beat_type: str
    description: str
    expected_chars: List[str]
    sequence: int
    handoff_sequence: List[str] = field(default_factory=list)
    narration_requirement: str = ""


@dataclass
class Scene:
    """A scene being filmed in the production."""
    scene_id: str
    chapter: int
    location: str
    time_of_day: str
    beats: List[PlotBeat] = field(default_factory=list)
    status: str = SceneStatus.PENDING.value
    assigned_chars: List[str] = field(default_factory=list)
    current_beat_index: int = 0
    outputs: Dict[str, str] = field(default_factory=dict)
    narration: str = ""


@dataclass
class CharacterBible:
    """Character profile and context for an agent."""
    name: str
    role: str
    identity: str
    realm: str
    personality: str
    speaking_style: str
    backstory: str
    objective_this_chapter: str
    key_moments: List[str]
    relationships: Dict[str, str]
    visual_ref_path: Optional[str] = None
    current_state: Dict[str, Any] = field(default_factory=dict)

    def to_system_prompt(self, book_title: str = "太古魔帝传") -> str:
        return f"""你正在演绎修仙小说《{book_title}》中的角色【{self.name}】。

# 角色基础信息
- 姓名: {self.name}
- 身份: {self.identity}
- 境界: {self.realm}
- 性格: {self.personality}
- 说话风格: {self.speaking_style}

# 角色背景故事
{self.backstory}

# 本章目标
{self.objective_this_chapter}

# 与其他角色的关系
{chr(10).join(f"- {k}: {v}" for k, v in self.relationships.items())}

# 演绎要求
1. 始终以{self.name}的视角回应
2. 体现角色的独特性格和说话方式
3. 关注角色的内心感受和外在表现
4. 不超出角色当前境界的知识和认知
"""


@dataclass
class DirectorScript:
    """The director's script for a scene."""
    scene: Scene
    cast: List[CharacterBible]
    non_main_char_requirements: Dict[str, str] = field(default_factory=dict)
    required_beats: List[str] = field(default_factory=list)
    tension_points: List[str] = field(default_factory=list)
    cliffhanger: str = ""
```

---

## 2. DirectorAgent Responsibilities and API

### 2.1 Core Responsibilities

1. **Scene Planning**: Break chapter outlines into scenes and beats
2. **Cast Determination**: Decide which characters appear in each scene
3. **Handoff Orchestration**: Control sequence of agent interactions
4. **NPC Simulation**: Act as non-main characters when needed
5. **Scene Assembly**: Combine individual performances into coherent narration

### 2.2 DirectorAgent Class

```python
# agents/film_drama/director_agent.py
class DirectorAgent:
    """Director Agent that orchestrates scene filming with handoff mechanism.

    DECOMPOSE → DELEGATE → SYNTHESIZE pattern:
    1. DECOMPOSE: Break chapter into scenes, scenes into beats
    2. DELEGATE: Hand off to character agents in sequence
    3. SYNTHESIZE: Assemble character outputs into scene narration
    """

    def __init__(self, llm_client, message_queue, config=None, world_context=None):
        self.llm = llm_client
        self.message_queue = message_queue
        self.config = config or DirectorAgentConfig()
        self.world_context = world_context or {}
        self.name = "Director"
        self.role = AgentRole.DIRECTOR.value
        self._active_scenes: Dict[str, Scene] = {}
        self._character_bibles: Dict[str, CharacterBible] = {}

    async def plan_scene(self, chapter_outline, cast) -> DirectorScript:
        """Plan a scene based on chapter outline and cast."""
        # 1. Create scene object
        # 2. Decompose into beats
        # 3. Create character bibles
        # 4. Determine handoff sequence
        pass

    async def execute_scene(self, script: DirectorScript) -> Dict[str, Any]:
        """Execute planned scene with handoff mechanism."""
        # Core filming loop:
        # 1. For each beat in sequence
        # 2. Hand off to characters in determined order
        # 3. Collect responses
        # 4. Simulate NPCs if needed
        # 5. Assemble into final scene narration
        pass

    async def simulate_npc(self, npc_name: str, context: Dict[str, Any]) -> str:
        """Simulate a non-main character response (Director acts as NPC)."""
        pass

    def assemble_scene_output(self, scene: Scene, outputs: Dict[str, str]) -> str:
        """Assemble character outputs into coherent scene narration."""
        pass
```

---

## 3. CharacterAgent Responsibilities and API

### 3.1 Core Responsibilities

1. **Maintain Character Bible**: Keep character profile, personality, speaking style
2. **Respond to Handoffs**: Receive scene assignments from Director and respond
3. **Perform Beats**: Execute dramatic beats from the script
4. **Request Handoffs**: Can request to hand off to another character for dialogue
5. **Track State**: Maintain character's emotional/mental state across beats

### 3.2 CharacterAgent Class

```python
# agents/film_drama/character_agent.py
class CharacterAgent:
    """Character Agent that performs as a specific character.

    RECEIVE → ACT → RESPOND cycle:
    1. RECEIVE: Receive handoff message from Director
    2. ACT: Process the beat and generate character response
    3. RESPOND: Send response back to Director
    """

    def __init__(self, name, character_bible, llm_client, message_queue):
        self.name = name
        self.character_bible = character_bible
        self.role = AgentRole.MAIN_CHARACTER.value
        self.llm = llm_client
        self.message_queue = message_queue
        self._emotional_state: Dict[str, Any] = {}
        self._pending_handoffs: List[HandoffMessage] = []
        self._completed_beats: List[str] = []

    async def receive_message(self, message: HandoffMessage) -> None:
        """Handle receiving a message from Director."""
        if message.msg_type == MessageType.HANDOFF.value:
            self._pending_handoffs.append(message)

    async def act(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the agent's main action for a beat."""
        beat = context.get("beat")
        prompt = self._build_act_prompt(beat, context)
        output = self.llm.generate(messages=[{"role": "user", "content": prompt}])
        return {"output": output, "state_update": self._update_emotional_state(beat, output)}

    def _build_act_prompt(self, beat: PlotBeat, context: Dict[str, Any]) -> str:
        """Build character-specific prompt for beat."""
        bible = self.character_bible
        previous_outputs = context.get("previous_outputs", {})
        return f"""{bible.to_system_prompt()}

# 当前场景节拍
类型: {beat.beat_type}
描述: {beat.description}

请以{self.name}的角色视角，描写对这个场景节拍的回应。
要求: 体现角色独特性格和说话风格，200-500字
"""

    async def request_handoff(self, target: str, context: Dict[str, Any]) -> HandoffMessage:
        """Request to hand off to another agent for dialogue."""
        return HandoffMessage(
            id=f"req_handoff_{self.name}_to_{target}",
            msg_type=MessageType.HANDOFF.value,
            sender=self.name,
            recipient="Director",
            scene_id=context.get("scene_id", ""),
            content=f"Requesting handoff to {target}",
            metadata={"target": target, "reason": "dialogue"}
        )
```

---

## 4. SceneSimulator (Scene Filming Flow)

### 4.1 SceneSimulator Class

```python
# agents/film_drama/scene_simulator.py
class SceneSimulator:
    """Simulates the film production workflow."""

    def __init__(self, director: DirectorAgent, filming_config=None):
        self.director = director
        self.config = filming_config or FilmingConfig()
        self._character_agents: Dict[str, CharacterAgent] = {}
        self._message_queue: List[HandoffMessage] = []

    async def film_scene(self, script: DirectorScript) -> Dict[str, Any]:
        """Film a complete scene.

        1. Setup - Spawn character agents
        2. Film - Execute via Director with handoff
        3. Wrap - Cleanup
        """
        scene = script.scene
        scene.status = SceneStatus.IN_PROGRESS.value

        # Phase 1: Setup
        await self._setup_character_agents(script)

        # Phase 2: Film with handoffs
        result = await self._film_with_handoffs(script)

        # Phase 3: Wrap
        await self._cleanup_character_agents()
        scene.status = SceneStatus.COMPLETED.value

        return result

    async def _film_with_handoffs(self, script: DirectorScript) -> Dict[str, Any]:
        """Film scene using handoff mechanism."""
        scene = script.scene

        # Broadcast SETUP
        await self._broadcast_message(MessageType.SETUP, {...})

        all_outputs = {}
        for beat in scene.beats:
            beat_result = await self._process_beat_with_handoff(beat, script)
            all_outputs.update(beat_result)

        # Broadcast WRAP
        await self._broadcast_message(MessageType.WRAP, {...})

        return {"scene_id": scene.scene_id, "outputs": all_outputs}
```

---

## 5. Message Passing Mechanism

### 5.1 Handoff Protocol

```python
# agents/film_drama/handoff_protocol.py
class HandoffProtocol:
    """Manages handoff protocol between agents."""

    async def initiate_handoff(self, from_agent, to_agent, scene_id, context):
        """Initiate handoff from one agent to another."""
        handoff_id = f"handoff_{from_agent}_to_{to_agent}"
        self._active_handoffs[handoff_id] = HandoffContext(...)
        return handoff_id

    async def complete_handoff(self, handoff_id, response):
        """Mark handoff as complete."""
        ctx = self._active_handoffs[handoff_id]
        ctx.state = HandoffState.COMPLETE
        ctx.response = response
```

### 5.2 Message Queue

```python
# agents/film_drama/message_queue.py
class InMemoryMessageQueue:
    """In-memory message queue for agent communication."""

    async def send(self, message: HandoffMessage) -> bool:
        if message.recipient == "broadcast":
            self._global_queue.append(message)
        else:
            self._queues[message.recipient].append(message)
        return True

    async def receive(self, recipient: str, timeout=None):
        """Receive message for recipient."""
        # Check private queue first, then global
        if self._queues.get(recipient):
            return self._queues[recipient].pop(0)
        # Check broadcasts
        for msg in self._global_queue:
            if msg.recipient == "broadcast":
                return msg
        return None
```

---

## 6. File Structure

```
agents/
├── film_drama/                    [NEW - FILM_DRAMA mode package]
│   ├── __init__.py
│   ├── enums.py                  [NEW - MessageType, AgentRole, SceneStatus, BeatType]
│   ├── data_structures.py        [NEW - HandoffMessage, PlotBeat, Scene, CharacterBible]
│   ├── interfaces.py             [NEW - Abstract interfaces]
│   ├── message_queue.py          [NEW - InMemoryMessageQueue]
│   ├── handoff_protocol.py       [NEW - HandoffProtocol]
│   ├── director_agent.py         [NEW - DirectorAgent]
│   ├── character_agent.py        [NEW - CharacterAgent]
│   ├── scene_simulator.py        [NEW - SceneSimulator]
│   └── prompts/                  [NEW - Prompt templates]
│       ├── director_prompts.py
│       ├── character_prompts.py
│       └── assembly_prompts.py
```

---

## 7. Phased Implementation Steps

### Phase 1: Foundation (Days 1-2)
- Create package structure
- Implement enums and data structures
- Implement message queue
- Implement handoff protocol

### Phase 2: DirectorAgent (Days 3-4)
- Implement scene planning
- Implement beat decomposition
- Implement handoff orchestration
- Implement NPC simulation
- Implement scene assembly

### Phase 3: CharacterAgent (Days 5-6)
- Implement character agent class
- Implement beat performance
- Implement handoff requests
- Implement state management

### Phase 4: SceneSimulator (Days 7-8)
- Implement filming flow
- Implement callback system
- Implement error handling

### Phase 5: Integration (Days 9-10)
- Integrate with NovelOrchestrator
- Add prompt templates
- Add configuration
- Testing and bug fixes

---

## Key Design Decisions

### Handoff Sequence for Dialogue Scenes

When a beat involves dialogue between characters:

1. Director sends HANDOFF to first character (e.g., 韩林)
2. 韩林 performs beat, may request handoff to 柳如烟
3. Director grants and sends HANDOFF to 柳如烟
4. 柳如烟 performs beat
5. Director assembles both outputs into scene narration

### NPC Simulation

Non-main characters are simulated by DirectorAgent when:
1. Scene requires NPC dialogue (e.g., "弟子惊呼", "长老皱眉")
2. Background character reaction needed
3. Atmospheric description needed

### Beat Type Classification

| BeatType | Description | Character Focus |
|----------|-------------|-----------------|
| OPENING | Scene start | Establish setting and mood |
| DEVELOPMENT | Plot progression | Character thoughts and reactions |
| CONFLICT | Confrontation | Emotional intensity |
| CLIMAX | Peak moment | Maximum character expression |
| RESOLUTION | Aftermath | Reflection and transition |
| TRANSITION | Scene change | Brief bridge |

---

## Success Criteria

- FILM_DRAMA mode generates chapters with distinct character perspectives
- Handoff mechanism correctly sequences character interactions
- DirectorAgent can simulate NPCs when needed
- SceneSimulator orchestrates complete filming flow
- Integration with existing NovelOrchestrator works seamlessly
- Performance: FILM_DRAMA mode completes chapter in <= 2x standard mode time

---

## 8. deer-flow Architecture Learnings

### 8.1 Referenced Patterns from deer-flow

DeerFlow (`/Users/muyi/Downloads/dev/deer-flow`) is a production-ready LangGraph-based multi-agent framework. Key patterns identified:

#### Middleware Chain Pattern
DeerFlow uses ordered middleware chain for cross-cutting concerns.

**FILM_DRAMA Adaptation**: CharacterAgent middleware chain.

#### SubagentLimitMiddleware Pattern
Limits concurrent subagent calls to a maximum (typically 3).

**FILM_DRAMA Adaptation**: Limit concurrent characters per beat to 3.

#### ClarificationMiddleware Pattern
Interrupts execution for human clarification via `ask_clarification` tool.

**FILM_DRAMA Adaptation**: CharacterAgent can request `CLARIFY` when scene context is ambiguous.

#### Memory Queue with Debounce
Per-character memory tracking via `agent_name` parameter.

**FILM_DRAMA Adaptation**: CharacterMemoryQueue per character.

---

## 9. Current State Analysis

### 9.1 Existing Components

| File | Status | Description |
|------|--------|-------------|
| `novel_orchestrator.py` | Stub (methods exist but not implemented) | `OrchestratorConfig` with FILM_DRAMA mode, skeleton methods |
| `novel_generator.py` | **Active** | Single-agent generator, works with progressive disclosure |
| `kimi_client.py` | **Active** | LLM client with CLI/API modes |
| `chapter_manager.py` | **Active** | Chapter context building with progressive disclosure |
| `outline_loader.py` | **Active** | Outline loading and enforcement |
| `knowledge_extractor.py` | **Active** | Knowledge extraction to SQLite |
| `feedback_loop.py` | **Active** | Feedback loop with LIGHT/DEEP/VOLUME modes |
| `run_novel_generation.py` | **Active** | Main entry point |

### 9.2 Current Architecture

```
run_novel_generation.py
    └── NovelGeneratorAgent.generate_chapter()
            └── KimiClient.generate()  (single LLM call)
```

**Problem**: Single-agent mode, no multi-agent orchestration despite `OrchestratorConfig` having FILM_DRAMA mode.

### 9.3 What's Already in Place

**OrchestratorConfig** (already exists):
```python
@dataclass
class OrchestratorConfig:
    max_subagent_concurrent: int = 5
    max_concurrent_scenes: int = 3
    enable_verification: bool = True
    mode: str = "FILM_DRAMA"
    num_subagents: int = 3
```

**NovelOrchestrator skeleton** (already exists):
- `setup()` - initializes orchestrator
- `orchestrate_chapter()` - orchestrates chapter generation
- `create_plot_outline()` - creates detailed plot outline
- `determine_cast()` - determines character cast
- `setup_subagents()` - sets up sub-agents
- `orchestrate_scenes()` - orchestrates scene generation
- `assemble_plot()` - assembles scenes into final plot
- `evaluate_evolution()` - evaluates plot evolution

### 9.4 Implementation Strategy

Given the current state, we have two approaches:

#### Option A: Incremental Integration (Recommended)
**Integrate FILM_DRAMA into existing NovelGeneratorAgent gradually**

1. Keep `NovelGeneratorAgent` as the main entry point
2. Add `DirectorAgent` and `CharacterAgent` as optional components
3. When FILM_DRAMA mode enabled, use multi-agent path
4. Fallback to single-agent for backwards compatibility

**Advantage**: Minimal disruption, can test incrementally
**Risk**: Hybrid code paths may be confusing

#### Option B: Full Replacement
Replace `NovelGeneratorAgent` with FILM_DRAMA flow

**Advantage**: Clean architecture
**Risk**: Breaking changes, requires full testing

### 9.5 Updated Implementation Plan

Given existing codebase, here's the pragmatic implementation:

---

## 10. Pragmatic Implementation Plan

### Phase 0: Foundation (Days 1-2) - Minimal Viable
**Goal**: Get FILM_DRAMA working with minimal code changes

#### Step 0.1: Create film_drama package structure
```
agents/film_drama/
├── __init__.py
├── enums.py           # MessageType, AgentRole, SceneStatus, BeatType
├── data_structures.py  # HandoffMessage, PlotBeat, Scene, CharacterBible
├── message_queue.py    # InMemoryMessageQueue
```

#### Step 0.2: Implement DirectorAgent (minimal)
```python
# director_agent.py - minimal implementation
class DirectorAgent:
    def __init__(self, llm_client):
        self.llm = llm_client

    def plan_scene(self, chapter_outline, cast) -> DirectorScript:
        # Decompose chapter into beats
        # Create character bibles
        pass

    def execute_scene(self, script) -> Dict[str, Any]:
        # For each beat, call LLM with all characters
        # (skip actual agent handoff for now)
        pass
```

#### Step 0.3: Add to NovelOrchestrator
```python
# Add to orchestrate_chapter() in NovelOrchestrator
def orchestrate_chapter(self, ...):
    if self.config.mode == "FILM_DRAMA" and self.director_agent:
        return self._orchestrate_film_drama(...)
    else:
        return self._orchestrate_standard(...)
```

**Deliverable**: End-to-end chapter generation using DirectorAgent (single LLM per beat)

---

### Phase 1: Agent Handoff (Days 3-4)
**Goal**: Add proper character agent handoff

- Add `CharacterAgent` class
- Add `MessageQueue` for agent communication
- Implement `handoff_to_character()` in DirectorAgent
- Implement `receive_message()` and `act()` in CharacterAgent

**Deliverable**: Multiple characters can be called in sequence for a beat

---

### Phase 2: Concurrency + Memory (Days 5-6)
**Goal**: Improve quality with concurrency and memory

- Implement `MAX_CONCURRENT_CHARACTERS = 3`
- Add `CharacterMemoryQueue` for emotional state
- Implement `CLARIFY` message type for ambiguity

**Deliverable**: Concurrent character execution with state tracking

---

### Phase 3: Middleware + Integration (Days 7-8)
**Goal**: Add middleware and finalize integration

- Add `CharacterMiddleware` base class
- Add `EmotionalStateMiddleware`
- Integrate into `NovelOrchestrator` fully
- Update `run_novel_generation.py` to use FILM_DRAMA mode

**Deliverable**: Full FILM_DRAMA mode integrated

---

### Phase 4: Testing + Polish (Days 9-10)
**Goal**: Ensure quality and stability

- Unit tests for core components
- Integration tests
- Performance comparison with single-agent mode
- Documentation

**Deliverable**: Production-ready FILM_DRAMA mode

---

## 11. Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Integration approach | Incremental (Option A) | Minimal disruption, testable |
| Handoff mechanism | Direct function call | Simpler than async messaging for now |
| Concurrency | ≤3 characters/beat | Prevent context overflow |
| State management | Per-character memory | Better isolation |
| Fallback | Single-agent mode | Backwards compatibility |
