# Shot Decomposition Prompt Template

## Input Variables
- `episode_num`: 集号
- `scene_number`: 场景序号
- `scene`: 场景信息
- `characters`: 角色描述
- `visual_style`: 视觉风格

## Shot Types
| Type | Chinese | Usage |
|------|---------|-------|
| establishing | 建立镜头 | 开场全景，介绍环境 |
| wide | 宽景 | 展示角色与环境关系 |
| medium | 中景 | 常规对话、动作 |
| close_up | 特写 | 强调表情、细节 |
| extreme_close_up | 大特写 | 强烈情绪、关键物品 |
| over_shoulder | 过肩镜头 | 两人对话 |
| two_shot | 双人镜头 | 同时展示两角色 |
| pov | 主观镜头 | 角色视角 |

## Output Format
```json
{
    "shots": [
        {
            "shot_number": 1,
            "scene_number": 1,
            "duration_seconds": 5.0,
            "shot_type": "medium",
            "action": "动作描述",
            "characters": ["角色"],
            "voiceover_segment": "配音词",
            "emotion": "中性"
        }
    ]
}
```

## Duration Guidelines
- Minimum: 3 seconds
- Maximum: 8 seconds
- Recommended: 4-6 seconds
