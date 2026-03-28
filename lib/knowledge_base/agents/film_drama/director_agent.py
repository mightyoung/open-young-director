"""DirectorAgent for FILM_DRAMA mode - orchestrates scene generation."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from .enums import MessageType, AgentRole, SceneStatus, BeatType
from .data_structures import (
    HandoffMessage,
    PlotBeat,
    Scene,
    CharacterBible,
    DirectorScript,
)
from .message_queue import InMemoryMessageQueue
from .character_agent import CharacterAgent
from .character_memory import CharacterMemoryQueue
from .middleware import (
    MiddlewareChain,
    CharacterMiddleware,
    EmotionalStateMiddleware,
    SubagentLimitMiddleware,
    ClarificationMiddleware,
    MemoryQueueMiddleware,
)

logger = logging.getLogger(__name__)


@dataclass
class DirectorConfig:
    """Configuration for DirectorAgent."""
    max_beats_per_scene: int = 8
    max_concurrent_character_agents: int = 3
    enable_npc_simulation: bool = True
    beat_decomposition_style: str = "beat_based"  # or "progressive_disclosure"
    stream_to_stdout: bool = False


class DirectorAgent:
    """Directs scene generation in FILM_DRAMA mode.

    Responsibilities:
    1. plan_scene() - decompose chapter into beats and create character bibles
    2. execute_scene() - for each beat, call LLM (simplified handoff)
    3. assemble_scene_output() - combine character outputs into scene narration

    ## Agent Configuration (Markdown + YAML Frontmatter)

    The DirectorAgent uses structured prompts for scene orchestration:

    ```yaml
    name: DirectorAgent
    role: scene_director
    capabilities:
      - beat_decomposition
      - character_orchestration
      - scene_assembly
      - tension_management
    ```
    """

    # ==================== SYSTEM PROMPT ====================

    SYSTEM_PROMPT_TEMPLATE = """---
name: DirectorAgent
role: scene_director
mode: FILM_DRAMA
color: "#9B59B6"
emoji: "🎬"
---

# DirectorAgent | 导演代理

## Identity & Memory

你是**导演代理**，一个专注于小说场景规划和叙事结构设计的AI专家。

你的核心能力是将章节大纲分解为具体的场景、人物动作和对话，确保情节连贯性和叙事张力。

**职责范围**:
- 场景规划与分解
- 情节点编排
- 人物视角分配
- 张力节奏把控

## Core Mission

### 场景分解
- 将章节大纲分解为多个场景
- 每个场景包含：开场、发展、冲突、高潮、解决、过渡
- 维护场景之间的叙事连贯性

### 节拍编排
- 遵循 BeatType 结构: OPENING → DEVELOPMENT → CONFLICT → CLIMAX → RESOLUTION → TRANSITION
- 识别关键张力点
- 管理角色出场顺序

### 角色协调
- 创建角色圣经 (CharacterBible)
- 管理角色情感状态
- 确保人物对话符合角色设定

## Critical Rules

- CRITICAL: 必须遵循 FILM_DRAMA 模式的核心原则
- CRITICAL: 场景分解必须保持叙事连贯性
- CRITICAL: 情感状态必须在角色间保持一致
- IMPORTANT: 人物对话必须符合角色设定（境界、性格、说话风格）
- IMPORTANT: 每个场景必须有明确的目标和结果
- NEVER: 不要生成与章节大纲冲突的内容
- NEVER: 不要改变已建立的人物关系

## Workflow

1. **Plan Scene** (plan_scene)
   - 分析章节大纲
   - 识别关键情节点
   - 分解场景结构
   - 分配人物视角
   - 创建角色圣经

2. **Execute Scene** (execute_scene)
   - 并发处理角色响应（≤3个并发）
   - 管理情感状态
   - 处理NPC模拟
   - 更新全局张力

3. **Assemble Output** (assemble_scene_output)
   - 整合角色响应
   - 添加场景叙述
   - 生成最终场景文本

## Tool Definitions (XML Format)

### Available Tools

```xml
<tools>
  <tool name="plan_scene">
    <description>将章节大纲分解为场景和节拍</description>
    <parameters>
      <param name="chapter_number" type="int">章节编号</param>
      <param name="scene_outline" type="str">场景大纲描述</param>
      <param name="characters" type="dict">角色信息字典</param>
      <param name="location" type="str">场景位置</param>
      <param name="time_of_day" type="str">时间段</param>
    </parameters>
  </tool>

  <tool name="execute_scene">
    <description>执行场景，生成角色响应</description>
    <parameters>
      <param name="script" type="DirectorScript">导演脚本</param>
    </parameters>
  </tool>

  <tool name="assemble_scene_output">
    <description>整合角色响应为场景文本</description>
    <parameters>
      <param name="script" type="DirectorScript">导演脚本</param>
      <param name="include_narration" type="bool">是否包含叙述</param>
    </parameters>
  </tool>
</tools>
```

