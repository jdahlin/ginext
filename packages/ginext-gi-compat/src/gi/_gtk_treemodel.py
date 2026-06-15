"""pygobject-compatible TreeModel / TreeStore / ListStore overlay.

This module installs the rich Python API that pygobject's Gtk overrides expose:
  - TreeModel subscript access (model[0], model[iter])
  - TreeModelRow, TreeModelRowIter helpers
  - TreePath convenience class
  - ListStore.append(row), insert(pos, row), set(iter, ...) etc.
  - TreeStore.append(parent, row), insert(parent, pos, row) etc.
  - TreeSortable.get_sort_column_id stripping the boolean prefix
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    pass


def strip_boolean_result(
    method: Any,
    exc_type: type | None = None,
    exc_str: str | None = None,
    fail_ret: Any = None,
) -> Any:
    @functools.wraps(method)
    def wrapped(*args: object, **kwargs: object) -> object:
        ret = method(*args, **kwargs)
        if ret[0]:
            if len(ret) == 2:
                return ret[1]
            return ret[1:]
        if exc_type:
            raise exc_type(exc_str or "call failed")
        return fail_ret

    return wrapped


class TreeModelRow:
    def __init__(self, model: Any, iter_or_path: Any) -> None:
        self.model = model
        import gi.repository
        _Gtk = getattr(gi.repository, "Gtk", None)
        if _Gtk is None:
            import gi
            from gi.repository import Gtk as _Gtk
        TreeIterType = _Gtk.TreeIter
        TreePathType = _Gtk.TreePath

        if not hasattr(model, "get_iter"):
            raise TypeError(
                f"expected Gtk.TreeModel, got {type(model).__name__}"
            )
        if isinstance(iter_or_path, TreePathType):
            self.iter = model.get_iter(iter_or_path)
        elif isinstance(iter_or_path, TreeIterType) or type(iter_or_path).__name__ == "TreeIter":
            self.iter = iter_or_path
        else:
            raise TypeError(
                "expected Gtk.TreeIter or Gtk.TreePath, "
                f"{type(iter_or_path).__name__} found"
            )

    @property
    def path(self) -> Any:
        return self.model.get_path(self.iter)

    @property
    def next(self) -> "TreeModelRow | None":
        return self.get_next()

    @property
    def previous(self) -> "TreeModelRow | None":
        return self.get_previous()

    @property
    def parent(self) -> "TreeModelRow | None":
        return self.get_parent()

    def get_next(self) -> "TreeModelRow | None":
        next_iter = self.model.iter_next(self.iter)
        if next_iter:
            return TreeModelRow(self.model, next_iter)
        return None

    def get_previous(self) -> "TreeModelRow | None":
        prev_iter = self.model.iter_previous(self.iter)
        if prev_iter:
            return TreeModelRow(self.model, prev_iter)
        return None

    def get_parent(self) -> "TreeModelRow | None":
        parent_iter = self.model.iter_parent(self.iter)
        if parent_iter:
            return TreeModelRow(self.model, parent_iter)
        return None

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            if key >= self.model.get_n_columns():
                raise IndexError(f"column index is out of bounds: {key:d}")
            if key < 0:
                key = self._convert_negative_index(key)
            return self.model.get_value(self.iter, key)
        if isinstance(key, slice):
            start, stop, step = key.indices(self.model.get_n_columns())
            return [self.model.get_value(self.iter, i) for i in range(start, stop, step)]
        if isinstance(key, tuple):
            return [self[k] for k in key]
        raise TypeError(f"indices must be integers, slice or tuple, not {type(key).__name__}")

    def _set_value(self, col: int, value: Any) -> None:
        model = self.model
        iter_ = self.iter
        if not hasattr(model, "set_value") and hasattr(model, "convert_iter_to_child_iter"):
            iter_ = model.convert_iter_to_child_iter(iter_)
            model = model.get_model()
        model.set_value(iter_, col, value)

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(key, int):
            if key >= self.model.get_n_columns():
                raise IndexError(f"column index is out of bounds: {key:d}")
            if key < 0:
                key = self._convert_negative_index(key)
            self._set_value(key, value)
        elif isinstance(key, slice):
            start, stop, step = key.indices(self.model.get_n_columns())
            index_list = range(start, stop, step)
            if len(index_list) != len(value):
                raise ValueError(
                    f"attempt to assign sequence of size {len(value):d} to slice of size {len(index_list):d}"
                )
            for i, v in enumerate(index_list):
                self._set_value(v, value[i])
        elif isinstance(key, tuple):
            if len(key) != len(value):
                raise ValueError(
                    f"attempt to assign sequence of size {len(value):d} to sequence of size {len(key):d}"
                )
            for k, v in zip(key, value):
                self[k] = v
        else:
            raise TypeError(f"indices must be an integer, slice or tuple, not {type(key).__name__}")

    def _convert_negative_index(self, index: int) -> int:
        new_index = self.model.get_n_columns() + index
        if new_index < 0:
            raise IndexError(f"column index is out of bounds: {index:d}")
        return new_index

    def iterchildren(self) -> "TreeModelRowIter":
        child_iter = self.model.iter_children(self.iter)
        return TreeModelRowIter(self.model, child_iter)

    def __iter__(self) -> Iterator[Any]:
        n = self.model.get_n_columns()
        for i in range(n):
            yield self.model.get_value(self.iter, i)

    def __len__(self) -> int:
        return self.model.get_n_columns()

    def __repr__(self) -> str:
        return f"<TreeModelRow {list(self)!r}>"


class TreeModelRowIter:
    def __init__(self, model: Any, aiter: Any) -> None:
        self.model = model
        self.iter = aiter

    def __next__(self) -> TreeModelRow:
        if not self.iter:
            raise StopIteration
        row = TreeModelRow(self.model, self.iter)
        self.iter = self.model.iter_next(self.iter)
        return row

    def __iter__(self) -> "TreeModelRowIter":
        return self


class TreePath:
    """Wrapper returned from TreeModel subscript-based access; not a C type."""


def _install_treemodel_compat(tree_model_cls: Any, gtk_namespace: Any) -> None:
    """Install TreeModel compat methods onto the ginext Gtk.TreeModel class."""
    if getattr(tree_model_cls, "_pygobject_compat_treemodel", False):
        return

    _raw_get_iter_first = tree_model_cls.get_iter_first
    _raw_iter_children = tree_model_cls.iter_children
    _raw_iter_nth_child = tree_model_cls.iter_nth_child
    _raw_iter_parent = tree_model_cls.iter_parent
    _raw_get_iter_from_string = tree_model_cls.get_iter_from_string

    def _strip2(method: Any, exc_type: Any = None, exc_str: str | None = None, fail_ret: Any = None) -> Any:
        return strip_boolean_result(method, exc_type, exc_str, fail_ret)

    tree_model_cls.get_iter_first = _strip2(_raw_get_iter_first)
    tree_model_cls.iter_children = _strip2(_raw_iter_children)
    tree_model_cls.iter_nth_child = _strip2(_raw_iter_nth_child)
    tree_model_cls.iter_parent = _strip2(_raw_iter_parent)
    tree_model_cls.get_iter_from_string = _strip2(
        _raw_get_iter_from_string, ValueError, "invalid tree path"
    )

    def _tm_get_iter(self: Any, path: Any) -> Any:
        from ginext import Gtk as _Gtk
        if not isinstance(path, _Gtk.TreePath):
            path = _Gtk.TreePath.new_from_string(str(path) if not isinstance(path, str) else path)
        success, aiter = type(self).__mro__[1].get_iter(self, path) if False else _raw_get_iter_impl(self, path)
        if not success:
            raise ValueError(f"invalid tree path '{path}'")
        return aiter

    _raw_get_iter_c = None

    def _tm_get_iter2(self: Any, path: Any) -> Any:
        from ginext import Gtk as _Gtk
        if not isinstance(path, _Gtk.TreePath):
            if isinstance(path, int):
                path = _Gtk.TreePath.new_from_string(str(path))
            elif isinstance(path, str):
                path = _Gtk.TreePath.new_from_string(path)
            else:
                try:
                    path = _Gtk.TreePath.new_from_string(":".join(str(v) for v in path))
                except Exception:
                    raise ValueError(f"invalid tree path '{path}'")
        ok, aiter = _raw_get_iter_c(self, path)
        if not ok:
            raise ValueError(f"invalid tree path '{path}'")
        return aiter

    _raw_get_iter_c = tree_model_cls.get_iter
    tree_model_cls.get_iter = _tm_get_iter2

    def _tm_iter_next(self: Any, aiter: Any) -> Any:
        next_iter = aiter.copy()
        ok = _raw_iter_next_c(self, next_iter)
        if ok:
            return next_iter
        return None

    _raw_iter_next_c = tree_model_cls.iter_next
    tree_model_cls.iter_next = _tm_iter_next

    def _tm_iter_previous(self: Any, aiter: Any) -> Any:
        prev_iter = aiter.copy()
        ok = _raw_iter_previous_c(self, prev_iter)
        if ok:
            return prev_iter
        return None

    _raw_iter_previous_c = getattr(tree_model_cls, "iter_previous", None)
    if _raw_iter_previous_c is not None:
        tree_model_cls.iter_previous = _tm_iter_previous

    def _tm_len(self: Any) -> int:
        return self.iter_n_children(None)

    def _tm_bool(self: Any) -> bool:
        return True

    def _tm_getitem(self: Any, key: Any) -> TreeModelRow:
        if key is None:
            raise TypeError("indices must be integers, not NoneType")
        if isinstance(key, str) and len(key) == 0:
            raise TypeError("indices must be integers, not str")
        if isinstance(key, tuple) and len(key) == 0:
            raise TypeError("indices must be integers, not tuple")
        if type(key).__name__ == "TreeIter":
            return TreeModelRow(self, key)
        if isinstance(key, int) and key < 0:
            index = len(self) + key
            if index < 0:
                raise IndexError(f"row index is out of bounds: {key:d}")
            return TreeModelRow(self, self.get_iter(index))
        try:
            aiter = self.get_iter(key)
        except (ValueError, TypeError) as e:
            if isinstance(e, TypeError):
                raise
            raise IndexError(f"could not find tree path '{key}'")
        return TreeModelRow(self, aiter)

    def _tm_setitem(self: Any, key: Any, value: Any) -> None:
        row = self[key]
        self.set_row(row.iter, value)

    def _tm_delitem(self: Any, key: Any) -> None:
        if key is None:
            raise TypeError("indices must be integers, not NoneType")
        if type(key).__name__ == "TreeIter":
            aiter = key
            self.remove(aiter)
            return
        elif isinstance(key, int) and key < 0:
            index = len(self) + key
            if index < 0:
                raise IndexError(f"row index is out of bounds: {key:d}")
            aiter = self.get_iter(index)
        else:
            try:
                aiter = self.get_iter(key)
            except ValueError:
                raise IndexError(f"could not find tree path '{key}'")
        self.remove(aiter)

    def _tm_iter(self: Any) -> TreeModelRowIter:
        return TreeModelRowIter(self, self.get_iter_first())

    def _tm_convert_value(self: Any, column: int, value: Any) -> Any:
        import ginext
        GObject = ginext._load_namespace("GObject", "2.0", profile=ginext.abi.PYGOBJECT)
        if isinstance(value, GObject.Value):
            return value
        col_type = self.get_column_type(column)
        return GObject.Value(col_type, value)

    def _tm_convert_row(self: Any, row: Any) -> tuple[list[Any], list[int]]:
        if isinstance(row, str):
            raise TypeError("Expected a list or tuple, but got str")
        n_columns = self.get_n_columns()
        if len(row) != n_columns:
            raise ValueError("row sequence has the incorrect number of elements")
        result = []
        columns = []
        for cur_col, value in enumerate(row):
            if value is None:
                continue
            result.append(self._convert_value(cur_col, value))
            columns.append(cur_col)
        return result, columns

    def _tm_set_row(self: Any, treeiter: Any, row: Any) -> None:
        if isinstance(row, dict):
            for key, value in row.items():
                self.set_value(treeiter, key, value)
        elif isinstance(row, (list, tuple)):
            n_columns = self.get_n_columns()
            if len(row) != n_columns:
                raise ValueError(
                    f"row sequence has the incorrect number of elements: expected {n_columns}, got {len(row)}"
                )
            for i, value in enumerate(row):
                if value is not None:
                    self.set_value(treeiter, i, value)
        else:
            raise TypeError(f"row must be a list, tuple, or dict, not {type(row).__name__}")

    def _tm_sort_new_with_model(self: Any) -> Any:
        import ginext
        Gtk = ginext._load_namespace("Gtk", "3.0")
        return Gtk.TreeModelSort.new_with_model(self)

    def _tm_get(self: Any, treeiter: Any, *columns: Any) -> tuple[Any, ...]:
        n_columns = self.get_n_columns()
        values = []
        for col in columns:
            if not isinstance(col, int):
                raise TypeError("column numbers must be ints")
            if col < 0 or col >= n_columns:
                raise ValueError("column number is out of range")
            values.append(self.get_value(treeiter, col))
        return tuple(values)

    tree_model_cls.get = _tm_get
    tree_model_cls.__len__ = _tm_len
    tree_model_cls.__bool__ = _tm_bool
    tree_model_cls.__getitem__ = _tm_getitem
    tree_model_cls.__setitem__ = _tm_setitem
    tree_model_cls.__delitem__ = _tm_delitem
    tree_model_cls.__iter__ = _tm_iter
    tree_model_cls._convert_value = _tm_convert_value
    tree_model_cls._convert_row = _tm_convert_row
    tree_model_cls.set_row = _tm_set_row
    tree_model_cls.sort_new_with_model = _tm_sort_new_with_model

    def _coerce_path(path: Any) -> Any:
        from ginext import Gtk as _Gtk
        if isinstance(path, _Gtk.TreePath):
            return path
        if isinstance(path, int):
            return _Gtk.TreePath.new_from_string(str(path))
        if isinstance(path, str):
            return _Gtk.TreePath.new_from_string(path)
        try:
            return _Gtk.TreePath.new_from_string(":".join(str(v) for v in path))
        except Exception:
            raise TypeError(f"could not convert {path!r} to a Gtk.TreePath") from None

    # Override row_* signal-emitter methods to coerce string/list paths to
    # Gtk.TreePath.  Before overriding, save the original SignalDescriptors so
    # _compat_signal_for_name can still find them for connect() lookups.
    _saved_sds: dict = {}
    for _sname in ("row_changed", "row_deleted", "row_has_child_toggled", "row_inserted"):
        _sd = tree_model_cls.__dict__.get(_sname)
        if _sd is not None:
            _saved_sds[_sname] = _sd

    if _saved_sds:
        _existing = getattr(tree_model_cls, "_compat_signal_descriptors", {})
        _existing.update(_saved_sds)
        tree_model_cls._compat_signal_descriptors = _existing

    def _tm_row_changed(self: Any, path: Any, treeiter: Any) -> None:
        self.emit("row-changed", _coerce_path(path), treeiter)

    def _tm_row_deleted(self: Any, path: Any) -> None:
        self.emit("row-deleted", _coerce_path(path))

    def _tm_row_has_child_toggled(self: Any, path: Any, treeiter: Any) -> None:
        self.emit("row-has-child-toggled", _coerce_path(path), treeiter)

    def _tm_row_inserted(self: Any, path: Any, treeiter: Any) -> None:
        self.emit("row-inserted", _coerce_path(path), treeiter)

    tree_model_cls.row_changed = _tm_row_changed
    tree_model_cls.row_deleted = _tm_row_deleted
    tree_model_cls.row_has_child_toggled = _tm_row_has_child_toggled
    tree_model_cls.row_inserted = _tm_row_inserted

    tree_model_cls._pygobject_compat_treemodel = True


def _install_list_store_compat(list_store_cls: Any) -> None:
    """Install ListStore compat methods (append/insert/set with row args)."""
    if getattr(list_store_cls, "_pygobject_compat_liststore_methods", False):
        return

    _raw_insert_with_valuesv = getattr(list_store_cls, "insert_with_valuesv", None)
    _raw_insert_with_values_c = getattr(list_store_cls, "insert_with_values", None)
    _raw_append = list_store_cls.append
    _raw_insert = list_store_cls.insert
    _raw_insert_before = list_store_cls.insert_before
    _raw_insert_after = list_store_cls.insert_after
    _raw_set_value_c = list_store_cls.set_value

    def _ls_insert_with_values_compat(self: Any, position: int, columns: Any, values: Any) -> Any:
        """pygobject-compatible insert_with_values(pos, columns, values) with raw Python values.

        Inserts atomically without emitting row-changed (only row-inserted).
        """
        import ginext as _gi
        _MATCH_ID = int(_gi.GObject.SignalMatchType.ID)
        _rc_sig_id = _gi.GObject.signal_lookup("row-changed", type(self))
        _gi.GObject.signal_handlers_block_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
        try:
            treeiter = _raw_insert(self, position)
            for col, val in zip(columns, values):
                _raw_set_value_c(self, treeiter, col, self._convert_value(col, val))
        finally:
            _gi.GObject.signal_handlers_unblock_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
        return treeiter

    def _ls_insert_with_values(self: Any, position: int, row: Any) -> Any:
        row_vals, columns = self._convert_row(row)
        return _ls_insert_with_values_compat(self, position, list(columns), row_vals)

    def _ls_do_insert(self: Any, position: int, row: Any) -> Any:
        if row is not None:
            return _ls_insert_with_values(self, position, row)
        return _raw_insert(self, position)

    def _ls_append(self: Any, row: Any = None) -> Any:
        if row:
            return _ls_insert_with_values(self, -1, row)
        return _raw_append(self)

    def _ls_prepend(self: Any, row: Any = None) -> Any:
        return _ls_do_insert(self, 0, row)

    def _ls_insert(self: Any, position: int, row: Any = None) -> Any:
        return _ls_do_insert(self, position, row)

    def _ls_insert_before(self: Any, sibling: Any, row: Any = None) -> Any:
        if row is not None:
            if sibling is None:
                position = -1
            else:
                position = self.get_path(sibling).get_indices()[-1]
            return _ls_do_insert(self, position, row)
        return _raw_insert_before(self, sibling)

    def _ls_insert_after(self: Any, sibling: Any, row: Any = None) -> Any:
        if row is not None:
            if sibling is None:
                position = 0
            else:
                position = self.get_path(sibling).get_indices()[-1] + 1
            return _ls_do_insert(self, position, row)
        return _raw_insert_after(self, sibling)

    def _ls_set_value(self: Any, treeiter: Any, column: int, value: Any) -> None:
        value = self._convert_value(column, value)
        _raw_set_value_c(self, treeiter, column, value)

    def _ls_set(self: Any, treeiter: Any, *args: Any) -> None:
        import ginext as _gi
        _MATCH_ID = int(_gi.GObject.SignalMatchType.ID)
        _rc_sig_id = _gi.GObject.signal_lookup("row-changed", type(self))

        def _set_lists(cols: Any, vals: Any) -> None:
            if len(cols) != len(vals):
                raise TypeError("The number of columns do not match the number of values")
            for col_num, value in zip(cols, vals):
                if not isinstance(col_num, int):
                    raise TypeError("Expected integer argument for column.")
                if not isinstance(col_num, int):
                    raise TypeError("Expected integer argument for column.")
                _raw_set_value_c(self, treeiter, col_num, self._convert_value(col_num, value))

        if args:
            if isinstance(args[0], int):
                if len(args) % 2 != 0:
                    raise TypeError("Expected even number of arguments (column, value, ...)")
                pairs = list(zip(args[::2], args[1::2]))
            elif isinstance(args[0], (tuple, list)):
                if len(args) != 2:
                    raise TypeError("Too many arguments")
                pairs = list(zip(args[0], args[1]))
            elif isinstance(args[0], dict):
                pairs = list(args[0].items())
            else:
                raise TypeError("Argument list must be in the form of (column, value, ...), ((columns,...), (values, ...)) or {column: value}.")
            # Block row-changed during multi-column set, then emit once
            _gi.GObject.signal_handlers_block_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
            try:
                for col_num, value in pairs:
                    _raw_set_value_c(self, treeiter, col_num, self._convert_value(col_num, value))
            finally:
                _gi.GObject.signal_handlers_unblock_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
            # Emit row-changed once after all values are set
            if pairs:
                path = self.get_path(treeiter)
                if path is not None:
                    self.emit("row-changed", path, treeiter)

    list_store_cls.append = _ls_append
    list_store_cls.prepend = _ls_prepend
    list_store_cls.insert = _ls_insert
    list_store_cls.insert_before = _ls_insert_before
    list_store_cls.insert_after = _ls_insert_after
    list_store_cls.set_value = _ls_set_value
    list_store_cls.set = _ls_set

    # pygobject compat: install insert_with_values with raw-Python-value support
    list_store_cls.insert_with_values = _ls_insert_with_values_compat
    list_store_cls.insert_with_valuesv = _ls_insert_with_values_compat

    list_store_cls._pygobject_compat_liststore_methods = True


def _install_tree_store_compat(tree_store_cls: Any) -> None:
    """Install TreeStore compat methods (append/insert with parent and row args)."""
    if getattr(tree_store_cls, "_pygobject_compat_treestore_methods", False):
        return

    _raw_insert_with_valuesv = getattr(tree_store_cls, "insert_with_valuesv", None)
    _raw_insert = tree_store_cls.insert
    _raw_insert_before = tree_store_cls.insert_before
    _raw_insert_after = tree_store_cls.insert_after
    _raw_set_value_c = tree_store_cls.set_value

    def _ts_insert_with_values_compat(self: Any, parent: Any, position: int, columns: Any, values: Any) -> Any:
        import ginext as _gi
        _MATCH_ID = int(_gi.GObject.SignalMatchType.ID)
        _rc_sig_id = _gi.GObject.signal_lookup("row-changed", type(self))
        _gi.GObject.signal_handlers_block_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
        try:
            treeiter = _raw_insert(self, parent, position)
            for col, val in zip(columns, values):
                _raw_set_value_c(self, treeiter, col, self._convert_value(col, val))
        finally:
            _gi.GObject.signal_handlers_unblock_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
        return treeiter

    def _ts_insert_with_values(self: Any, parent: Any, position: int, row: Any) -> Any:
        row_vals, columns = self._convert_row(row)
        return _ts_insert_with_values_compat(self, parent, position, list(columns), row_vals)

    def _ts_do_insert(self: Any, parent: Any, position: int, row: Any) -> Any:
        if row is not None:
            return _ts_insert_with_values(self, parent, position, row)
        return _raw_insert(self, parent, position)

    def _ts_append(self: Any, parent: Any, row: Any = None) -> Any:
        return _ts_do_insert(self, parent, -1, row)

    def _ts_prepend(self: Any, parent: Any, row: Any = None) -> Any:
        return _ts_do_insert(self, parent, 0, row)

    def _ts_insert(self: Any, parent: Any, position: int, row: Any = None) -> Any:
        return _ts_do_insert(self, parent, position, row)

    def _ts_insert_before(self: Any, parent: Any, sibling: Any, row: Any = None) -> Any:
        if row is not None:
            if sibling is None:
                position = -1
            else:
                if parent is None:
                    parent = self.iter_parent(sibling)
                position = self.get_path(sibling).get_indices()[-1]
            return _ts_do_insert(self, parent, position, row)
        return _raw_insert_before(self, parent, sibling)

    def _ts_insert_after(self: Any, parent: Any, sibling: Any, row: Any = None) -> Any:
        if row is not None:
            if sibling is None:
                position = 0
            else:
                if parent is None:
                    parent = self.iter_parent(sibling)
                position = self.get_path(sibling).get_indices()[-1] + 1
            return _ts_do_insert(self, parent, position, row)
        return _raw_insert_after(self, parent, sibling)

    def _ts_set_value(self: Any, treeiter: Any, column: int, value: Any) -> None:
        value = self._convert_value(column, value)
        _raw_set_value_c(self, treeiter, column, value)

    def _ts_set(self: Any, treeiter: Any, *args: Any) -> None:
        import ginext as _gi
        _MATCH_ID = int(_gi.GObject.SignalMatchType.ID)
        _rc_sig_id = _gi.GObject.signal_lookup("row-changed", type(self))

        if args:
            if isinstance(args[0], int):
                if len(args) % 2 != 0:
                    raise TypeError("Expected even number of arguments (column, value, ...)")
                pairs = list(zip(args[::2], args[1::2]))
            elif isinstance(args[0], (tuple, list)):
                if len(args) != 2:
                    raise TypeError("Too many arguments")
                if len(args[0]) != len(args[1]):
                    raise TypeError("The number of columns do not match the number of values")
                pairs = list(zip(args[0], args[1]))
            elif isinstance(args[0], dict):
                pairs = list(args[0].items())
            else:
                raise TypeError("Argument list must be in the form of (column, value, ...), ((columns,...), (values, ...)) or {column: value}.")
            for col_num, _v in pairs:
                if not isinstance(col_num, int):
                    raise TypeError("Expected integer argument for column.")
            _gi.GObject.signal_handlers_block_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
            try:
                for col_num, value in pairs:
                    _raw_set_value_c(self, treeiter, col_num, self._convert_value(col_num, value))
            finally:
                _gi.GObject.signal_handlers_unblock_matched(self, _MATCH_ID, signal_id=_rc_sig_id, detail=0)
            if pairs:
                path = self.get_path(treeiter)
                if path is not None:
                    self.emit("row-changed", path, treeiter)

    tree_store_cls.append = _ts_append
    tree_store_cls.prepend = _ts_prepend
    tree_store_cls.insert = _ts_insert
    tree_store_cls.insert_before = _ts_insert_before
    tree_store_cls.insert_after = _ts_insert_after
    tree_store_cls.set_value = _ts_set_value
    tree_store_cls.set = _ts_set

    if _raw_insert_with_valuesv is not None and not hasattr(tree_store_cls, "insert_with_values"):
        tree_store_cls.insert_with_values = _raw_insert_with_valuesv

    tree_store_cls._pygobject_compat_treestore_methods = True


def _install_tree_sortable_compat(sortable_cls: Any) -> None:
    if getattr(sortable_cls, "_pygobject_compat_treesortable", False):
        return
    _raw_get_sort = sortable_cls.get_sort_column_id
    sortable_cls.get_sort_column_id = strip_boolean_result(_raw_get_sort, fail_ret=(None, None))

    _raw_set_sort_func = sortable_cls.set_sort_func
    _raw_set_default_sort_func = sortable_cls.set_default_sort_func

    def _set_sort_func(self: Any, sort_column_id: int, sort_func: Any, user_data: Any = None) -> None:
        _raw_set_sort_func(self, sort_column_id, sort_func, user_data)

    def _set_default_sort_func(self: Any, sort_func: Any, user_data: Any = None) -> None:
        _raw_set_default_sort_func(self, sort_func, user_data)

    sortable_cls.set_sort_func = _set_sort_func
    sortable_cls.set_default_sort_func = _set_default_sort_func
    sortable_cls._pygobject_compat_treesortable = True


def _install_treepath_compat(tree_path_cls: Any) -> None:
    if getattr(tree_path_cls, "_pygobject_compat_treepath", False):
        return

    _raw_new = tree_path_cls.__new__
    _raw_new_from_string = tree_path_cls.new_from_string

    def _tp_new(cls: type, path: Any = 0) -> Any:
        if isinstance(path, int):
            path_str = str(path)
        elif isinstance(path, str):
            path_str = path
        elif isinstance(path, (tuple, list)):
            path_str = ":".join(str(v) for v in path)
        else:
            try:
                path_str = str(path)
            except Exception:
                raise TypeError(f"could not parse subscript '{path}' as a tree path")
        if len(path_str) == 0:
            raise TypeError(f"could not parse subscript '{path}' as a tree path")
        try:
            return _raw_new_from_string(path_str)
        except (TypeError, ValueError):
            raise TypeError(f"could not parse subscript '{path}' as a tree path")

    tree_path_cls.__new__ = staticmethod(_tp_new)

    def _tp_eq(self: Any, other: Any) -> bool:
        if other is None:
            return False
        if not hasattr(other, "compare"):
            return NotImplemented
        return self.compare(other) == 0

    def _tp_ne(self: Any, other: Any) -> bool:
        r = _tp_eq(self, other)
        if r is NotImplemented:
            return r
        return not r

    def _tp_lt(self: Any, other: Any) -> bool:
        return other is not None and self.compare(other) < 0

    def _tp_le(self: Any, other: Any) -> bool:
        return other is not None and self.compare(other) <= 0

    def _tp_gt(self: Any, other: Any) -> bool:
        return other is None or self.compare(other) > 0

    def _tp_ge(self: Any, other: Any) -> bool:
        return other is None or self.compare(other) >= 0

    def _tp_iter(self: Any) -> Iterator[int]:
        return iter(self.get_indices())

    def _tp_len(self: Any) -> int:
        return self.get_depth()

    def _tp_getitem(self: Any, index: Any) -> int:
        return self.get_indices()[index]

    def _tp_str(self: Any) -> str:
        return self.to_string() or ""

    def _tp_repr(self: Any) -> str:
        return f"<TreePath {_tp_str(self)!r}>"

    tree_path_cls.__eq__ = _tp_eq
    tree_path_cls.__ne__ = _tp_ne
    tree_path_cls.__lt__ = _tp_lt
    tree_path_cls.__le__ = _tp_le
    tree_path_cls.__gt__ = _tp_gt
    tree_path_cls.__ge__ = _tp_ge
    tree_path_cls.__iter__ = _tp_iter
    tree_path_cls.__len__ = _tp_len
    tree_path_cls.__getitem__ = _tp_getitem
    tree_path_cls.__str__ = _tp_str
    tree_path_cls.__repr__ = _tp_repr
    tree_path_cls._pygobject_compat_treepath = True


def _install_treeviewcolumn_compat(tvc_cls: Any) -> None:
    if getattr(tvc_cls, "_pygobject_compat_tvc", False):
        return

    _raw_tvc_init = tvc_cls.__init__

    def _tvc_init(self: Any, title: str = "", cell_renderer: Any = None, **attributes: Any) -> None:
        _raw_tvc_init(self, title=title)
        if cell_renderer is not None:
            self.pack_start(cell_renderer, True)
            for name, value in attributes.items():
                self.add_attribute(cell_renderer, name, value)

    _raw_cell_get_position = tvc_cls.cell_get_position
    tvc_cls.cell_get_position = strip_boolean_result(_raw_cell_get_position)

    _raw_set_cell_data_func = tvc_cls.set_cell_data_func

    def _set_cell_data_func(self: Any, cell_renderer: Any, func: Any, func_data: Any = None) -> None:
        _raw_set_cell_data_func(self, cell_renderer, func, func_data)

    def _set_attributes(self: Any, cell_renderer: Any, **attributes: Any) -> None:
        import ginext
        Gtk = ginext._load_namespace("Gtk", "3.0")
        Gtk.CellLayout.clear_attributes(self, cell_renderer)
        for name, value in attributes.items():
            Gtk.CellLayout.add_attribute(self, cell_renderer, name, value)

    tvc_cls.__init__ = _tvc_init
    tvc_cls.set_cell_data_func = _set_cell_data_func
    tvc_cls.set_attributes = _set_attributes
    tvc_cls._pygobject_compat_tvc = True


def _install_treeview_compat(tv_cls: Any) -> None:
    if getattr(tv_cls, "_pygobject_compat_treeview", False):
        return

    _raw_set_cursor = tv_cls.set_cursor
    _raw_insert_column_with_attributes = getattr(tv_cls, "insert_column_with_attributes", None)

    def _set_cursor(self: Any, path: Any, column: Any = None, start_editing: bool = False) -> None:
        _raw_set_cursor(self, path, column, start_editing)

    _raw_scroll_to_cell = tv_cls.scroll_to_cell

    def _scroll_to_cell(
        self: Any,
        path: Any,
        column: Any = None,
        use_align: bool = False,
        row_align: float = 0.0,
        col_align: float = 0.0,
    ) -> None:
        _raw_scroll_to_cell(self, path, column, use_align, row_align, col_align)

    def _insert_column_with_attributes(
        self: Any, position: int, title: str, cell: Any, **attributes: Any
    ) -> Any:
        import ginext
        Gtk = ginext._load_namespace("Gtk", "3.0")
        tv_col = Gtk.TreeViewColumn()
        tv_col.set_title(title)
        tv_col.pack_start(cell, True)
        for name, value in attributes.items():
            tv_col.add_attribute(cell, name, value)
        return self.insert_column(tv_col, position)

    tv_cls.set_cursor = _set_cursor
    tv_cls.scroll_to_cell = _scroll_to_cell
    tv_cls.insert_column_with_attributes = _insert_column_with_attributes
    tv_cls._pygobject_compat_treeview = True


def _install_treeselection_compat(sel_cls: Any) -> None:
    if getattr(sel_cls, "_pygobject_compat_treeselection", False):
        return

    _raw_get_selected = sel_cls.get_selected

    def _get_selected(self: Any) -> Any:
        ok, model, aiter = _raw_get_selected(self)
        if ok:
            return model, aiter
        return None, None

    _raw_get_selected_rows = sel_cls.get_selected_rows

    def _get_selected_rows(self: Any) -> Any:
        rows, model = _raw_get_selected_rows(self)
        return model, rows

    _raw_select_path = sel_cls.select_path

    def _select_path(self: Any, path: Any) -> None:
        if not type(path).__name__ == "TreePath":
            import ginext
            Gtk = ginext._load_namespace("Gtk", "3.0")
            if isinstance(path, int):
                path = Gtk.TreePath.new_from_string(str(path))
            elif isinstance(path, str):
                path = Gtk.TreePath.new_from_string(path)
            elif isinstance(path, (tuple, list)):
                path = Gtk.TreePath.new_from_string(":".join(str(v) for v in path))
        _raw_select_path(self, path)

    sel_cls.get_selected = _get_selected
    sel_cls.get_selected_rows = _get_selected_rows
    sel_cls.select_path = _select_path
    sel_cls._pygobject_compat_treeselection = True


def install_tree_compat(namespace: Any) -> None:
    """Install all tree compat methods on Gtk namespace classes."""
    tree_path_cls = getattr(namespace, "TreePath", None)
    if tree_path_cls is not None:
        _install_treepath_compat(tree_path_cls)

    tree_model_cls = getattr(namespace, "TreeModel", None)
    if tree_model_cls is not None:
        _install_treemodel_compat(tree_model_cls, namespace)

    list_store_cls = getattr(namespace, "ListStore", None)
    if list_store_cls is not None:
        _install_list_store_compat(list_store_cls)

    tree_store_cls = getattr(namespace, "TreeStore", None)
    if tree_store_cls is not None:
        _install_tree_store_compat(tree_store_cls)

    sortable_cls = getattr(namespace, "TreeSortable", None)
    if sortable_cls is not None:
        _install_tree_sortable_compat(sortable_cls)

    tvc_cls = getattr(namespace, "TreeViewColumn", None)
    if tvc_cls is not None:
        _install_treeviewcolumn_compat(tvc_cls)

    tv_cls = getattr(namespace, "TreeView", None)
    if tv_cls is not None:
        _install_treeview_compat(tv_cls)

    sel_cls = getattr(namespace, "TreeSelection", None)
    if sel_cls is not None:
        _install_treeselection_compat(sel_cls)

    # Expose helpers in the namespace for tests that import them
    namespace.TreeModelRow = TreeModelRow
    namespace.TreeModelRowIter = TreeModelRowIter
