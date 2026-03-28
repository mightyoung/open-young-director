---
name: quality_check
version: 1.0.0
description: 对生成内容进行质量评估和门禁检查
inputs:
  - content
  - consumer_type
  - context
outputs:
  decision: GateDecision
  issues: List[str]
---

# Skill: quality_check

对生成内容进行质量评估和门禁检查。

## Overview

quality_check 技能是内容生成系统的质量门禁。它负责验证生成内容是否满足质量标准，包括角色一致性、情节连贯性、情感弧线匹配等。

## When to Use

- 内容生成后需要进行质量验证
- 需要检查角色行为一致性
- 需要验证情节连贯性
- 触发短语：`质量检查`、`内容审核`、`验证质量`

---

## Metadata

| Field | Value |
|-------|-------|
| name | quality_check |
| version | 1.0.0 |

---

## Inputs

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| content | str | Yes | 待验证的内容 |
| consumer_type | str | Yes | 内容类型（novel, video, podcast, music） |
| context | dict | Yes | 上下文信息 |

---

## Outputs

```python
{
    "decision": GateDecision,  # PASS | NEEDS_WORK | REJECT
    "score": float,           # 质量分数 0-1
    "issues": List[str],      # 发现的问题列表
    "evidence_required": List[str],  # 需要的额外验证
    "details": {
        "character_consistency": bool,
        "plot_coherence": bool,
        "emotional_arc_match": bool
    }
}
```

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| pass_threshold | 0.8 | 通过阈值 |
| strict_mode | true | 严格模式（需要更多证据） |

---

## Integration

### 与 Orchestra 集成

quality_check 技能由 `RealityChecker` 提供：

```python
from agents.reality_checker import RealityChecker, RealityCheckerConfig

config = RealityCheckerConfig()
checker = RealityChecker(llm_client=llm_client, config=config)

# 验证内容
result = checker.validate_content(content, criteria)

# 便捷方法
validation = orchestrator.validate_chapter(chapter_content, context)
```

---

## Validation Criteria

### 角色一致性

检查项：
- 角色行为是否符合其设定
- 对话语气是否一致
- 情绪变化是否合理

### 情节连贯性

检查项：
- 与前文是否连贯
- 情节发展是否逻辑清晰
- 伏笔是否正确回收

### 情感弧线匹配

检查项：
- 情感变化是否符合弧线设定
- 高潮和低谷是否恰当
- 结局是否满足情感期待

---

## Usage Example

```python
# 直接使用 RealityChecker
result = checker.validate_content(content, {
    "characters": character_profiles,
    "previous_summary": prev_summary,
    "required_elements": ["打斗", "情感"],
    "prohibited_elements": ["穿越"]
})

print(f"Decision: {result.status}")
print(f"Score: {result.score:.2f}")
for issue in result.issues:
    print(f"Issue: {issue}")
```

---

## Tips

1. **默认 NEEDS_WORK**：默认状态为需要改进，需要充分证据才能通过
2. **多维度验证**：建议同时检查多个维度
3. **证据要求**：对于复杂内容，需要提供更多证据
4. **可配置阈值**：根据项目需求调整通过阈值
