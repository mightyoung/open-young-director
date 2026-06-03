"""Compatibility namespace for legacy consumers imports."""

from __future__ import annotations

from young_writer._compat import (
    compatibility_exports,
    compatibility_namespace,
    install_alias_prefix,
)

install_alias_prefix(__name__, "young_writer.consumers")
__path__ = compatibility_namespace("consumers")
globals().update(compatibility_exports("young_writer.consumers"))
