from __future__ import annotations

import pytest

from ginext.gobject.properties import set_property_via_introspection
from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


def test_pointer_property_rejects_arbitrary_python_objects(regress: Namespace) -> None:
    obj = regress.AnnotationObject()

    with pytest.raises(TypeError, match="gpointer GValue expects None or an integer pointer"):
        set_property_via_introspection(obj, "function-property", ("str1", "str2"))


def test_pointer_backed_glist_property_round_trips_sequence(regress: Namespace) -> None:
    obj = regress.TestSubObj()

    set_property_via_introspection(obj, "list", ("str1", "str2"))

    assert obj.get_property_by_name("list") == ["str1", "str2"]


def test_unichar_property_round_trips_string(regress: Namespace) -> None:
    obj = regress.TestObj()

    assert obj.get_property_by_name("unichar") == ""

    set_property_via_introspection(obj, "unichar", "🙃")

    assert obj.get_property_by_name("unichar") == "🙃"
