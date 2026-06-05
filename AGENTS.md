# Agent Instructions

## Project

This repository is  modern Python binding for gobject-introspection.

## Development Guidelines

- binding code goes into ginext/
- compatibility code goes into gi/ and only here
- Prefer small, focused changes that follow existing code and test patterns.
- Do not add unnecessary comments or docstrings. Add comments only when they
  clarify non-obvious behavior.
- Keep commit messages brief and specific.
- Run the relevant tests before committing.
- Avoid unrelated refactors, formatting churn, or generated output changes.

## Useful Commands

- `make test` runs the default build and test suite.
- `make test-debug` runs the tests with the configured debug Python.
- `make test-asan` runs the tests with address sanitizer enabled.
- `make test-ubsan` runs the tests with undefined behavior sanitizer enabled.
- `make test-coverage` runs tests with coverage enabled and prints a coverage
  summary.
- `PYTEST_ARGS='src/ginext/tests/some_test.py -q -n 0' make test` runs a focused
  pytest selection through the normal build environment.

For help choosing focused tests, see the ginext test suite map in
[`src/ginext/tests/README.md`](src/ginext/tests/README.md).

Shared pytest fixtures are categorized in the "Shared Fixtures And Helpers"
section of [`src/ginext/tests/README.md`](src/ginext/tests/README.md).

For the current skipped/xfail backlog, see
[`src/ginext/tests/TODO.md`](src/ginext/tests/TODO.md).

Implementation-specific design notes, architecture plans, and development
checklists live in [`docs/internals/`](docs/internals/).

## Before Commit

1. Run the narrowest useful test command for the change.
2. Run `make test` when the change touches shared runtime behavior,
   compatibility behavior, or test infrastructure.
3. Review the diff for accidental comments, docstrings, formatting churn, and
   unrelated edits.
