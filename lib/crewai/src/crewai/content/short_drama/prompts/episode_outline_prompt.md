# Episode Outline Prompt Template

## Input Variables
- `series_title`: 系列标题
- `episode_num`: 集号
- `episode_context`: 上集剧情承接
- `chapter_text`: 章节原文
- `world_rules`: 世界观设定
- `characters`: 出场角色

## Output Format
```json
{
    "episode_num": 1,
    "title": "集标题",
    "episode_summary": "本集概要",
    "scene_plan": [
        {
            "scene_number": 1,
            "location": "地点",
            "time_of_day": "时间段",
            "description": "场景描述",
            "key_actions": ["动作1", "动作2"],
            "characters": ["角色1", "角色2"],
            "emotion": "情绪基调",
            "duration_estimate": 45
        }
    ]
}
```

## Guidelines
- 每集时长 2-5 分钟
- 场景数 3-6 个
- 开头 30 秒建立冲突
- 高潮在 2-3 分钟处
