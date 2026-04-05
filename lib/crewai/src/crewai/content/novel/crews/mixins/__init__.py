"""NovelCrew mixins package.

Provides focused mixins for NovelCrew decomposition:
- crew_properties: Lazy-loading crew/agent properties
- pipeline_management: Pipeline state init/load/save

More mixins will be added in future refactoring phases.
"""

from crewai.content.novel.crews.mixins.crew_properties import CrewPropertiesMixin
from crewai.content.novel.crews.mixins.pipeline_management import PipelineManagementMixin

__all__ = ["CrewPropertiesMixin", "PipelineManagementMixin"]
