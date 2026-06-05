import gc
import weakref
from typing import Any, cast

import pytest
from gi.repository import GObject, Regress

try:
    from gi.repository import Gtk

    GTK4 = Gtk._version == "4.0"
except ImportError:
    Gtk = cast(Any, None)
    GTK4 = False


@pytest.mark.xfail(
    reason="fundamental type constructor compatibility is incomplete",
    strict=False,
)
def test_constructor_no_data():
    obj = Regress.TestFundamentalSubObject()

    assert isinstance(obj, Regress.TestFundamentalSubObject)
    assert isinstance(obj, Regress.TestFundamentalObject)
    assert obj.refcount == 1
    assert obj.data is None


def test_constructor_with_data():
    with pytest.raises(TypeError):
        Regress.TestFundamentalSubObject(data="foo")


@pytest.mark.xfail(
    reason="fundamental type new() constructor compatibility is incomplete",
    strict=False,
)
def test_create_fundamental_new_with_data():
    obj = Regress.TestFundamentalSubObject.new("foo")

    assert isinstance(obj, Regress.TestFundamentalSubObject)
    assert isinstance(obj, Regress.TestFundamentalObject)
    assert obj.refcount == 1
    assert obj.data == "foo"


@pytest.mark.xfail(
    reason="fundamental type new() constructor compatibility is incomplete",
    strict=False,
)
def test_change_field():
    obj = Regress.TestFundamentalObjectNoGetSetFunc.new("foo")

    obj.data = "bar"

    assert obj.get_data() == "bar"


def test_call_method():
    obj = Regress.TestFundamentalObjectNoGetSetFunc.new("foo")

    assert obj.get_data() == "foo"


def test_create_fundamental_hidden_class_instance():
    obj = Regress.test_create_fundamental_hidden_class_instance()

    assert isinstance(obj, Regress.TestFundamentalObject)


@pytest.mark.xfail(
    reason="fundamental type new() constructor compatibility is incomplete",
    strict=False,
)
def test_create_fundamental_refcount():
    obj = Regress.TestFundamentalSubObject.new("foo")

    assert obj.refcount == 1


def test_delete_fundamental_refcount():
    obj = Regress.TestFundamentalSubObject.new("foo")
    del obj

    gc.collect()


@pytest.mark.xfail(
    reason="fundamental __gtype__ and GObject.Value compatibility is incomplete",
    strict=False,
)
def test_value_set_fundamental_object():
    val = GObject.Value(Regress.TestFundamentalSubObject.__gtype__)
    obj = Regress.TestFundamentalSubObject()

    val.set_value(obj)

    assert val.get_value() == obj


@pytest.mark.xfail(
    reason="fundamental __gtype__ and GObject.Value compatibility is incomplete",
    strict=False,
)
def test_value_set_wrong_value():
    val = GObject.Value(Regress.TestFundamentalSubObject.__gtype__)

    with pytest.raises(TypeError, match="Fundamental type is required"):
        val.set_value(1)


@pytest.mark.xfail(
    reason="fundamental __gtype__ and GObject.Value compatibility is incomplete",
    strict=False,
)
def test_value_set_wrong_fundamental():
    class MyCustomFundamentalObject(Regress.TestFundamentalObject):
        pass

    val = GObject.Value(Regress.TestFundamentalSubObject.__gtype__)

    with pytest.raises(TypeError, match="Invalid fundamental type for assignment"):
        val.set_value(MyCustomFundamentalObject())


@pytest.mark.xfail(
    reason="fundamental object construction and array marshalling compatibility is incomplete",
    strict=False,
)
def test_array_of_fundamental_objects_in():
    assert Regress.test_array_of_fundamental_objects_in(
        [Regress.TestFundamentalSubObject()]
    )


def test_array_of_fundamental_objects_out():
    objs = Regress.test_array_of_fundamental_objects_out()

    assert len(objs) == 2
    assert all(isinstance(o, Regress.TestFundamentalObject) for o in objs)


@pytest.mark.xfail(
    reason="fundamental object construction and argument marshalling compatibility is incomplete",
    strict=False,
)
def test_fundamental_argument_in():
    obj = Regress.TestFundamentalSubObject()

    assert Regress.test_fundamental_argument_in(obj)


def test_abstract_fundamental_type():
    with pytest.raises(TypeError):
        Regress.TestFundamentalObject()


@pytest.mark.xfail(
    reason="fundamental object out-argument compatibility is incomplete",
    strict=False,
)
def test_fundamental_argument_out():
    obj = Regress.TestFundamentalSubObject.new("data")
    other = Regress.test_fundamental_argument_out(obj)

    assert type(obj) is type(other)
    assert obj is not other
    assert obj.data == other.data


@pytest.mark.xfail(
    reason="fundamental object construction compatibility is incomplete",
    strict=False,
)
def test_multiple_objects():
    obj1 = Regress.TestFundamentalSubObject()
    obj2 = Regress.TestFundamentalSubObject()

    assert obj1 != obj2


@pytest.mark.xfail(
    reason="fundamental object construction and weak-ref compatibility is incomplete",
    strict=False,
)
def test_fundamental_weak_ref():
    obj = Regress.TestFundamentalSubObject()
    weak = weakref.ref(obj)

    assert weak() == obj

    del obj
    gc.collect()

    assert weak() is None


@pytest.mark.xfail(
    reason="primitive fundamental constructor compatibility is incomplete",
    strict=False,
)
def test_fundamental_primitive_object():
    bitmask = Regress.Bitmask(2)

    assert bitmask.v == 2


@pytest.mark.xfail(
    reason="custom fundamental subclass construction and vfunc compatibility is incomplete",
    strict=False,
)
def test_custom_fundamental_type_vfunc_override():
    class MyCustomFundamentalObject(Regress.TestFundamentalObject):
        def __init__(self):
            super().__init__()
            invocations["__init__"] = True

        def do_finalize(self):
            invocations["do_finalize"] = True

    invocations = {}
    obj = MyCustomFundamentalObject()
    del obj
    gc.collect()

    assert "__init__" in invocations
    assert "do_finalize" in invocations


@pytest.mark.skipif(not GTK4, reason="requires GTK 4")
@pytest.mark.xfail(
    reason="GValue conversion for arbitrary Python objects is incomplete",
    strict=False,
)
def test_gtk_expression():
    obj = object()
    con = Gtk.ConstantExpression.new_for_value(obj)

    assert con.get_value() is obj


@pytest.mark.skipif(not GTK4, reason="requires GTK 4")
@pytest.mark.xfail(
    reason="GTK expression fundamental property compatibility is incomplete",
    strict=False,
)
def test_gtk_string_filter_fundamental_property():
    expr = Gtk.ConstantExpression.new_for_value("one")
    filter = Gtk.StringFilter.new(expr)
    filter.props.expression = expr

    assert filter.get_expression() == expr
    assert filter.props.expression == expr
