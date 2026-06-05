# PyGObject Architectural Issues To Research

Based on the `docs/pygobject-gitlab-issues/` snapshot fetched on
2026-05-15. The snapshot contains 760 public issues: 150 open and 610 closed.

This is not a full issue summary. It is a design-oriented pass over recurring
PyGObject problems that are relevant to goi's architecture.

## 1. Async Is A Cross-Cutting Architecture, Not A Wrapper

Representative issues:

- !146: Add support for Python 3 asyncio event loop.
- !500: Comparing asyncio mainloop implementations.
- !636: Follow up on asyncio support.
- !641: asyncio error propagation issue.
- !677: `pygi_async_finish_cb` misbehaves when the finish function is a constructor.
- !689: event loop source registration mismatch with Python 3.13.
- !700: support `await`-style async operations.
- !235: GLib async callbacks ran in a surprising thread/context.
- !125: improve GTask wrapping.
- !382: `Gio.InputStream.read_async/read_all_async` buffer lifetime crashes.

Lessons:

- Async cannot be solved only by detecting `*_async` and calling `*_finish`.
  Constructor finish functions, nullable returns, error domains, callback
  thread/context, and buffer ownership all affect correctness.
- The event loop design is a compatibility surface. It needs a clear answer
  for how `asyncio` selectors map to `GMainContext`, including Python-version
  changes like Python 3.13 selector behavior.
- Error propagation must preserve GLib error domains/codes, not collapse into
  a generic exception that forces string matching.
- Async I/O with caller-provided buffers needs explicit lifetime ownership.

Research for goi:

- Define one async model: callback-compatible first, `await` sugar second.
- Store async pair metadata explicitly instead of re-discovering it at call
  time where possible.
- Treat finish functions that are constructors as a distinct call shape.
- Add tests for callback thread/context, cancellation, error-domain matching,
  nullable async results, and buffer lifetime.

## 2. Callback, Closure, And Signal Lifetime Is Fragile

Representative issues:

- !36: `Object.connect_object` holds a strong reference to object argument.
- !70: GtkBuilder user-data objects not passed to signal handlers.
- !12: support out parameters in signals.
- !68: signal marshalling of string + length.
- !158: memory corruption around closure list during cross-thread GC/disconnect.
- !122: occasional SIGSEGV invoking a C callable.
- !581: `G_IS_TASK` error with completion provider.
- !43: meta issue for leak-free PyGI marshalling.
- !47: vfunc arguments leaked.
- !69: callable cache for signal and vfunc closures.

Lessons:

- Closure ownership must be explicitly modeled. Signal connections, builder
  callbacks, vfunc closures, and async callbacks all have slightly different
  ownership rules.
- Strong references in convenience APIs can defeat the purpose of lifetime-
  tied signal helpers.
- Callback argument shaping must support C signal quirks: user data, length
  arguments, out parameters, and caller-allocated storage.
- GC and disconnect can run through different GLib/Python paths; closure lists
  need thread-aware synchronization and predictable GIL handling.

Research for goi:

- Keep closure state in one native representation with clear ownership states:
  connected, disconnected, in-flight, finalized.
- Make disconnect/finalize idempotent and thread-aware.
- Build signal argument plans separately from method-call argument plans.
- Test builder signal user-data, connect_object lifetime, signal out params,
  and length-paired callback arrays.

## 3. Subclassing, Vfuncs, Interfaces, And GType Registration Are One System

Representative issues:

- !3: overriding inherited interface methods requires explicitly re-inheriting
  from the interface.
- !367: vfunc inheritance does not work.
- !258: importing Gtk caused a metaclass conflict.
- !7 and !9: vfunc implementation resolution timing.
- !13: cannot install Gtk.Widget style properties.
- !357: properties with custom specs.
- !386: `Gtk.Template.init_template` double-call behavior.
- !52, !179, !230, !257: composite template/template hierarchy problems.

Lessons:

- Python subclass registration cannot be independent from interface/vfunc
  installation. The GType, class struct, interface vtables, Python MRO, and
  Python descriptors all need to agree.
- Lazy vfunc resolution is attractive but can create inheritance and override
  timing bugs.
- Custom metaclasses are a risk: they improve class-creation control but can
  collide with other Python metaclasses.
- `Gtk.Template` is not just a decorator; it depends on class creation,
  instance initialization, builder callbacks, and typed child descriptors.

Research for goi:

- Keep `__init_subclass__`/metaclass behavior minimal until a real custom
  metaclass is required.
- Treat interface vfuncs as first-class during subclass registration.
- Add tests for inherited interface override without restating the interface.
- Add tests for vfunc chaining, template double-init, template inheritance, and
  Python-set GObject properties.

## 4. Marshalling Needs A Declarative Ownership Plan

Representative issues:

- !43: meta issue for leak-free marshalling.
- !56: transfer-full `GArray`, `GPtrArray`, and `GHashTable` elements leak.
- !87: caller-allocated GValues from Python vfuncs leak.
- !278: `GHashTable` with boxed values segfaults.
- !516: array length argument not omitted when marshalling callback arrays.
- !41: segfault with methods returning `GValue` of type `GValue`.
- !154: `GLib.VariantType.next` broken.
- !469: constructor returning NULL reported as an error even when allowed.
- !712: `GLib.MainContext.query()` crashes because the C API is two-pass.

