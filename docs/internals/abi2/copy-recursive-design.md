# `copy_recursive()` Design Notes

Design discussion for an async recursive copy helper using ABI2-style ginext APIs.

## Background

The commander example's `File.copy_to()` is synchronous, blocks the UI thread, and has no
progress reporting. A standalone async helper operating on `Gio.File` directly (no wrapper
class) is the right shape once ginext's async layer is in place.

Ginext's `AsyncCallable` wrapping is automatic: any GIO method with `glib:finish-func` in the
typelib is awaitable inside an `async` function. So `copy`, `enumerate_children`, `next_files`,
`close`, `make_directory`, `query_info`, and `measure_disk_usage` are all directly awaitable
with no `_async` suffix.

GLib error codes are mapped to Python builtins by `install_gio_error_classes`:
`FileExistsError`, `FileNotFoundError`, `PermissionError`. No `GLib.Error` catching needed.

The `__truediv__` overlay on `Gio.File` makes `source / name` work for child path construction.

## Intended Location

`examples/commander/src/commander/fs/copy.py`

## API

```python
@dataclass
class CopyProgress:
    files_done: int
    files_total: int   # 0 = unknown (pre-scan unavailable)
    bytes_done: int
    bytes_total: int   # 0 = unknown

async def copy_recursive(
    source: Gio.File,
    target: Gio.File,
    *,
    flags: Gio.FileCopyFlags = Gio.FileCopyFlags.NONE,
    on_progress: Callable[[CopyProgress], None] | None = None,
) -> None:
```

## Implementation Sketch

Two phases:

**Phase 1 — pre-scan** (only when `on_progress` is given):

```python
_, num_dirs, num_files = await source.measure_disk_usage(Gio.FileMeasureFlags.NONE)
files_total = num_dirs + num_files
bytes_total = disk_usage  # first return value
```

`measure_disk_usage_async` is in the GIR async inventory but marked `introspectable="0"` at
the C level due to OUT parameters. Verify at implementation time whether ginext handles this;
if not, leave `files_total = bytes_total = 0`.

**Phase 2 — inner recursive coroutine `_copy(src, dst)`:**

```python
async def _copy(src: Gio.File, dst: Gio.File) -> None:
    info = await src.query_info("standard::type,standard::size")

    if info.get_file_type() == Gio.FileType.DIRECTORY:
        try:
            await dst.make_directory()
        except FileExistsError:
            pass  # merging into existing dir is fine

        enumerator = await src.enumerate_children("standard::name,standard::type")
        try:
            while batch := await enumerator.next_files(32):
                for child_info in batch:
                    await _copy(src / child_info.get_name(),
                                dst / child_info.get_name())
        finally:
            await enumerator.close()  # always close, even on cancellation

    else:
        file_size = info.get_size()

        def _file_progress(current: int, total: int) -> None:
            if on_progress:
                on_progress(CopyProgress(
                    files_done, files_total,
                    bytes_done + current, bytes_total,
                ))

        await src.copy(dst, flags, progress_callback=_file_progress)
        files_done += 1
        bytes_done += file_size
        if on_progress:
            on_progress(CopyProgress(files_done, files_total, bytes_done, bytes_total))
```

`files_done` and `bytes_done` are `nonlocal` ints in closure scope shared between `_copy` and
`_file_progress`.

## Exception Surface

| Exception | Cause |
|-----------|-------|
| `FileNotFoundError` | source missing |
| `PermissionError` | no read/write access |
| `FileExistsError` | target file exists without `OVERWRITE` flag |
| `asyncio.CancelledError` | task cancelled; `finally` ensures enumerator is closed |

`FileExistsError` on `make_directory` is silently swallowed — merging into an existing
directory is normal for a copy-into operation.

## Flags Reference

| Flag | Value | Notes |
|------|-------|-------|
| `NONE` | 0 | Default |
| `OVERWRITE` | 1 | Overwrite existing files |
| `BACKUP` | 2 | Backup existing files before overwriting |
| `NOFOLLOW_SYMLINKS` | 4 | Don't follow symlinks |
| `ALL_METADATA` | 8 | Copy owner, permissions, timestamps |
| `TARGET_DEFAULT_PERMS` | 32 | Ignore source permissions |
| `TARGET_DEFAULT_MODIFIED_TIME` | 64 | Set mtime to now |

## Caller Integration

`OperationDialog` in `operations/base.py` is currently synchronous. Wiring `copy_recursive`
into the dialog requires async context (GLib + asyncio event loop integration via
`GLibEventLoopPolicy` from `gi.events`). That is a separate task; `copy_recursive` is designed
to be drop-in ready once the dialog layer goes async.

## Progress Design Notes

- `_file_progress` fires during each file's copy with `(current_bytes, total_bytes)` for that
  file; the callback reports running totals by adding `current` to `bytes_done`.
- After a file completes, `files_done` and `bytes_done` are updated and a final progress event
  fires with exact values.
- Directories count in `files_total` (consistent with GIO's `measure_disk_usage` semantics)
  but do not generate their own progress events (they're instant).
- Batch size 32 for `next_files` balances syscall overhead vs. memory for large directories.
