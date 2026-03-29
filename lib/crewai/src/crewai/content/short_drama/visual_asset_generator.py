"""VisualAssetGenerator - 角色和场景视觉Prompt自动生成器

自动从小说内容中提取角色和场景，生成可用于AI绘图的视觉Prompt。

Usage:
    generator = VisualAssetGenerator(novel_project_path)
    
    # 从小说内容提取并生成
    generator.generate_from_novel(novel_text)
    
    # 或手动添加
    generator.add_character(name="林逸", age="15岁", ...)
    generator.add_scene(name="矿山宿舍", time_of_day="黎明")
    
    # 保存
    generator.save_to_assets_dir()
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import json

__all__ = ["VisualAssetGenerator", "CharacterVisualPrompt", "SceneVisualPrompt"]


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class CharacterVisualPrompt:
    """角色视觉Prompt"""
    character_id: str
    character_name: str
    age: str
    identity: str
    cultivation_realm: str
    full_body_prompt: str
    face_closeup_prompt: str
    variants: dict = field(default_factory=dict)
    status: str = "pending"


@dataclass
class SceneVisualPrompt:
    """场景视觉Prompt"""
    scene_id: str
    scene_name: str
    time_of_day: str
    lighting: str
    full_scene_prompt: str
    detail_prompts: dict = field(default_factory=dict)
    status: str = "pending"


@dataclass
class VisualAssetManifest:
    """视觉资产清单"""
    project_name: str
    characters: list = field(default_factory=list)
    scenes: list = field(default_factory=list)


# ============================================================================
# Prompt Templates
# ============================================================================

CHARACTER_BODY_TEMPLATE = """【技术参数】9:16竖屏，8K超清，电影级画质
【风格】高度写实风格，仙侠古风
【绝对主体】{name}，{age}，{appearance}
【服装】{clothing}
【道具】{props}
【发型】{hairstyle}
【面部】{face_features}
【姿态】{pose}
【情绪状态】{emotion}
【光影】{lighting}
【负面提示词】anime, cartoon, CGI, fantasy creature, dirty, ugly, deformed"""


CHARACTER_FACE_TEMPLATE = """【技术参数】1:1方形，8K超清，电影级画质
【风格】高度写实风格
【绝对主体】{name}面部特写，{age}
【面部细节】{face_details}
【皮肤状态】{skin_condition}
【光影】{lighting_style}
【情绪】{emotion}
【负面提示词】anime, cartoon, CGI, smooth skin, perfect complexion"""


SCENE_TEMPLATE = """【技术参数】9:16竖屏，8K超清，电影级画质
【风格】高度写实风格
【绝对主体】{scene_name}
【场景描述】{description}
【空间布局】
{space_layout}
【道具陈设】
{items}
【环境细节】
{env_details}
【光线设计】
{lighting}
【氛围】{atmosphere}
【时间线索】{time_hint}
【负面提示词】{negative}"""


# ============================================================================
# VisualAssetGenerator
# ============================================================================


class VisualAssetGenerator:
    """角色和场景视觉Prompt生成器"""

    def __init__(self, project_path: str | Path):
        self.project_path = Path(project_path)
        self.manifest = VisualAssetManifest(project_name=self.project_path.name)
        self._char_counter = 0
        self._scene_counter = 0

    def add_character(
        self,
        name: str,
        age: str,
        appearance: str,
        clothing: str,
        identity: str,
        cultivation_realm: str = "凡人",
        pose: str = "站姿挺拔",
        emotion: str = "坚毅",
        lighting: str = "侧光",
        face_features: str = "",
        hairstyle: str = "黑色短发",
        props: str = "无",
        face_details: str = "",
        skin_condition: str = "微黄略显营养不良",
        lighting_style: str = "伦勃朗光，左侧45度主光",
    ) -> CharacterVisualPrompt:
        """添加角色"""
        self._char_counter += 1
        char_id = f"C{self._char_counter:02d}"

        full_body = CHARACTER_BODY_TEMPLATE.format(
            name=name,
            age=age,
            appearance=appearance,
            clothing=clothing,
            props=props,
            hairstyle=hairstyle,
            face_features=face_features,
            pose=pose,
            emotion=emotion,
            lighting=lighting,
        )

        face_closeup = CHARACTER_FACE_TEMPLATE.format(
            name=name,
            age=age,
            face_details=face_details,
            skin_condition=skin_condition,
            lighting_style=lighting_style,
            emotion=emotion,
        )

        char = CharacterVisualPrompt(
            character_id=char_id,
            character_name=name,
            age=age,
            identity=identity,
            cultivation_realm=cultivation_realm,
            full_body_prompt=full_body,
            face_closeup_prompt=face_closeup,
        )
        self.manifest.characters.append(char)
        return char

    def add_scene(
        self,
        name: str,
        time_of_day: str,
        description: str,
        lighting: str,
        space_layout: str,
        items: str,
        env_details: str,
        atmosphere: str,
        time_hint: str,
        negative: str = "anime, cartoon, CGI, modern, bright",
    ) -> SceneVisualPrompt:
        """添加场景"""
        self._scene_counter += 1
        scene_id = f"S{self._scene_counter:02d}"

        full_scene = SCENE_TEMPLATE.format(
            scene_name=name,
            description=description,
            space_layout=space_layout,
            items=items,
            env_details=env_details,
            lighting=lighting,
            atmosphere=atmosphere,
            time_hint=time_hint,
            negative=negative,
        )

        scene = SceneVisualPrompt(
            scene_id=scene_id,
            scene_name=name,
            time_of_day=time_of_day,
            lighting=lighting,
            full_scene_prompt=full_scene,
        )
        self.manifest.scenes.append(scene)
        return scene

    def generate_from_novel(self, novel_text: str) -> None:
        """从小说文本自动提取并生成Prompt"""
        # 简单的关键词匹配逻辑
        # 实际使用时可以让LLM来提取

        lines = novel_text.split("\n")

        # 提取角色（简单规则）
        for line in lines:
            if "林逸" in line and "：" in line:
                self.add_character(
                    name="林逸",
                    age="15岁",
                    appearance="身材瘦削但结实，眉目清秀，眼神中带着超越年龄的坚毅",
                    clothing="粗布麻衣，深灰色，衣角有补丁，袖口磨损",
                    identity="矿山童工",
                    cultivation_realm="未入门（凡人）",
                    pose="站姿挺拔，虽衣着破旧但不卑不亢",
                    emotion="坚毅、沉默、隐忍",
                    lighting="侧光，面部1/3明暗对比",
                    face_features="眉宇间有一股不屈之气",
                    hairstyle="黑色短发，略显凌乱，额前碎发",
                    props="破旧草鞋，背一个旧布包",
                    face_details="眉毛浓密微皱；眼睛有神，眼角略有细纹；鼻梁挺直",
                    skin_condition="微黄略显营养不良",
                )

            if "孙伯" in line and "老者" in line.lower():
                self.add_character(
                    name="孙伯",
                    age="70岁",
                    appearance="白发苍苍，面容慈祥中带着沧桑",
                    clothing="深色粗布棉袍，颜色褪旧但干净，袖口有缝补",
                    identity="退休矿工",
                    cultivation_realm="凡人",
                    pose="佝偻站立，拄拐杖姿势稳健",
                    emotion="慈祥、关切",
                    lighting="正面柔光，展现慈祥面容",
                    face_features="皱纹密布，眼窝深陷但眼神温和",
                    hairstyle="白发苍苍，盘髻用木簪固定",
                    props="木质拐杖，雕刻古朴，包浆厚实",
                    face_details="额头深深的抬头纹；眼角皱纹呈放射状",
                    skin_condition="古铜色肌肤，布满岁月痕迹",
                )

            if "赵铁柱" in line:
                self.add_character(
                    name="赵铁柱",
                    age="40岁",
                    appearance="身材魁梧健壮，络腮胡子黝黑",
                    clothing="深色粗布短褂，袖子卷至肘部",
                    identity="矿工",
                    cultivation_realm="凡人",
                    pose="双手抱臂，或叉腰站立",
                    emotion="严肃、警惕",
                    lighting="顶光，在疤痕处形成阴影",
                    face_features="国字脸，颧骨高耸；左侧眼角有疤痕",
                    hairstyle="短发，络腮胡子浓密",
                    props="无",
                    face_details="眉毛浓密；眼睛有神但略显疲惫；鼻翼宽大",
                    skin_condition="古铜色肌肤",
                )

        # 提取场景
        if "宿舍" in novel_text or "矿区" in novel_text:
            self.add_scene(
                name="矿山宿舍",
                time_of_day="黎明",
                description="简陋矿工宿舍内部，昏暗压抑",
                lighting="主光源：油灯（暖黄色），辅光源：窗户透光（冷蓝色）",
                space_layout="狭小空间，约10平米；土坯墙，墙面斑驳脱落；屋顶为木质横梁+茅草",
                items="土炕铺旧草席；木凳缺腿用砖垫起；角落木箱；墙上挂油灯",
                env_details="墙角有蜘蛛网；墙面有汗渍水痕；窗户木框糊纸",
                atmosphere="阴暗、潮湿、压抑、贫困",
                time_hint="黎明，窗外天色微明但室内仍昏暗",
            )

        if "街道" in novel_text or "清晨" in novel_text:
            self.add_scene(
                name="临渊镇街道",
                time_of_day="清晨",
                description="偏僻山乡小镇清晨街道，晨雾缭绕",
                lighting="主光源：晨曦天光（冷蓝色）；辅光源：民居窗户透出暖黄灯光",
                space_layout="青石板路，宽约3米；两旁为低矮民居，土坯墙，黑瓦屋顶；远处天荡山脉",
                items="民居门扉陈旧贴褪色春联；墙角堆放柴火；远处烟囱冒炊烟",
                env_details="薄雾笼罩；地面微湿有露水；空气清冷可见呼吸白雾",
                atmosphere="宁静、古朴、清冷、略带神秘",
                time_hint="清晨太阳初升，雾气未散",
            )

        if "矿山入口" in novel_text or "洞口" in novel_text:
            self.add_scene(
                name="矿山入口",
                time_of_day="清晨",
                description="矿山入口广场，人群聚集",
                lighting="主光源：晨曦天光从洞口内侧照射；形成强烈明暗对比",
                space_layout="半圆形矿洞洞口，宽约5米；木支架支撑；洞口上方岩石刻'临渊矿'",
                items="入口两侧火把架；广场边缘登记棚屋；矿车轨道延伸入洞",
                env_details="碎石地面，面积约200平米；三面环山，晨雾缭绕",
                atmosphere="压抑、紧张、等级分明",
                time_hint="清晨，雾气从洞口向外飘散",
            )

    def save_to_assets_dir(self, assets_dir: Optional[Path] = None) -> Path:
        """保存到assets目录"""
        if assets_dir is None:
            assets_dir = self.project_path / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # 保存角色Prompt
        char_file = assets_dir / "角色视觉Prompt.md"
        self._save_character_prompts(char_file)

        # 保存场景Prompt
        scene_file = assets_dir / "场景视觉Prompt.md"
        self._save_scene_prompts(scene_file)

        # 保存manifest JSON
        manifest_file = assets_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(), f, ensure_ascii=False, indent=2)

        return assets_dir

    def _save_character_prompts(self, path: Path) -> None:
        lines = [f"# {self.manifest.project_name} 角色视觉Prompt\n"]
        lines.append(f"\n## 角色资产目录\n")
        lines.append("| ID | 名称 | 状态 | 用途 |\n")
        lines.append("|----|------|------|------|\n")
        for c in self.manifest.characters:
            lines.append(f"| {c.character_id} | {c.character_name} | {c.status} | {c.identity} |\n")

        for c in self.manifest.characters:
            lines.append(f"\n## {c.character_id} {c.character_name}\n")
            lines.append(f"\n### 全身Prompt\n")
            lines.append(f"```\n{c.full_body_prompt}\n```\n")
            lines.append(f"\n### 面部特写Prompt\n")
            lines.append(f"```\n{c.face_closeup_prompt}\n```\n")

        path.write_text("".join(lines), encoding="utf-8")

    def _save_scene_prompts(self, path: Path) -> None:
        lines = [f"# {self.manifest.project_name} 场景视觉Prompt\n"]
        lines.append(f"\n## 场景资产目录\n")
        lines.append("| ID | 名称 | 状态 | 时段 |\n")
        lines.append("|----|------|------|------|\n")
        for s in self.manifest.scenes:
            lines.append(f"| {s.scene_id} | {s.scene_name} | {s.status} | {s.time_of_day} |\n")

        for s in self.manifest.scenes:
            lines.append(f"\n## {s.scene_id} {s.scene_name}（{s.time_of_day}）\n")
            lines.append(f"\n### 场景Prompt\n")
            lines.append(f"```\n{s.full_scene_prompt}\n```\n")

        path.write_text("".join(lines), encoding="utf-8")

    def _to_dict(self) -> dict:
        return {
            "project_name": self.manifest.project_name,
            "characters": [
                {
                    "id": c.character_id,
                    "name": c.character_name,
                    "age": c.age,
                    "identity": c.identity,
                    "status": c.status,
                }
                for c in self.manifest.characters
            ],
            "scenes": [
                {
                    "id": s.scene_id,
                    "name": s.scene_name,
                    "time_of_day": s.time_of_day,
                    "status": s.status,
                }
                for s in self.manifest.scenes
            ],
        }
