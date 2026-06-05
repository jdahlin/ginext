from __future__ import annotations

import pathlib

from conftest_shared import setup_gi_test_env, setup_split_package_test_env

_ROOT = pathlib.Path(__file__).resolve().parents[2]

setup_split_package_test_env(_ROOT, include_ginext_tests=True)
setup_gi_test_env(_ROOT)


def _configure_compat_defaults() -> None:
    import ginext

    ginext.features.set_enabled("pygobject_compat", True)
    for namespace in (
        "GIMarshallingTests",
        "Regress",
        "RegressUnix",
        "Utility",
    ):
        ginext.defaults.require(namespace, "1.0")


_configure_compat_defaults()