## Success Metrics

- 场景数量准确度: > 90%
- 情节点覆盖率: 100% (所有大纲要求的情节都必须覆盖)
- 人物对话一致性: > 95%
- 叙事连贯性: > 90%
- 张力节奏评分: 按照 BeatType 递增/递减合理

## Beat Type Definitions

| BeatType | Chinese | Tension | Description |
|----------|---------|---------|-------------|
| OPENING | 开场 | 0.1 | 设置场景，介绍参与者 |
| DEVELOPMENT | 发展 | 0.3 | 人物互动，情况展开 |
| CONFLICT | 冲突 | 0.6 | 紧张升级，分歧或反对 |
| CLIMAX | 高潮 | 0.9 | 紧张或决策的顶峰时刻 |
| RESOLUTION | 解决 | 0.4 | 冲突解决或转折 |
| TRANSITION | 过渡 | 0.2 | 为下一场景做铺垫 |

## Output Format

场景输出格式：
```
【场景】位置，时间
◆开场
【角色A】对话/动作
【角色B】对话/动作
◆发展
...
```
"""

    def __init__(
        self,
        agent_name: str = "director",
        llm_client=None,
        config: DirectorConfig = None,
        message_queue: InMemoryMessageQueue = None,
        memory_queue: CharacterMemoryQueue = None,
        middleware_chain: MiddlewareChain = None,
    ):
        self.agent_name = agent_name
        self.llm_client = llm_client
        self.config = config or DirectorConfig()
        self.message_queue = message_queue or InMemoryMessageQueue()
        self.memory_queue = memory_queue or CharacterMemoryQueue()

        # Middleware chain
        if middleware_chain:
            self._middleware_chain = middleware_chain
        else:
            self._middleware_chain = self._create_default_middleware()

        # Active state
        self._current_script: Optional[DirectorScript] = None
        self._beat_outputs: Dict[str, Dict[str, str]] = {}  # beat_id -> {char_name: output}
        self._npc_outputs_by_beat: Dict[str, str] = {}  # beat_id -> NPC output
        self._character_agents: Dict[str, CharacterAgent] = {}
        self._protagonist_constraint: str = ""

    def _create_default_middleware(self) -> MiddlewareChain:
        """Create default middleware chain.

        Order from least to most side effects:
        1. EmotionalStateMiddleware - read-only, no state modification
        2. SubagentLimitMiddleware - read-only, enforces concurrency limits
        3. MemoryQueueMiddleware - has side effects (records memory)
        4. ClarificationMiddleware - may trigger retry, placed last
        """
        chain = MiddlewareChain()
        chain.add(EmotionalStateMiddleware())  # First: read-only
        chain.add(SubagentLimitMiddleware(self.memory_queue))  # Second: read-only
        chain.add(MemoryQueueMiddleware(self.memory_queue))  # Third: has side effects
        chain.add(ClarificationMiddleware())  # Last: may trigger retry
        return chain

    def add_middleware(self, middleware: CharacterMiddleware) -> None:
        """Add a middleware to the chain."""
        self._middleware_chain.add(middleware)

    # ==================== PUBLIC API ====================

    def plan_scene(
        self,
        chapter_number: int,
        scene_outline: str,
        characters: Dict[str, Dict[str, Any]],
        location: str,
        time_of_day: str = "morning",
        previous_context: str = "",
        protagonist_constraint: str = "",
        title: str = "",
        bible_constraint: str = "",
    ) -> DirectorScript:
        """Plan a scene by decomposing into beats and creating character bibles.

        Args:
            chapter_number: Current chapter number
            scene_outline: Description of what happens in this scene
            characters: Dict of character info {name: {identity, realm, personality, ...}}
            location: Scene location
            time_of_day: Time setting
            previous_context: Previous chapter/scene context for progressive disclosure
            protagonist_constraint: Hard constraint specifying the absolute protagonist and role assignments
            title: Scene title (extracted from scene_outline if not provided)
            bible_constraint: Production Bible constraints (world rules, facts, foreshadowing) to follow

        Returns:
            DirectorScript with scene structure and character bibles
        """
        logger.info(f"[Director] Planning scene for chapter {chapter_number}")

        # Extract title from scene_outline if not provided
        if not title and scene_outline:
            title = scene_outline.split("。")[0][:50] if "。" in scene_outline else scene_outline[:50]

        # Store protagonist constraint for later handoffs
        self._protagonist_constraint = protagonist_constraint
        # Store bible constraint for later handoffs
        self._bible_constraint = bible_constraint

        # Step 1: Decompose scene outline into beats
        beats = self._decompose_into_beats(scene_outline, characters, protagonist_constraint, bible_constraint)

        # Step 2: Create scene
        scene = Scene(
            scene_id=f"ch{chapter_number}_scene_{uuid.uuid4().hex[:8]}",
            chapter=chapter_number,
            location=location,
            time_of_day=time_of_day,
            title=title,
            beats=beats,
            status=SceneStatus.PENDING.value,
        )

        # Step 3: Create character bibles
        cast = self._create_character_bibles(
            characters, beats, previous_context, chapter_number
        )

        # Step 4: Create director script
        script = DirectorScript(
            scene=scene,
            cast=cast,
            non_main_char_requirements=self._extract_npc_requirements(beats, characters),
            required_beats=[b.beat_id for b in beats],
            tension_points=self._identify_tension_points(beats),
        )

        self._current_script = script
        self._beat_outputs = {}
        self._npc_outputs_by_beat = {}

        logger.info(
            f"[Director] Scene planned: {len(beats)} beats, {len(cast)} characters"
        )
        return script

    async def execute_scene(
        self,
        script: DirectorScript,
        llm_call_fn=None,
    ) -> Dict[str, Any]:
        """Execute scene by processing each beat with character agents.

        Uses concurrent handoff with ≤3 character limit:
        1. Spawn character agents from cast
        2. For each beat, hand off to characters in batches of max_concurrent
        3. Collect responses, update memory, and assemble

        Args:
            script: The director script from plan_scene()
            llm_call_fn: Async function to call LLM (optional, uses self.llm_client)

        Returns:
            Dict with scene outputs and status
        """
        import asyncio

        logger.info(f"[Director] Executing scene: {script.scene.scene_id}")
        script.scene.status = SceneStatus.IN_PROGRESS.value
        has_failures = False

        # Clear memory and reset middleware for new scene
        self.memory_queue.clear()
        self._middleware_chain.reset()

        # Spawn character agents
        self._spawn_character_agents(script)

        llm_fn = llm_call_fn or self._default_llm_call
        max_concurrent = self.config.max_concurrent_character_agents

        for beat in script.scene.beats:
            logger.debug(f"[Director] Processing beat: {beat.beat_id}")

            # Get characters that need to respond for this beat
            chars_to_process = [
                char_name for char_name in beat.expected_chars
                if char_name in self._character_agents
            ]

            # Process in batches of max_concurrent
            for i in range(0, len(chars_to_process), max_concurrent):
                batch = chars_to_process[i:i + max_concurrent]
                logger.debug(
                    f"[Director] Beat {beat.beat_id}: processing batch "
                    f"{i//max_concurrent + 1} with {len(batch)} chars: {batch}"
                )

                # Create tasks for concurrent execution with index tracking
                indexed_tasks = [
                    (idx, char_name, asyncio.create_task(
                        self._handoff_with_memory(
                            character_name=char_name,
                            beat=beat,
                            script=script,
                            llm_fn=llm_fn,
                        )
                    ))
                    for idx, char_name in enumerate(batch)
                ]

                # Execute batch concurrently
                results = await asyncio.gather(
                    *[task[2] for task in indexed_tasks],
                    return_exceptions=True
                )

                # Store outputs and update memory (using index to avoid zip ambiguity)
                for idx, char_name, _ in indexed_tasks:
                    result = results[idx]
                    if isinstance(result, Exception):
                        logger.warning(f"[Director] {char_name} failed: {result}, retrying...")
                        # Retry up to 2 times (total 3 attempts)
                        max_retries = 2
                        retry_success = False
                        for retry_count in range(max_retries):
                            try:
                                result = await self._handoff_with_memory(
                                    character_name=char_name,
                                    beat=beat,
                                    script=script,
                                    llm_fn=llm_fn,
                                )
                                retry_success = True
                                logger.info(f"[Director] {char_name} succeeded on retry {retry_count + 1}")
                                break
                            except Exception as retry_err:
                                logger.error(f"[Director] Retry {retry_count + 1}/{max_retries} failed for {char_name}: {retry_err}")

                        if not retry_success:
                            # Don't store placeholder - mark as failed
                            logger.error(f"[Director] {char_name} failed after {max_retries} retries")
                            has_failures = True
                            continue  # Skip storing this character's output for this beat

                    # Store per beat (only if successful)
                    if beat.beat_id not in self._beat_outputs:
                        self._beat_outputs[beat.beat_id] = {}
                    self._beat_outputs[beat.beat_id][char_name] = result

            # Handle NPC simulation for non-main characters
            if self.config.enable_npc_simulation:
                npc_response = await self._simulate_npc_response(
                    beat=beat,
                    script=script,
                    llm_fn=llm_fn,
                    protagonist_constraint=self._protagonist_constraint,
                )
                if npc_response:
                    self._npc_outputs_by_beat[beat.beat_id] = npc_response

            # Update global tension based on beat type
            await self._update_tension_for_beat(beat)

        if has_failures:
            script.scene.status = SceneStatus.FAILED.value
        else:
            script.scene.status = SceneStatus.COMPLETED.value

        # Capture outputs before cleanup
        beat_outputs = dict(self._beat_outputs)
        npc_outputs_by_beat = dict(self._npc_outputs_by_beat)
        scene_summary = self.memory_queue.get_scene_summary()

        # Cleanup character agents
        self._cleanup_character_agents()

        # Clear beat outputs to prevent pollution of next scene
        self._beat_outputs = {}
        self._npc_outputs_by_beat = {}

        # Cleanup current script
        self._current_script = None

        return {
            "scene_id": script.scene.scene_id,
            "status": script.scene.status,
            "beat_outputs": beat_outputs,
            "npc_outputs_by_beat": npc_outputs_by_beat,
            "scene_summary": scene_summary,
        }

    def _get_previous_outputs_flat(self) -> Dict[str, List[str]]:
        """Get previous outputs in flat {char_name: [outputs]} format."""
        flat: Dict[str, List[str]] = {}
        for beat_outputs in self._beat_outputs.values():
            for char_name, output in beat_outputs.items():
                if char_name not in flat:
                    flat[char_name] = []
                flat[char_name].append(output)
        return flat

    async def _handoff_with_memory(
        self,
        character_name: str,
        beat: PlotBeat,
        script: DirectorScript,
        llm_fn,
    ) -> str:
        """Hand off to character and process through middleware."""
        # Build previous outputs in flat format
        previous_outputs_flat = self._get_previous_outputs_flat()

        context = {
            "previous_outputs": previous_outputs_flat,
            "scene_info": {
                "location": script.scene.location,
                "time_of_day": script.scene.time_of_day,
            },
            "scene_id": script.scene.scene_id,
            "memory": self.memory_queue.get_context_for_character(character_name, include_history=True),
            "global_tension": self.memory_queue.get_global_tension(),
        }

        await self._middleware_chain.on_beat_start(character_name, beat, context)

        # Get response via handoff
        response = await self.handoff_to_character(
            character_name=character_name,
            beat=beat,
            script=script,
            previous_outputs=previous_outputs_flat,
            llm_fn=llm_fn,
        )

        # Process through middleware chain
        result = await self._middleware_chain.process(
            character_name=character_name,
            beat=beat,
            output=response,
            context=context,
        )

        # Notify middlewares of beat end
        await self._middleware_chain.on_beat_end(character_name, beat, result, context)

        # Return the (possibly modified) output
        return result.modified_output or response

    def _estimate_tension(self, beat: PlotBeat, emotional_state: Dict[str, Any]) -> float:
        """Estimate tension level for a beat."""
        base_tension = {
            BeatType.OPENING.value: 0.1,
            BeatType.DEVELOPMENT.value: 0.3,
            BeatType.CONFLICT.value: 0.6,
            BeatType.CLIMAX.value: 0.9,
            BeatType.RESOLUTION.value: 0.4,
            BeatType.TRANSITION.value: 0.2,
        }.get(beat.beat_type, 0.3)

        # Increase for active conflicts
        if emotional_state.get("conflict_active"):
            base_tension = min(1.0, base_tension + 0.2)

        return base_tension

    async def _update_tension_for_beat(self, beat: PlotBeat) -> None:
        """Update global tension based on beat type."""
        tension_deltas = {
            BeatType.OPENING.value: 0.0,
            BeatType.DEVELOPMENT.value: 0.05,
            BeatType.CONFLICT.value: 0.15,
            BeatType.CLIMAX.value: 0.25,
            BeatType.RESOLUTION.value: -0.1,
            BeatType.TRANSITION.value: -0.05,
        }
        delta = tension_deltas.get(beat.beat_type, 0.0)
        await self.memory_queue.update_global_tension_async(delta)

    def _spawn_character_agents(self, script: DirectorScript) -> None:
        """Spawn character agents for the cast."""
        self._character_agents = {}

        for char_bible in script.cast:
            agent = CharacterAgent(
                name=char_bible.name,
                character_bible=char_bible,
                llm_client=self.llm_client,
                message_queue=self.message_queue,
            )
            agent.reset()  # Ensure clean state
            self._character_agents[char_bible.name] = agent
            logger.debug(f"[Director] Spawned agent for {char_bible.name}")

    def _cleanup_character_agents(self) -> None:
        """Cleanup character agents after scene completion."""
        self._character_agents = {}

    async def handoff_to_character(
        self,
        character_name: str,
        beat: PlotBeat,
        script: DirectorScript,
        previous_outputs: Dict[str, List[str]],
        llm_fn=None,
    ) -> str:
        """Hand off to a character agent for their response.

        Args:
            character_name: Name of character to handoff to
            beat: Current beat being processed
            script: Director script with scene info
            previous_outputs: Dict of char_name -> list of outputs
            llm_fn: Optional LLM function override

        Returns:
            Character's response text
        """
        agent = self._character_agents.get(character_name)
        if not agent:
            # Fallback to direct simulation
            char_bible = script.get_char_bible(character_name)
            if char_bible:
                return await self._simulate_character_response(
                    char_bible=char_bible,
                    beat=beat,
                    script=script,
                    llm_fn=llm_fn or self._default_llm_call,
                )
            return f"[{character_name}的回应]"

        # Build context for the agent, including memory
        memory_context = self.memory_queue.get_context_for_character(
            character_name, include_history=True
        )

        context = {
            "previous_outputs": previous_outputs,
            "scene_info": {
                "location": script.scene.location,
                "time_of_day": script.scene.time_of_day,
            },
            "scene_id": script.scene.scene_id,
            "memory": memory_context,
            "global_tension": self.memory_queue.get_global_tension(),
            "protagonist_constraint": self._protagonist_constraint,
        }

        # Act as the character
        result = await agent.act(beat, context)

        # Send response back (for message queue tracking)
        await agent.send_response(
            scene_id=script.scene.scene_id,
            beat_id=beat.beat_id,
            output=result.get("output", ""),
        )

        return result.get("output", "")

    def assemble_scene_output(
        self,
        script: DirectorScript,
        include_narration: bool = True,
        beat_outputs: Dict[str, Dict[str, str]] = None,
        npc_outputs_by_beat: Dict[str, str] = None,
    ) -> str:
        """Assemble character outputs into coherent scene narration.

        Args:
            script: The director script with scene info
            include_narration: Whether to add scene narration
            beat_outputs: Optional beat outputs dict (if not provided, uses instance variable)
            npc_outputs_by_beat: Optional NPC outputs dict (if not provided, uses instance variable)

        Returns:
            Assembled scene text
        """
        logger.info(f"[Director] Assembling scene: {script.scene.scene_id}")

        # Use provided outputs or fall back to instance variables
        beat_outputs = beat_outputs if beat_outputs is not None else self._beat_outputs
        npc_outputs_by_beat = npc_outputs_by_beat if npc_outputs_by_beat is not None else self._npc_outputs_by_beat

        output_parts = []

        # Add scene header
        if include_narration:
            output_parts.append(f"【场景】{script.scene.location}，{script.scene.time_of_day}")

        # Process beats in order
        for beat in script.scene.beats:
            beat_narration = self._assemble_beat(beat, script, beat_outputs)
            output_parts.append(beat_narration)

            # Include NPC output for this beat if available
            npc_output = npc_outputs_by_beat.get(beat.beat_id)
            if npc_output:
                output_parts.append(npc_output)

        final_output = "\n\n".join(output_parts)
        script.scene.narration = final_output

        # Build raw data for downstream consumers
        script.build_raw_data()

        return final_output

    # ==================== BEAT DECOMPOSITION ====================

    def _decompose_into_beats(
        self,
        scene_outline: str,
        characters: Dict[str, Dict[str, Any]],
        protagonist_constraint: str = "",
        bible_constraint: str = "",
    ) -> List[PlotBeat]:
        """Decompose scene outline into plot beats using BeatType structure.

        Standard beat structure:
        1. OPENING - Set the scene, introduce participants
        2. DEVELOPMENT - Characters interact, situation develops
        3. CONFLICT - Tension rises, disagreement or opposition
        4. CLIMAX - Peak moment of tension or decision
        5. RESOLUTION - Conflict resolved or turned
        6. TRANSITION - Setup for next scene
        """
        # For simplicity, use LLM to decompose if available
        if self.llm_client:
            return self._llm_decompose_beats(scene_outline, characters, protagonist_constraint, bible_constraint)

        # Fallback: simple manual decomposition
        return self._manual_decompose_beats(scene_outline, characters, protagonist_constraint)

    def _llm_decompose_beats(
        self,
        scene_outline: str,
        characters: Dict[str, Dict[str, Any]],
        protagonist_constraint: str = "",
        bible_constraint: str = "",
    ) -> List[PlotBeat]:
        """Use LLM to decompose scene into beats."""
        char_names = list(characters.keys())

        # Build protagonist constraint section
        constraint_section = ""
        if protagonist_constraint:
            constraint_section = f"""
