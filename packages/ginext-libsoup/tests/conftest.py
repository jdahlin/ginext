from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _require_soup() -> None:
    # These tests need the Soup 3.0 typelib (gir1.2-soup-3.0). Skip gracefully
    # where it is absent (e.g. a CI image without it) instead of erroring, so the
    # suite stays portable in the unified run.
    import ginext

    try:
        ginext.private.require_namespace("Soup", "3.0")
    except ImportError:
        pytest.skip("Soup 3.0 typelib not available")


@pytest.fixture(scope="session")
def aio():
    from ginext import aio

    return aio


@pytest.fixture(scope="session")
def Soup():
    import ginext

    ginext.private.require_namespace("Soup", "3.0")
    from ginext import Soup

    return Soup
