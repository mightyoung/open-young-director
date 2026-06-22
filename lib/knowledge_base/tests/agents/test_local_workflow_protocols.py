"""Regression tests for the local workflow protocol layer."""

from young_writer.agents.novel_workflow_orchestrator import (
    NovelPipelineStep,
    NovelWorkflowConfig,
    NovelWorkflowOrchestrator,
)


class _FailingNovelOrchestrator:
    _reality_checker = None

    def orchestrate_chapter(self, **_kwargs):
        return {"status": "FAIL", "issues": ["forced failure"]}


def test_default_workflow_config_constructs_without_external_protocols():
    config = NovelWorkflowConfig()

    assert [step.agent_name for step in config.pipeline_steps] == [
        "novel_orchestrator",
        "novel_orchestrator",
        "reality_checker",
        "assembler",
    ]


def test_local_workflow_stops_on_quality_failure():
    config = NovelWorkflowConfig(
        pipeline_steps=[
            NovelPipelineStep(agent_name="novel_orchestrator", step_type="generate")
        ],
        enable_quality_gate=True,
        stop_on_quality_failure=True,
    )
    workflow = NovelWorkflowOrchestrator(
        novel_orchestrator=_FailingNovelOrchestrator(),
        config=config,
    )

    result = workflow.execute_chapter_pipeline(
        chapter_outline="outline",
        context={"chapter_number": 1},
    )

    assert result.success is False
    assert result.error == "Quality gate failed"


def test_pipeline_dag_zero_interval_marks_end_only_gate():
    config = NovelWorkflowConfig(
        pipeline_steps=[
            NovelPipelineStep(agent_name="planner", step_type="plan"),
            NovelPipelineStep(agent_name="writer", step_type="generate"),
        ],
        enable_quality_gate=True,
        quality_gate_interval=0,
    )
    workflow = NovelWorkflowOrchestrator(
        novel_orchestrator=_FailingNovelOrchestrator(),
        config=config,
    )

    dag = workflow.get_pipeline_dag()

    assert [step["quality_gate"] for step in dag] == [False, True]


def test_pipeline_dag_zero_interval_respects_disabled_quality_gate():
    config = NovelWorkflowConfig(
        pipeline_steps=[
            NovelPipelineStep(agent_name="planner", step_type="plan"),
            NovelPipelineStep(agent_name="writer", step_type="generate"),
        ],
        enable_quality_gate=False,
        quality_gate_interval=0,
    )
    workflow = NovelWorkflowOrchestrator(
        novel_orchestrator=_FailingNovelOrchestrator(),
        config=config,
    )

    dag = workflow.get_pipeline_dag()

    assert [step["quality_gate"] for step in dag] == [False, False]
