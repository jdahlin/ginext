from __future__ import annotations

import pytest

from ginext.namespace import Namespace
from ginext.tests.gi_test_utils import load_test_namespace


@pytest.fixture(scope="module")
def regress() -> Namespace:
    return load_test_namespace("Regress")


def test_pointer_property_rejects_arbitrary_python_objects(regress: Namespace) -> None:
    obj = regress.AnnotationObject()

    with pytest.raises(TypeError, match="gpointer GValue expects None or an integer pointer"):
        obj.set_property_by_name("function-property", ("str1", "str2"))


def test_pointer_backed_glist_property_round_trips_sequence(regress: Namespace) -> None:
    obj = regress.TestSubObj()

    obj.set_property_by_name("list", ("str1", "str2"))

    assert obj.get_property_by_name("list") == ["str1", "str2"]


def test_unichar_property_round_trips_string(regress: Namespace) -> None:
    obj = regress.TestObj()

    assert obj.get_property_by_name("unichar") == ""

    obj.set_property_by_name("unichar", "🙃")

    assert obj.get_property_by_name("unichar") == "🙃"
