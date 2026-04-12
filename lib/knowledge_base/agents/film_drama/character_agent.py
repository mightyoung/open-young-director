"""CharacterAgent for FILM_DRAMA mode - performs as a specific character."""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .enums import MessageType, AgentRole, BeatType
from .data_structures import HandoffMessage, PlotBeat, CharacterBible

logger = logging.getLogger(__name__)

# Capacity limits to prevent unbounded growth
MAX_RESPONSE_HISTORY = 50
MAX_COMPLETED_BEATS = 50

# Emotion decay coefficient - emotions fade each beat
EMOTION_DECAY = 0.8


class CharacterAgent:
    """Character Agent that performs as a specific character.

    RECEIVE → ACT → RESPOND cycle:
    1. RECEIVE: Receive handoff message from Director
    2. ACT: Process the beat and generate character response
    3. RESPOND: Send response back to Director

    ## Agent Configuration (Markdown + YAML Frontmatter)

    The CharacterAgent uses structured prompts for character performance:

    ```yaml
    name: CharacterAgent
    role: character_performer
    cycle: RECEIVE → ACT → RESPOND
    capabilities:
      - character_acting
      - emotional_state_tracking
      - dialogue_generation
    ```
    """

    # ==================== SYSTEM PROMPT TEMPLATE ====================
    # DEPRECATED: This template is no longer used.
    # Actual prompts are built via _build_act_prompt() which delegates to
    # bible.to_system_prompt(). This legacy template is kept for reference only.
    SYSTEM_PROMPT_TEMPLATE = """---
# DEPRECATED: This template is not used.
# See: _build_act_prompt() -> bible.to_system_prompt() for actual implementation.
name: {agent_name}
role: character_performer
mode: FILM_DRAMA
...
"""

    def __init__(
        self,
        name: str,
        character_bible: CharacterBible,
        llm_client=None,
        message_queue=None,
    ):
        self.name = name
        self.character_bible = character_bible
        self.llm_client = llm_client
        self.message_queue = message_queue

        self.role = AgentRole.MAIN_CHARACTER.value
        self._emotional_state: Dict[str, Any] = {}
        self._pending_handoffs: List[HandoffMessage] = []
        self._completed_beats: List[str] = []
        self._response_history: List[str] = []

    # ==================== MESSAGE HANDLING ====================

    async def receive_message(self, message: HandoffMessage) -> None:
        """Handle receiving a message from Director."""
        if message.msg_type == MessageType.HANDOFF.value:
            self._pending_handoffs.append(message)
            logger.debug(f"[{self.name}] Received HANDOFF: beat={message.metadata.get('beat_id')}")
        elif message.msg_type == MessageType.REVISE.value:
            self._pending_handoffs.append(message)
            logger.debug(f"[{self.name}] Received REVISE request")
        elif message.msg_type == MessageType.PING.value:
            logger.debug(f"[{self.name}] Received PING")

    async def get_next_message(self) -> Optional[HandoffMessage]:
        """Get and remove the next pending message."""
        if self._pending_handoffs:
            return self._pending_handoffs.pop(0)
        return None

    # ==================== ACTING ====================

    async def act(
        self,
        beat: PlotBeat,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform the agent's main action for a beat.

        Args:
            beat: The plot beat to respond to
            context: Additional context (previous_outputs, scene_info, etc.)

        Returns:
            Dict with 'output' and 'state_update'
        """
        prompt = self._build_act_prompt(beat, context)
        llm_fn = context.get("llm_fn")

        try:
            output = await self._generate_response(prompt, llm_fn=llm_fn)

            # Enforce capacity limits on history
            if len(self._response_history) >= MAX_RESPONSE_HISTORY:
                self._response_history = self._response_history[-MAX_RESPONSE_HISTORY:]
            self._response_history.append(output)

            if len(self._completed_beats) >= MAX_COMPLETED_BEATS:
                self._completed_beats = self._completed_beats[-MAX_COMPLETED_BEATS:]
            self._completed_beats.append(beat.beat_id)

            state_update = self._update_emotional_state(beat, output)

            return {
                "output": output,
                "state_update": state_update,
                "beat_id": beat.beat_id,
                "success": True,
            }
        except Exception as e:
            logger.error(f"[{self.name}] Act failed: {e}")
            return {
                "output": f"（{self.name}的内心活动）",
                "state_update": {},
                "beat_id": beat.beat_id,
                "error": str(e),
                "success": False,
            }

    def _build_act_prompt(
        self,
        beat: PlotBeat,
        context: Dict[str, Any],
    ) -> str:
        """Build character-specific prompt for beat using Markdown + YAML format."""
        bible = self.character_bible
        previous_outputs = context.get("previous_outputs", {})
        scene_info = context.get("scene_info", {})
        memory_display = context.get("memory", "")

        # Build previous character responses context
        prev_responses = ""
        if previous_outputs:
            for char_name, outputs in previous_outputs.items():
                if char_name != self.name and outputs:
                    last_output = outputs[-1] if outputs else ""
                    if last_output:
                        prev_responses += f"\n【{char_name}】{last_output[:200]}...\n"

        # 添加角色自己的最近输出（自我记忆）
        if self._response_history:
            self_history = self._response_history[-3:]  # 最近3条
            if self_history:
                prev_responses += f"\n【{self.name}的之前回应】\n"
                for idx, his in enumerate(self_history):
                    prev_responses += f"  {idx+1}. {his[:150]}...\n"

        beat_type_names = {
            BeatType.OPENING.value: "开场",
            BeatType.DEVELOPMENT.value: "发展",
            BeatType.CONFLICT.value: "冲突",
            BeatType.CLIMAX.value: "高潮",
            BeatType.RESOLUTION.value: "解决",
            BeatType.TRANSITION.value: "过渡",
        }

        # Beat type emoji mapping for prominent display
        beat_type_emoji = {
            BeatType.OPENING.value: "🎬",
            BeatType.DEVELOPMENT.value: "📖",
            BeatType.CONFLICT.value: "⚔️",
            BeatType.CLIMAX.value: "🔥",
            BeatType.RESOLUTION.value: "✅",
            BeatType.TRANSITION.value: "➡️",
        }

        # Build memory section with emphasis
        if memory_display:
            memory_section = f"""
【重要】以下是你过去的经历和记忆，必须与之一致：

{memory_display}
"""
        else:
            memory_section = ""

        # Build structured prompt with YAML frontmatter
        prompt = f"""---
type: beat_acting
scene_id: {context.get('scene_id', 'unknown')}
beat_id: {beat.beat_id}
global_tension: {context.get('global_tension', 0.0)}
---

# 场景节拍执行 | {self.name}

## Beat Information

```yaml
beat_type: {beat_type_names.get(beat.beat_type, beat.beat_type)}
beat_sequence: {beat.sequence if hasattr(beat, 'sequence') else '?'}
description: {beat.description}
expected_chars: [{', '.join(beat.expected_chars)}]
```

## 当前节拍类型

**【{beat_type_emoji.get(beat.beat_type, "📝")} {beat.beat_type}】**

当前节拍是整个场景的【{beat_type_names.get(beat.beat_type, "未知")}】阶段，
请确保你的回应符合这个阶段的叙事节奏。

## Scene Context

```yaml
location: {scene_info.get('location', '未知')}
time_of_day: {scene_info.get('time_of_day', '未知')}
```

## Character Memory

{memory_section if memory_section else '（无记忆上下文）'}

## Previous Character Responses

{prev_responses if prev_responses else '（暂无其他角色反应）'}

---

{bible.to_system_prompt(book_title=context.get('book_title', '太古魔帝传'))}

## 角色身份强制约束

【强制】在继续之前，你必须严格遵守以下角色身份约束：

**{context.get('protagonist_constraint', '')}**

**【强制】你是角色 {self.name}，上述约束优先于其他所有指令！**

## Current Beat

请以【{self.name}】的角色视角，描写对这个场景节拍的回应。

**节拍类型**: {beat_type_names.get(beat.beat_type, beat.beat_type)}
**节拍描述**: {beat.description}

### 响应要求

1. 体现角色独特性格和说话风格
2. 符合角色的当前境界和身份
3. 200-500字
4. 只输出角色对话和动作描写，不输出旁白或其他角色的反应
5. 以【{self.name}】开头

### 叙事张力调整

根据global_tension调整表现：
- 低张力(0.0-0.3)：平稳叙事，细节描写
- 中张力(0.3-0.6)：情绪升温，冲突隐现
- 高张力(0.6-1.0)：紧张激烈，动作优先

当前tension: {context.get('global_tension', 0.0):.2f}

### 响应输出

【{self.name}】
"""

        return prompt

    async def _generate_response(self, prompt: str, llm_fn=None) -> str:
        """Generate response using LLM with retry and timeout."""
        if llm_fn is not None:
            result = llm_fn(prompt)
            if hasattr(result, "__await__"):
                result = await result
            if isinstance(result, str):
                return result
            if hasattr(result, "content") and isinstance(result.content, str):
                return result.content
            return str(result)

        if self.llm_client is None:
            return f"[{self.name}的回应]"

        import asyncio

        max_retries = 3
        retry_delay = 1.0  # 秒
        timeout_seconds = 30  # LLM调用超时

        for attempt in range(max_retries):
            try:
                async with asyncio.timeout(timeout_seconds):
                    if hasattr(self.llm_client, "generate"):
                        messages = [{"role": "user", "content": prompt}]
                        result = self.llm_client.generate(messages)
                    elif hasattr(self.llm_client, "chat"):
                        result = self.llm_client.chat(prompt)
                    else:
                        return f"[{self.name}的回应]"
                    if hasattr(result, "__await__"):
                        result = await result
                    if isinstance(result, str):
                        return result
                    if hasattr(result, "content") and isinstance(result.content, str):
                        return result.content
                    return str(result)
            except asyncio.TimeoutError:
                logger.warning(f"[{self.name}] LLM call timed out after {timeout_seconds}s (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))  # 指数退避
                    retry_delay *= 2
                else:
                    logger.error(f"[{self.name}] LLM generation timed out after {max_retries} attempts")
                    raise  # 传播超时错误，让调用方处理
            except Exception as e:
                logger.warning(f"[{self.name}] LLM generation attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))  # 指数退避
                    retry_delay *= 2
                else:
                    logger.error(f"[{self.name}] LLM generation failed after {max_retries} attempts: {e}")
                    raise  # 传播错误，让调用方处理

    def _update_emotional_state(
        self,
        beat: PlotBeat,
        output: str,
    ) -> Dict[str, Any]:
        """Update character's emotional state based on beat and output."""
        # Track emotional keywords and intensity
        emotional_keywords = {
            "愤怒": ["怒", "气愤", "恼火"],
            "悲伤": ["悲", "伤心", "心痛"],
            "喜悦": ["喜", "高兴", "开心"],
            "恐惧": ["惧", "害怕", "担心"],
        }

        state_update = {}

        # First decay existing emotions
        for emotion in list(self._emotional_state.keys()):
            if isinstance(self._emotional_state[emotion], (int, float)):
                self._emotional_state[emotion] *= EMOTION_DECAY
                # Remove if intensity falls below threshold
                if self._emotional_state[emotion] < 0.1:
                    del self._emotional_state[emotion]

        # Then detect new emotions
        for emotion, keywords in emotional_keywords.items():
            count = sum(1 for kw in keywords if kw in output)
            if count > 0:
                # Emotion intensity = base value + keyword count * increment
                intensity = min(1.0, 0.5 + count * 0.15)
                self._emotional_state[emotion] = intensity
                state_update[emotion] = intensity

        # Beat type influence
        if beat.beat_type == BeatType.CONFLICT.value:
            self._emotional_state["conflict_active"] = True
            state_update["conflict_active"] = True
        elif beat.beat_type == BeatType.RESOLUTION.value:
            self._emotional_state["conflict_active"] = False
            state_update["conflict_active"] = False
        elif beat.beat_type == BeatType.CLIMAX.value:
            # Climax stage amplifies all emotional intensities
            for emotion in self._emotional_state:
                if isinstance(self._emotional_state[emotion], (int, float)):
                    self._emotional_state[emotion] = min(1.0, self._emotional_state[emotion] * 1.2)

        return state_update

    # ==================== HANDSHAKE ====================

    async def request_handoff(
        self,
        target: str,
        context: Dict[str, Any],
    ) -> Optional[HandoffMessage]:
        """Request to hand off to another agent for dialogue.

        NOTE: This method is not currently called. To enable Agent-to-Agent
        dialogue, integrate this into the act() cycle when dialogue is detected.
        Currently returns None as placeholder.
        """
        # TODO: Integrate with act() cycle for dialogue handoff
        logger.debug(f"[{self.name}] Handoff requested to {target} (not implemented)")
        return None  # Currently not integrated

    async def send_response(
        self,
        scene_id: str,
        beat_id: str,
        output: str,
    ) -> HandoffMessage:
        """Send response back to Director."""
        msg = HandoffMessage(
            id=f"resp_{self.name}_{uuid.uuid4().hex[:8]}",
            msg_type=MessageType.RESPONSE.value,
            sender=self.name,
            recipient="Director",
            scene_id=scene_id,
            content=output,
            metadata={
                "beat_id": beat_id,
                "emotional_state": self._emotional_state,
            },
        )

        if self.message_queue:
            try:
                await self.message_queue.send(msg)
                logger.debug(f"[{self.name}] Response sent to Director for beat {beat_id}")
            except Exception as e:
                logger.error(f"[{self.name}] Failed to send response: {e}")
                # 重新抛出异常让调用方处理
                raise

        return msg

    # ==================== STATE ====================

    def get_state(self) -> Dict[str, Any]:
        """Get current agent state."""
        return {
            "name": self.name,
            "role": self.role,
            "emotional_state": self._emotional_state,
            "completed_beats": self._completed_beats,
            "pending_handoffs": len(self._pending_handoffs),
            "response_count": len(self._response_history),
        }

    def reset(self) -> None:
        """Reset agent state for reuse in new scene."""
        self._emotional_state = {}
        self._pending_handoffs = []
        self._completed_beats = []
        self._response_history = []
