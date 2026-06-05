# ABI2 Methods

ABI2 methods, constructors, and static functions should look like ordinary
Python callables while preserving the GObject invocation boundary.

Unconflicted methods keep the natural Python spelling:

```python
cancellable.cancel()
file.get_parent()
```

Class constructors and static constructors follow the same rule:

```python
cancellable = Gio.Cancellable.new()
file = Gio.File.new_for_path(path)
```

That rule is not a requirement to expose every GIR `new_*` or helper function
under its C-derived name on the native surface. When a GTK, GIO, or GStreamer
operation maps cleanly to a familiar Python abstraction, ABI2 should expose the
abstraction and keep the mechanical GIR spelling in compatibility mode. For
example, `Gio.File.temporary()` is clearer than `Gio.File.new_tmp()` if ABI2
also defines the result record and async behavior.

ABI2 may use a GIR callable without exposing it as a public native attribute.
This is how larger abstractions can force one coherent API instead of leaking
every low-level operation:

```python
async with file.open("r+b") as stream:
    ...
```

can internally call `g_file_open_readwrite_async()` /
`g_file_open_readwrite_finish()` even if `file.open_readwrite()` and
`file.open_readwrite_async()` are not public ABI2 methods.

Hidden callables need an explicit policy:

- they remain available on the compatibility surface;
- native wrappers may call them through an internal invoker, provisionally
  named `_internal_invoke()`, or a private descriptor table;
- normal ABI2 attribute lookup should raise `AttributeError`;
- generated docs and stubs should not advertise them as public native methods;
- tests should cover both the public wrapper and the hidden-name rejection.

The internal API should not be installed as a method on user objects. Prefer a
runtime helper shape like:

```python
stream = await _abi2._internal_invoke(
    file,
    "Gio.File.open_readwrite_async",
    finish="Gio.File.open_readwrite_finish",
    args=(priority, cancellable),
)
```

over names such as `file.__private_open_readwrite()`. The latter still leaks a
discoverable object attribute and invites users to depend on it.

Use this only when the Python abstraction is genuinely better. Do not hide
low-level operations merely because they look C-like; hide them when exposing
them would create two competing ways to do the same thing.

When a method participates in a property-involved conflict, the escaped spelling
is `foo_func`:

```python
widget.has_focus_func()
```

The full conflict policy is in [Shared Namespace](shared-namespace.md).

## Native Boundary

During the Python bootstrap stage, ABI2 method objects may delegate to the
existing compat callable implementation. The ABI2 boundary still has to wrap
results and unwrap arguments at the native edge:

```python
store.append(native_item)     # passes the underlying compat/GObject instance
item = store.get_item(0)      # returns a native ABI2 wrapper
```

The final C implementation should keep that same contract without duplicating
the invocation and GI marshalling engine. What is duplicated per ABI is the
class/type surface and method descriptor policy; those descriptors can still
call a shared low-level invoker.

## MethodSignal

Method/signal conflicts are different from property conflicts because both
members are operations. A `MethodSignal` object preserves the obvious Python
method call and still exposes the signal API:

```python
obj.foo(...)
obj.foo.connect(callback)
obj.foo.connect(callback, after=True)
obj.foo.emit(...)
```

Detailed signals use indexing:

```python
obj.notify("title").connect(callback)
```

This avoids stringly native code such as `connect("notify::title", ...)` while
using `GObject.Object.notify(obj, "title")` for explicit notification.

Use `MethodSignal` for every pure method/signal conflict. The installed GIR
conflict scan shows these are by far the common case. If a property also
participates, do not use the short spelling; use `foo_`, `foo_func`, and
`foo_signal` as described in [Shared Namespace](shared-namespace.md).

## Async Methods

ABI2 defaults to async for operations that have an explicit async call plan. For
a sync/async/finish family, the natural short name is the awaitable operation
and the blocking operation gets an explicit `_sync()` suffix.

For example, a native file operation can present:

```python
result = await file.load_contents()
sync_result = file.load_contents_sync()
```

while still keeping compatibility spellings available where needed:

```python
file.load_contents_async(cancellable, callback)
file.load_contents_finish(result)
```

The `_sync()` spelling is only added for operations whose short native name was
promoted to async. A method with no async sibling remains a normal synchronous
method at the short spelling.

An awaitable ABI2 method plan must specify:

- the source async callable;
- the matching finish callable;
- the blocking sync callable, when one exists;
- cancellation behavior and whether a `Gio.Cancellable` is synthesized;
- result shaping, including multi-value records;
- nullable result behavior;
- error-domain and error-code preservation;
- buffer and callback lifetime rules.

The generated async inventory is in [Async Inventory](async.md). Entries with a
`finish:` pair are candidates for awaitable wrappers. Entries without a finish
pair but with a `*_async` name need an explicit hand-written policy before ABI2
should promote them to `await`.

## Constructors And Async Factories

Python constructors should stay synchronous. Do not make class construction
return an awaitable:

```python
file = Gio.File(path)          # sync, maps to path construction
file = Gio.File(uri=uri)       # sync, maps to URI construction
```

Async constructor-like operations should be class methods or factory methods,
not `__init__` / `__call__`:

```python
tmp = await Gio.File.temporary()
tmp_sync = Gio.File.temporary_sync()
tmp_dir = await Gio.File.temporary_dir()
```

This is especially important for operations such as `Gio.File.new_tmp`, whose
finish function returns more than just a `GFile`: it also returns a
`GFileIOStream`. ABI2 should expose that as a result record instead of hiding it
inside `Gio.File(...)`.

The detailed `Gio.File` factory and open-mode policy is in
[Gio.File](gio-file.md).