【强制约束】
{protagonist_constraint}

请严格遵循上述约束，所有场景必须以指定主角视角展开。
"""

        # Build bible constraint section
        bible_section = ""
        if bible_constraint:
            bible_section = f"""
【Production Bible 约束】（必须遵守）:
{bible_constraint}
"""

        prompt = f"""将以下场景分解为6个左右的情节节拍（Plot Beats）。
{constraint_section}
{bible_section}
场景概述：
{scene_outline}

出场人物：{', '.join(char_names)}

情节节拍类型说明：
- OPENING: 开场，设置场景，介绍参与者
- DEVELOPMENT: 发展，人物互动，情况展开
- CONFLICT: 冲突，紧张升级，分歧或反对
- CLIMAX: 高潮，紧张或决策的顶峰时刻
- RESOLUTION: 解决，冲突解决或转折
- TRANSITION: 过渡，为下一场景做铺垫

请以JSON格式返回节拍列表：
{{
  "beats": [
    {{
      "beat_type": "OPENING",
      "description": "节拍描述",
      "expected_chars": ["角色1", "角色2"],
      "sequence": 0
    }}
  ]
}}
"""
        try:
            # Wrap prompt in messages format for KimiClient
            messages = [{"role": "user", "content": prompt}]
            if hasattr(self.llm_client, 'generate'):
                response = self.llm_client.generate(messages)
            elif hasattr(self.llm_client, 'chat'):
                response = self.llm_client.chat(prompt)
            else:
                raise ValueError(f"Unknown LLM client type: {type(self.llm_client)}")
            data = json.loads(response)
            beats = []
            for b in data.get("beats", []):
                beat = PlotBeat(
                    beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                    beat_type=b["beat_type"],
                    description=b["description"],
                    expected_chars=b.get("expected_chars", []),
                    sequence=b.get("sequence", 0),
                )
                beats.append(beat)
            return beats
        except Exception as e:
            logger.warning(f"LLM beat decomposition failed: {e}, using manual")
            return self._manual_decompose_beats(scene_outline, characters, protagonist_constraint)

    def _extract_protagonist_from_constraint(
        self, constraint: str, char_names: list
    ) -> Optional[str]:
        """从protagonist_constraint中提取主角名称"""
        if not constraint:
            return char_names[0] if char_names else None
        # 简单实现：查找constraint中出现的角色名
        for name in char_names:
            if name in constraint:
                return name
        return char_names[0] if char_names else None

    def _manual_decompose_beats(
        self,
        scene_outline: str,
        characters: Dict[str, Dict[str, Any]],
        protagonist_constraint: str = "",
    ) -> List[PlotBeat]:
        """Manual fallback beat decomposition."""
        char_names = list(characters.keys())
        protagonist = self._extract_protagonist_from_constraint(
            protagonist_constraint, char_names
        )

        def ensure_protagonist(chars: list) -> list:
            """确保protagonist在角色列表中"""
            if protagonist and protagonist not in chars:
                return [protagonist] + [c for c in chars if c != protagonist]
            return chars

        # Simple 5-beat structure with protagonist guaranteed in each beat
        beats = [
            PlotBeat(
                beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                beat_type=BeatType.OPENING.value,
                description=f"场景开场：{scene_outline[:50]}...",
                expected_chars=ensure_protagonist(char_names[:3]),
                sequence=0,
            ),
            PlotBeat(
                beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                beat_type=BeatType.DEVELOPMENT.value,
                description="情节发展",
                expected_chars=ensure_protagonist(char_names),
                sequence=1,
            ),
            PlotBeat(
                beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                beat_type=BeatType.CONFLICT.value,
                description="冲突升级",
                expected_chars=ensure_protagonist(char_names),
                sequence=2,
            ),
            PlotBeat(
                beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                beat_type=BeatType.CLIMAX.value,
                description="高潮时刻",
                expected_chars=ensure_protagonist(char_names) if char_names else char_names,
                sequence=3,
            ),
            PlotBeat(
                beat_id=f"beat_{uuid.uuid4().hex[:6]}",
                beat_type=BeatType.RESOLUTION.value,
                description="冲突解决",
                expected_chars=ensure_protagonist(char_names[:3]),
                sequence=4,
            ),
        ]
        return beats

    # ==================== CHARACTER BIBLE CREATION ====================

    def _create_character_bibles(
        self,
        characters: Dict[str, Dict[str, Any]],
        beats: List[PlotBeat],
        previous_context: str,
        chapter_number: int,
    ) -> List[CharacterBible]:
        """Create CharacterBible for each main character."""
        bibles = []

        for name, info in characters.items():
            # Determine which beats this character participates in
            key_moments = [
                beat.description
                for beat in beats
                if name in beat.expected_chars
            ][:3]  # Top 3

            bible = CharacterBible(
                name=name,
                role=AgentRole.MAIN_CHARACTER.value,
                identity=info.get("identity", "未知身份"),
                realm=info.get("realm", "炼气期"),
                personality=info.get("personality", "坚毅果敢"),
                speaking_style=info.get("speaking_style", "简洁有力"),
                backstory=info.get("backstory", ""),
                objective_this_chapter=info.get("objective", ""),
                key_moments=key_moments,
                relationships=info.get("relationships", {}),
            )
            bibles.append(bible)

        return bibles

    def _extract_npc_requirements(
        self,
        beats: List[PlotBeat],
        characters: Dict[str, Dict[str, Any]],
    ) -> Dict[str, str]:
        """Extract requirements for NPC simulation."""
        # For now, return empty - NPCs handled by Director
        return {}

    def _identify_tension_points(self, beats: List[PlotBeat]) -> List[str]:
        """Identify key tension points in beats."""
        return [
            beat.description
            for beat in beats
            if beat.beat_type in [BeatType.CONFLICT.value, BeatType.CLIMAX.value]
        ]

    # ==================== CHARACTER SIMULATION ====================

    async def _simulate_character_response(
        self,
        char_bible: CharacterBible,
        beat: PlotBeat,
        script: DirectorScript,
        llm_fn,
    ) -> str:
        """Simulate a character's response to a beat (Director speaks as character)."""
        # Build context for this character
        context = self._build_character_context(char_bible, beat, script)

        beat_type_names = {
            BeatType.OPENING.value: "开场",
            BeatType.DEVELOPMENT.value: "发展",
            BeatType.CONFLICT.value: "冲突",
            BeatType.CLIMAX.value: "高潮",
            BeatType.RESOLUTION.value: "解决",
            BeatType.TRANSITION.value: "过渡",
        }

        prompt = f"""---
type: character_simulation
beat_id: {beat.beat_id}
---

# 角色模拟 | {char_bible.name}

## Character Bible

{char_bible.to_system_prompt()}

## Current Beat

```yaml
beat_type: {beat_type_names.get(beat.beat_type, beat.beat_type)}
description: {beat.description}
expected_chars: [{', '.join(beat.expected_chars)}]
```

## Scene Context

{context}

请以【{char_bible.name}】的视角，回应这个情节。只输出角色对话和动作描写，不输出旁白或其他角色的反应。

### 响应

【{char_bible.name}】
"""
        try:
            response = await llm_fn(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Character simulation failed for {char_bible.name}: {e}")
            return f"（{char_bible.name}的内心活动）"

    async def _simulate_npc_response(
        self,
        beat: PlotBeat,
        script: DirectorScript,
        llm_fn,
        protagonist_constraint: str = "",
    ) -> Optional[str]:
        """Simulate NPC (non-main character) responses.

        Finds characters in the beat that are not in the main cast,
        then generates responses for each via LLM.
        """
        import asyncio

        # Find characters not in the main cast
        all_chars_in_beat = set(beat.expected_chars)
        main_chars = {cb.name for cb in script.cast}
        npc_names = list(all_chars_in_beat - main_chars)

        if not npc_names:
            return None

        # Build NPC prompts
        npc_prompts = []
        for npc_name in npc_names:
            prompt = self._build_npc_prompt(
                npc_name, beat, script,
                protagonist_constraint=self._protagonist_constraint
            )
            npc_prompts.append((npc_name, prompt))

        # Execute NPC simulations concurrently
        try:
            tasks = [llm_fn(prompt) for _, prompt in npc_prompts]
            responses = await asyncio.gather(*tasks, return_exceptions=True)

            npc_outputs = []
            for (npc_name, _), response in zip(npc_prompts, responses):
                if isinstance(response, Exception):
                    logger.warning(f"NPC {npc_name} simulation failed: {response}")
                    continue
                npc_outputs.append(f"【{npc_name}】{response}")

            return "\n".join(npc_outputs) if npc_outputs else None

        except Exception as e:
            logger.error(f"NPC simulation batch failed: {e}")
            return None

    def _build_npc_prompt(
        self,
        npc_name: str,
        beat: PlotBeat,
        script: DirectorScript,
        protagonist_constraint: str = "",
    ) -> str:
        """Build prompt for NPC simulation."""
        beat_type_names = {
            BeatType.OPENING.value: "开场",
            BeatType.DEVELOPMENT.value: "发展",
            BeatType.CONFLICT.value: "冲突",
            BeatType.CLIMAX.value: "高潮",
            BeatType.RESOLUTION.value: "解决",
            BeatType.TRANSITION.value: "过渡",
        }

        # Get NPC identity info if available
        npc_identity = ""
        if hasattr(script, 'non_main_char_requirements') and npc_name in script.non_main_char_requirements:
            npc_identity = script.non_main_char_requirements[npc_name]

        # Get main characters present in this beat (interacting with NPC)
        main_chars_in_beat = [cb.name for cb in script.cast if cb.name in beat.expected_chars]

        # Get previous NPC output for this beat if any
        prev_npc_output = self._npc_outputs_by_beat.get(beat.beat_id, "")

        constraint_section = ""
        if protagonist_constraint:
            constraint_section = f"""
【主角身份约束】
{protagonist_constraint}

【重要】作为NPC，你的言行必须符合上述主角视角设定，不得与主角冲突。
"""

        prev_output_section = ""
        if prev_npc_output:
            prev_output_section = f"""
【当前节拍已有NPC反应】
{prev_npc_output}
"""

        return f"""你是一个扮演{npc_name}的NPC。
{constraint_section}
{prev_output_section}

当前场景：{script.scene.location}
时间段：{script.scene.time_of_day}
当前节拍：{beat_type_names.get(beat.beat_type, beat.beat_type)}
描述：{beat.description}

在场主角：{', '.join(main_chars_in_beat) if main_chars_in_beat else '无'}
NPC身份设定：{npc_identity if npc_identity else '普通路人'}

请以{npc_name}的身份，给出一句符合场景氛围的简短反应或动作。
要求：
- 简洁（不超过50字）
- 符合{npc_name}作为旁观者/背景角色的身份
- 可以是动作、心理描写或简短对话
- 你的言行应该与主角的视角一致

直接输出NPC的反应，不要加任何前缀。"""

    def _build_character_context(
        self,
        char_bible: CharacterBible,
        beat: PlotBeat,
        script: DirectorScript,
    ) -> str:
        """Build context string for a character in YAML format."""
        other_chars = [
            cb.name for cb in script.cast if cb.name != char_bible.name
        ]
        return f"""```yaml
location: {script.scene.location}
time_of_day: {script.scene.time_of_day}
other_chars: [{', '.join(other_chars) if other_chars else '无'}]
beat_description: {beat.description}
```"""

    # ==================== SCENE ASSEMBLY ====================

    def _assemble_beat(
        self,
        beat: PlotBeat,
        script: DirectorScript,
        beat_outputs: Dict[str, Dict[str, str]] = None,
    ) -> str:
        """Assemble a single beat's output."""
        # Use provided outputs or fall back to instance variable
        beat_outputs = beat_outputs if beat_outputs is not None else self._beat_outputs

        parts = []

        # Beat header
        beat_type_names = {
            BeatType.OPENING.value: "开场",
            BeatType.DEVELOPMENT.value: "发展",
            BeatType.CONFLICT.value: "冲突",
            BeatType.CLIMAX.value: "高潮",
            BeatType.RESOLUTION.value: "解决",
            BeatType.TRANSITION.value: "过渡",
        }
        parts.append(f"◆{beat_type_names.get(beat.beat_type, beat.beat_type)}")

        # Get outputs for this beat's characters
        beat_char_outputs = beat_outputs.get(beat.beat_id, {})
        for char_name in beat.expected_chars:
            char_output = beat_char_outputs.get(char_name, "")
            if char_output:
                parts.append(f"【{char_name}】{char_output}")

        return "\n".join(parts)

    # ==================== LLM CALL ====================

    async def _default_llm_call(self, prompt: str) -> str:
        """Default LLM call using self.llm_client."""
        if self.llm_client is None:
            return "[LLM not available]"

        try:
            if hasattr(self.llm_client, "generate"):
                # Wrap prompt in messages format for KimiClient
                messages = [{"role": "user", "content": prompt}]
                return self.llm_client.generate(messages)
            elif hasattr(self.llm_client, "chat"):
                return self.llm_client.chat(prompt)
            else:
                return "[LLM client format not recognized]"
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return f"[Error: {e}]"
