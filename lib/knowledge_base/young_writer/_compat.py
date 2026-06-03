from __future__ import annotations

from importlib import import_module
from importlib.abc import Loader, MetaPathFinder
from importlib.util import find_spec, spec_from_loader
from pathlib import Path
import sys


_ROOT = Path(__file__).resolve().parent.parent
_YOUNG_WRITER_DIR = Path(__file__).resolve().parent
_ALIAS_PREFIXES: dict[str, str] = {}


class _AliasFinder(MetaPathFinder, Loader):
    def find_spec(self, fullname: str, path=None, target=None):
        del path, target
        for legacy_prefix, canonical_prefix in sorted(
            _ALIAS_PREFIXES.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if fullname != legacy_prefix and not fullname.startswith(f"{legacy_prefix}."):
                continue

            suffix = fullname[len(legacy_prefix) :]
            canonical_name = f"{canonical_prefix}{suffix}"
            canonical_spec = find_spec(canonical_name)
            if canonical_spec is None:
                return None

            is_package = canonical_spec.submodule_search_locations is not None
            spec = spec_from_loader(fullname, self, origin=canonical_spec.origin, is_package=is_package)
            spec.loader_state = {"canonical_name": canonical_name}
            if is_package and canonical_spec.submodule_search_locations is not None:
                spec.submodule_search_locations = list(canonical_spec.submodule_search_locations)
            return spec
        return None

    def create_module(self, spec):
        canonical_name = spec.loader_state["canonical_name"]
        module = import_module(canonical_name)
        sys.modules[spec.name] = module
        return module

    def exec_module(self, module) -> None:
        del module


def install_alias_prefix(legacy_prefix: str, canonical_prefix: str) -> None:
    _ALIAS_PREFIXES[legacy_prefix] = canonical_prefix
    if not any(isinstance(finder, _AliasFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, _AliasFinder())


def compatibility_namespace(relative: str) -> list[str]:
    target = _YOUNG_WRITER_DIR / relative
    return [str(target)] if target.exists() else []


def compatibility_exports(module_name: str) -> dict[str, object]:
    module = import_module(module_name)
    exported = {
        name: getattr(module, name)
        for name in dir(module)
        if not name.startswith("_")
    }
    exported["__all__"] = getattr(
        module,
        "__all__",
        sorted(name for name in exported if not name.startswith("_")),
    )
    return exported
