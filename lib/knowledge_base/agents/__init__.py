"""Compatibility namespace for legacy agents imports."""

from __future__ import annotations

from importlib import import_module as _import_module
import sys

from young_writer._compat import (
    compatibility_exports,
    compatibility_namespace,
    install_alias_prefix,
)

install_alias_prefix(__name__, "young_writer.agents")
__path__ = compatibility_namespace("agents")
globals().update(compatibility_exports("young_writer.agents"))

for _SUBMODULE in ("config_manager", "longform_memory"):
    _MODULE = _import_module(f"young_writer.agents.{_SUBMODULE}")
    sys.modules[f"{__name__}.{_SUBMODULE}"] = _MODULE
    globals()[_SUBMODULE] = _MODULE
