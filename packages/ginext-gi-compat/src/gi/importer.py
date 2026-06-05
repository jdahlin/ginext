from __future__ import annotations

import importlib
import importlib.util
import sys
from contextlib import contextmanager
from typing import Any, cast


@contextmanager
def _check_require_version(namespace: str, stacklevel: int):
    yield


def get_import_stacklevel(import_hook: bool) -> int:
    return 4 if import_hook else 2


class DynamicImporter:
    def __init__(self, path: str):
        self.path = path

    def _handles(self, fullname: str) -> bool:
        if not fullname.startswith(self.path):
            return False
        path, _, namespace = fullname.rpartition(".")
        return path == self.path and bool(namespace)

    def find_spec(self, fullname: str, path=None, target=None):
        if self._handles(fullname):
            return importlib.util.spec_from_loader(fullname, cast("Any", self))
        return None

    def find_module(self, fullname: str, path=None):
        if self._handles(fullname):
            return self
        return None

    def create_module(self, spec):
        from gi import repository as gi_repository

        _path, namespace = spec.name.rsplit(".", 1)
        stacklevel = get_import_stacklevel(import_hook=True)
        with _check_require_version(namespace, stacklevel=stacklevel):
            try:
                return getattr(gi_repository, namespace)
            except AttributeError:
                # A namespace whose typelib is unavailable (e.g. GdkX11 on a
                # non-X11 platform) must surface as ImportError to match
                # PyGObject, so `from gi.repository import X` can be guarded
                # with `except ImportError`.
                raise ImportError(
                    f"cannot import name {namespace!r} from 'gi.repository'"
                ) from None

    def exec_module(self, module):
        return None


importer = DynamicImporter("gi.repository")
if not any(
    type(existing) is DynamicImporter and existing.path == "gi.repository"
    for existing in sys.meta_path
):
    sys.meta_path.insert(0, importer)
