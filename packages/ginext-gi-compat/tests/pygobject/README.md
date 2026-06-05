# PyGObject Compatibility Tests

This directory stages tests copied from `pygobject/tests`.

The copied `test_*.py` files are intentionally left close to their upstream
shape. They are collected normally by pytest so compatibility gaps show up as
real failures or upstream skip/xfail markers.

The subtree enables the `pygobject_compat` feature flag in `conftest.py` so
the tests can import `gi.repository` through ginext's compatibility layer.
