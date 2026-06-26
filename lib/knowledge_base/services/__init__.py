"""Compatibility namespace for legacy services imports."""

from __future__ import annotations

from young_writer._compat import (
    compatibility_exports,
    compatibility_namespace,
    install_alias_prefix,
)

install_alias_prefix(__name__, "young_writer.services")
__path__ = compatibility_namespace("services")
globals().update(compatibility_exports("young_writer.services"))
