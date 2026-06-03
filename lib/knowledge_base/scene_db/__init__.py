"""Compatibility namespace for legacy scene_db imports."""

from __future__ import annotations

from young_writer._compat import (
    compatibility_exports,
    compatibility_namespace,
    install_alias_prefix,
)

install_alias_prefix(__name__, "young_writer.scene_db")
__path__ = compatibility_namespace("scene_db")
globals().update(compatibility_exports("young_writer.scene_db"))
