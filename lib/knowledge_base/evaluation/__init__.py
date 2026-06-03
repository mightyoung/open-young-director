"""Compatibility namespace for legacy evaluation imports."""

from __future__ import annotations

from young_writer._compat import (
    compatibility_exports,
    compatibility_namespace,
    install_alias_prefix,
)

install_alias_prefix(__name__, "young_writer.evaluation")
__path__ = compatibility_namespace("evaluation")
globals().update(compatibility_exports("young_writer.evaluation"))
