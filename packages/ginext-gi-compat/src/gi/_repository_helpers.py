# Copyright 2026 Johan Dahlin
#
# SPDX-License-Identifier: LGPL-2.1-or-later

from __future__ import annotations

import os
from typing import Any

import ginext.GIRepository as _GIRepository


_repository: Any | None = None
_loaded: set[tuple[str, str | None]] = set()
_path_state: tuple[str, str] | None = None
_gerror_gtype: int | None = None


def _sync_paths(repo: Any) -> None:
    global _path_state

    state = (
        os.environ.get("GI_TYPELIB_PATH", ""),
        os.environ.get("LD_LIBRARY_PATH", ""),
    )
    if state == _path_state:
        return

    typelib_path, library_path = state
    for entry in reversed([p for p in typelib_path.split(os.pathsep) if p]):
        repo.prepend_search_path(entry)
        repo.prepend_library_path(entry)
    for entry in reversed([p for p in library_path.split(os.pathsep) if p]):
        repo.prepend_library_path(entry)
    _path_state = state


def repository() -> Any:
    global _repository

    if _repository is None:
        _repository = _GIRepository.Repository.dup_default()
    _sync_paths(_repository)
    require("GIRepository", "3.0")
    return _repository


def require(namespace: str, version: str | None) -> None:
    repo = _repository
    if repo is None:
        repo = _GIRepository.Repository.dup_default()
        globals()["_repository"] = repo
    _sync_paths(repo)
    key = (namespace, version)
    if key in _loaded:
        return
    repo.require(namespace, version, 0)
    _loaded.add(key)


def typelib_path(namespace: str, version: str | None = None) -> str | None:
    if version is not None and not repository().is_registered(namespace, version):
        require(namespace, version)
    return repository().get_typelib_path(namespace)


def gerror_gtype() -> int:
    global _gerror_gtype

    if _gerror_gtype is None:
        import ginext

        _, info = ginext.private.namespace_find("GLib", "2.0", "Error")
        _gerror_gtype = int(info.get_g_type())
    return _gerror_gtype
