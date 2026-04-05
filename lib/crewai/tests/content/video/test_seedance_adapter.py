"""Tests for Seedance 2.0 Video Prompt Adapter."""

import pytest

from crewai.content.video import (
    Seedance2PromptAdapter,
    FramePrompt,
    TimelineSegment,
    CharacterSpec,
    SceneSpec,
    create_character_spec,
    create_scene_spec,
)


class TestSeedance2PromptAdapter:
    """Tests for Seedance2PromptAdapter."""

    def test_generate_prompt_basic(self):
        """Test basic prompt generation."""
        adapter = Seedance2PromptAdapter()
        char = CharacterSpec(name="韩林", age_appearance="少年", clothing="白袍")

        prompt = adapter.generate_prompt(
            scene_description="韩林立于演武场边缘，清晨薄雾中抬眸望向测灵台",
            characters=[char],
            shot_type="establishing"
        )

        assert "absolute_subject_motion" in prompt
        assert "environment_light_mood" in prompt
        assert "optical_camera" in prompt
        assert "timeline_evolution" in prompt
        assert "aesthetic_rendering" in prompt

        # Check subject motion contains character info
        assert "韩林" in prompt["absolute_subject_motion"]
        assert "白袍" in prompt["absolute_subject_motion"]

    def test_generate_prompt_with_emotion(self):
        """Test prompt generation with emotion."""
        adapter = Seedance2PromptAdapter()
        char = CharacterSpec(
            name="韩林",
            expression_range={"default": "平静", "angry": "眉头紧锁"}
        )

        prompt = adapter.generate_prompt(
            scene_description="韩林看到测试结果",
            characters=[char],
            emotion="angry"
        )

        assert "眉头紧锁" in prompt["absolute_subject_motion"]

    def test_to_seedance_prompt(self):
        """Test converting prompt dict to Seedance format."""
        adapter = Seedance2PromptAdapter()
        char = CharacterSpec(name="韩林", clothing="白袍")

        prompt = adapter.generate_prompt(
            scene_description="韩林立于演武场边缘",
            characters=[char],
            shot_type="medium"
        )

        output = adapter.to_seedance_prompt(prompt)

        # Check format sections
        assert "【绝对主体与物理动势】" in output
        assert "【环境场与情绪光影】" in output
        assert "【光学与摄影机调度】" in output
        assert "【时间轴与状态演变】" in output
        assert "【美学介质与底层渲染参数】" in output
        assert "【负面提示词】" in output

        # Check negative prompt is included
        assert "CGI, 3D render" in output

    def test_generate_from_template(self):
        """Test generating from predefined template."""
        adapter = Seedance2PromptAdapter()

        prompt = adapter.generate_from_template("对峙沉默")

        assert "absolute_subject_motion" in prompt
        assert "environment_light_mood" in prompt
        # Template contains "二人相隔数步无言对视"
        assert "二人相隔数步无言对视" in prompt["absolute_subject_motion"]

    def test_generate_frame_prompts(self):
        """Test generating frame-level prompts."""
        adapter = Seedance2PromptAdapter()
        char = CharacterSpec(name="韩林")

        frame_sequence = [
            {"frame_type": "start_frame", "time": "0-3s", "description": "韩林抬头"},
            {"frame_type": "key_frame", "time": "3-5s", "description": "眼神坚定"},
        ]

        frames = adapter.generate_frame_prompts(
            frame_sequence=frame_sequence,
            characters=[char]
        )

        assert len(frames) == 2
        assert frames[0].frame_type == "start_frame"
        assert frames[0].time_range == "0-3s"
        assert "韩林" in frames[0].prompt_text

    def test_shot_type_mapping(self):
        """Test shot type to Chinese mapping."""
        adapter = Seedance2PromptAdapter()

        prompt = adapter.generate_prompt(
            scene_description="测试场景",
            shot_type="establishing"
        )

        assert "航拍全景" in prompt["optical_camera"]

        prompt = adapter.generate_prompt(
            scene_description="测试场景",
            shot_type="close_up"
        )

        assert "特写" in prompt["optical_camera"]

    def test_lens_focal_length_mapping(self):
        """Test lens focal length recommendations."""
        adapter = Seedance2PromptAdapter()

        # 85mm for portrait
        prompt = adapter.generate_prompt(
            scene_description="测试场景",
            shot_type="portrait"
        )

        assert "85mm" in prompt["optical_camera"]

    def test_default_style(self):
        """Test default style is applied."""
        adapter = Seedance2PromptAdapter(default_style="水墨风格")

        prompt = adapter.generate_prompt(scene_description="测试")

        assert "水墨风格" in prompt["aesthetic_rendering"]


class TestCharacterSpec:
    """Tests for CharacterSpec."""

    def test_to_subject_description(self):
        """Test converting to subject description."""
        char = CharacterSpec(
            name="韩林",
            age_appearance="十六岁",
            clothing="白袍",
            hair="黑发",
            expression_range={"default": "平静"}
        )

        desc = char.to_subject_description()
        # Default expression is included when no emotion specified
        assert desc == "韩林，十六岁，白袍，黑发，平静"

    def test_to_subject_description_with_emotion(self):
        """Test with emotion override."""
        char = CharacterSpec(
            name="韩林",
            expression_range={"default": "平静", "angry": "眉头紧锁"}
        )

        desc = char.to_subject_description(emotion="angry")
        assert "眉头紧锁" in desc


class TestSceneSpec:
    """Tests for SceneSpec."""

    def test_to_environment_description(self):
        """Test converting to environment description."""
        scene = SceneSpec(
            name="太虚宗演武场",
            location_type="宗门演武场",
            architecture="古朴石制",
            color_palette="青灰色调",
            lighting={"morning": "金色晨光"}
        )

        desc = scene.to_environment_description("morning")
        assert "太虚宗演武场" in desc
        assert "金色晨光" in desc


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_character_spec(self):
        """Test create_character_spec factory."""
        char = create_character_spec(
            name="韩林",
            age_appearance="少年",
            clothing="白袍"
        )

        assert isinstance(char, CharacterSpec)
        assert char.name == "韩林"
        assert char.age_appearance == "少年"
        assert char.clothing == "白袍"

    def test_create_scene_spec(self):
        """Test create_scene_spec factory."""
        scene = create_scene_spec(
            name="演武场",
            location_type="宗门",
            atmosphere="庄严肃穆"
        )

        assert isinstance(scene, SceneSpec)
        assert scene.name == "演武场"
        assert scene.atmosphere == "庄严肃穆"