Lessons:

- GI annotations are necessary but insufficient. Some APIs require custom call
  plans: two-pass calls, caller-allocated values, nullable constructors, or
  container element cleanup.
- Container marshalling must own both the container and each element's cleanup
  policy. Transfer-full on the outer container is not enough.
- Callback/vfunc marshalling has different length/out/caller-allocated rules
  than regular method invocation.
- Return shaping must preserve GLib semantics: nullable constructors should
  become `None`, not an opaque "constructor returned NULL" error.

Research for goi:

- Make invoke plans explicit about ownership, cleanup, and two-pass calls.
- Separate method, constructor, signal callback, vfunc, and async-finish plans.
- Add marshalling tests for nested container ownership, boxed hash values,
  GValue-of-GValue, nullable constructors, callback arrays, and two-pass APIs.

## 5. Object Lifetime, Toggle Refs, Weakrefs, And Free-Threading

Representative issues:

- !273: try to get rid of toggle refs.
- !646: support free-threaded Python.
- !158: closure list race during GC/disconnect.
- !137, !350, !547: refcount issues crossing library boundaries.
- !27: embedded Python C program segfaults on reinitialization.

Lessons:

- Toggle refs create surprising observable behavior and complicate weakrefs,
  wrapper identity, and GC.
- Free-threaded Python will make implicit GIL assumptions fail. Closure lists,
  wrapper registries, qdata, async completions, and finalization paths all need
  an explicit threading story.
- Embedded/reinitialized Python stresses process-lifetime caches and leaked
  singletons.

Research for goi:

- Continue avoiding toggle refs unless a concrete compatibility blocker appears.
- Keep wrapper identity storage independent from Python wrapper lifetime where
  possible.
- Audit every native global/cache for subinterpreter/reinitialization behavior.
- Add PEP 703/free-threaded tests early, especially for closure disconnect,
  object finalization, and async completion.

## 6. Errors Need Domain-Aware Python Shapes

Representative issues:

- !199: GError-specific logic could be easier.
- !641: asyncio error propagation collapsed into a generic error.
- !442: Windows GError conversion failed.
- !342: GDBus error helper introspection issue.

Lessons:

- `GLib.Error` should preserve enough structure to match domain/code cleanly.
- Async and sync call paths must shape errors the same way.
- GDBus remote errors need a clear story for stripping/matching remote domains.

Research for goi:

- Provide `err.matches(domain, code)` parity and make it easy to discover
  domain constants.
- Ensure async `await` exceptions and callback `_finish()` exceptions carry the
  same domain/code/message.

## 7. Python Ergonomics And Typing Are Architectural Surfaces

Representative issues:

- !508: typed `.connect_*` helpers for signal callbacks.
- !530: typing/linting with `Gtk.Template.Child`.
- !286: typing for template specifications.
- !527 and !627: `os.PathLike` / `pathlib.Path` support.
- !699 and !683: enum/flags introspection attributes/regressions.
- !231: pylint mismatch for virtual methods.

Lessons:

- PyGObject compatibility is not only runtime behavior. IDEs, type checkers,
  linters, and generated stubs affect whether large apps can adopt a binding.
- Dynamic signal names and template child replacement are hard for static tools
  unless the binding exposes a typed surface.
- Small Python-native conveniences like PathLike support reduce app-side glue
  and are easy to regress if treated as overlays instead of call-shape policy.

Research for goi:

- Generate typed signal helpers or at least typed overload metadata.
- Make `Gtk.Template.Child` understandable to stubs/type checkers.
- Accept `os.PathLike` for filename/path inputs, but avoid broadening every
  arbitrary UTF-8 string argument.
- Keep enum/flags class surfaces stable and introspectable.

## 8. Static Overrides Drift From Introspection

Representative issues:

- !33: replace static GObject bindings with GI and Python.
- !40: replace static `Object.bind_property` with introspection version.
- !32: remove static GParamSpec bindings.
- !508: signal connection API surface.
- !396: missing documentation for template support.

Lessons:

- Static overrides solve immediate compatibility holes but become parallel API
  surfaces that drift from introspection.
- Overlays should be data-driven or generated where possible, and hand-written
  only when Python shape genuinely differs from C shape.

Research for goi:

- Keep compiled overlays declarative.
- Track every hand-written overlay with a compatibility reason and tests.
- Prefer shaping introspected callables over replacing them with unrelated
  Python functions.

## Suggested Research Order For goi

1. Async call plan architecture: pair detection, finish constructors,
   cancellation, error domains, and buffer lifetime.
2. Closure/signal/vfunc lifetime: one native closure model with thread-aware
   disconnect/finalize behavior.
3. Subclass/interface/vfunc registration: inherited interface overrides and
   template lifecycle.
4. Declarative marshalling plans: containers, GValue/GVariant, nullable
   constructors, callback arrays, and two-pass APIs.
5. Free-threaded Python audit: wrapper registry, closure lists, async
   completion, object finalization.
6. Typed ergonomic surface: PathLike, typed signals, Template.Child, enum/flags
   stability.
