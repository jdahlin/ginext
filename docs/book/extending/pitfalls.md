# FFI pitfalls and lifetimes

> The bugs that bite everyone the first time they cross the language boundary. Memorize these and you'll save days.

## What this chapter covers

- **Transfer ownership errors**: the single most common crash. Walk through `(transfer none)` vs `(transfer full)` vs `(transfer container)` and what happens when each is wrong.
- **NULL where goi doesn't expect it**: missing `(nullable)` annotations.
- **Strings**: `const gchar *` vs `gchar *`; UTF-8 expectation; encoding errors crossing the boundary.
- **Arrays**: missing length annotations; off-by-one in `(array length=...)`.
- **Callback scopes**:
    - `(scope call)` — callback freed after function returns; common case.
    - `(scope async)` — kept for one-shot async result.
    - `(scope notified)` — kept until `destroy_notify` fires; needs `(closure ...)`.
    - `(scope forever)` — kept for the program's lifetime (rare; e.g., signal handlers).
- **User-data lifetime**: Python objects passed as `user_data` need to be kept alive in Python.
- **Thread safety**: the GIL, GObject's main-context model, what's safe from where.
- **Reference cycles**: GObject and Python both refcount; cycles between them need explicit breaks.
- **GError ownership**: who frees, when.
- **GDestroyNotify** misalignment.
- **GType vs Python class**: when GType lookup fails and what to do.

## What you'll be able to do

- Recognize FFI crash signatures and map them to causes.
- Write defensive C/annotation patterns the first time, not the second.

## Notes for the writer

- This is the most cited chapter in Part VII. Make it a checklist as much as a narrative.
- Include "the symptom → the cause" lookup table.
