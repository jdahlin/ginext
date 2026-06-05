# Compiled Overlays Design

## Goal

Overlays should be part of the normal namespace/member construction flow, not a parallel runtime.

The design target is:

- overlay specs are authored as TOML
- TOML is compiled to C data at build time
- no Python overlay code runs at startup
- no direct GLib/GObject helper reimplementation in overlay code
- overridden members still become normal goi function/class objects
- invocation still goes through the normal GI JIT/FFI path

For `GLib.idle_add`, `GLib.timeout_add`, and `GLib.timeout_add_seconds`, this means:

- export the short Python-facing name
- invoke the introspected `*_full` symbol underneath
- apply argument/default remapping before the final GI call


## Implemented: argument defaults

`overlay.defaults(class_name, method_name, **param_defaults)` declares default
values for a method's arguments, so callers can omit the ubiquitous
`flags`/`io_priority` arguments:

```python
overlay.defaults("File", "query_info", flags=Gio.FileQueryInfoFlags.NONE)
# now: file.query_info("standard::name")   # flags defaults, cancellable omitted
```

Notes:

- Trailing nullable arguments (e.g. `cancellable` when it is the last
  parameter) are already omittable by the invoke path, so defaults are mainly
  for non-nullable middle arguments like `flags`. `cancellable` is defaulted
  explicitly only when another argument (e.g. a progress callback) follows it.
- A default is supplied only when the parameter is not passed positionally or
  by keyword, so the descriptor's own duplicate/unknown-argument errors are
  preserved.
- Declare defaults before the class's method overlays (or at module top), since
  `make_method` captures them when the class is built.
- A declared default for a parameter the method does not have is ignored.

This is the declarative form of the "keyword defaults" item in the invoke-path
plan below.

## Non-goals

- mutating loaded typelibs in memory
- a second object model for “overlay callables”
- Python-side startup hooks
- using overlays to hide core marshaling bugs


## Current Problems

The current experimental overlay code is pointed at the wrong layer.

- `LazyNamespace` stores `overlays`
- `lazy.c` checks overlays before normal GI lookup
- `overlays.c` materializes a separate wrapper callable and dispatch path
- old `augment.c` helpers call GLib directly for some APIs

That is too much responsibility in the overlay subsystem.

The overlay subsystem should not:

- own symbol construction
- own a separate invoke path
- reimplement GLib convenience APIs directly in C


## Correct Integration Point

Overlays should plug into normal lazy construction.

Resolution of `namespace.member` should work like this:

1. Namespace is opened normally.
2. During namespace construction, check once whether compiled overlay metadata exists for that `(namespace, version)`.
3. If no compiled overlays exist, store `NULL` and do nothing else.
4. If compiled overlays exist, attach a lightweight pointer to the namespace instance.
5. On first lazy lookup of a member:
   - check the normal cache first
   - if the namespace has no overlay metadata, continue normal GI lookup
   - if the namespace has overlay metadata, look for a matching overlay entry
   - if none exists, continue normal GI lookup
   - if one exists, build the symbol through the normal builder with the overlay descriptor attached
6. Cache the resulting Python object in the namespace cache.
7. All later lookups hit the normal cache.

This keeps overlay cost off the hot path:

- zero extra work for namespaces with no overlays
- one branch for namespaces that do
- one overlay lookup on first construction only


## Lookup Result Structs

The runtime likely needs a small refactor so lazy resolution passes around one lookup result struct instead of raw ad hoc pieces.

That struct should describe what was resolved, independent of whether it came from plain GI metadata or compiled overlay metadata.

Suggested shape:

- `PygirLookupResult`
  - member kind
  - exported name
  - underlying identifier, if redirected
  - `GIBaseInfo *info`
  - optional overlay wrapper metadata

Suggested member kinds:

- namespace member for functions
- namespace member for classes/objects
- namespace member for enums/flags
- namespace member for constants
- class member for methods
- class member for static methods / constructors

In practice the first useful cut is:

- function
- object/class
- enum/flags
- constant

with methods reusing the same callable-oriented sub-structure later.

The important rule is that builders should consume a single resolved description:

- plain GI lookup fills only `info`
- overlay lookup fills `info` plus wrapper metadata
- both paths then call the same builder entry points

This avoids spreading “if overlay” branches through:

- `lazy.c`
- callable builders
- object/class builders
- later class-method lazy lookup

Instead, each lookup site produces one normalized result and construction code consumes it.


## What An Overlay Actually Means

An overlay is metadata that changes how a member is exposed, not a separate implementation.

For function-style overlays, the metadata answers:

- what public name is exported
- what underlying introspected identifier is invoked
- what public parameters exist
- what defaults exist
- what call remapping is needed

The resulting object should still be a normal goi callable descriptor, with extra wrapper metadata attached.

The actual invoke path remains the existing GI call machinery.

For functions and methods, the wrapper metadata should ride along with the normal callable descriptor rather than being executed by a separate overlay object.


## Data Model

One TOML file is used per typelib, for example:

- `src/overlays/GLib-2.0.toml`

Example:

```toml
version = "2.0"

[idle_add]
identifier = "idle_add_full"
params = [
  { function = "required" },
  { user_data = "variadic" },
  { priority = { kind = "keyword", default = "PRIORITY_DEFAULT_IDLE" } },
]
call = { data = { from = "user_data", pack = true }, notify = { value = "none" } }

[timeout_add]
identifier = "timeout_add_full"
params = [
  { interval = "required" },
  { function = "required" },
  { user_data = "variadic" },
  { priority = { kind = "keyword", default = "PRIORITY_DEFAULT" } },
]
call = { data = { from = "user_data", pack = true }, notify = { value = "none" } }

[timeout_add_seconds]
identifier = "timeout_add_seconds_full"
params = [
  { interval = "required" },
  { function = "required" },
  { user_data = "variadic" },
  { priority = { kind = "keyword", default = "PRIORITY_DEFAULT" } },
]
call = { data = { from = "user_data", pack = true }, notify = { value = "none" } }
```


## Runtime Representation

The generator should emit static C data only.

At minimum:

- namespace table
- per-namespace overlay entry array
- per-entry param metadata
- per-entry call remap metadata

The runtime representation should be lookup-oriented, not execution-oriented.

Suggested shape:

- `PygirCompiledOverrideNamespace`
  - namespace name
  - namespace version
  - array of entries
  - entry count
- `PygirOverrideEntry`
  - exported name
  - underlying identifier
  - param descriptors
  - call remap descriptors

The overlay layer should expose lookup helpers, not “execute overlay” helpers.

Separately, lookup normalization should produce a runtime `PygirLookupResult` which points at the overlay entry when one applies.


## Lookup Strategy

Do not mutate typelibs.

Loaded GI typelibs should be treated as immutable.

For generated overlay lookup, start simple:

- static generated arrays
- `strcmp` lookup only when:
  - a namespace with overlays is opened
  - an uncached member in that namespace is resolved

That is already cheap because:

- most namespaces will have no overlays
- member construction is lazy
- constructed members are cached

If overlay count grows later, the generator can switch to:

- sorted arrays + binary search
- generated dispatch by prefix/length
- perfect hash

without changing the rest of the runtime design.

Do not build runtime `GHashTable`s unless measurements show a real need.


## Builders And Invocation

The overlay metadata should be consumed by the normal builders.

For functions:

- namespace lookup returns a `PygirLookupResult`
- if an overlay entry matched, lookup resolves `entry->identifier` with `gi_repository_find_by_name()`
- the result carries the resolved `GIFunctionInfo`
- normal function descriptor is built from that `GIFunctionInfo`
- the descriptor also receives the optional wrapper metadata from the lookup result

At call time:

- normal descriptor/vectorcall entry point runs
- if no wrapper metadata is attached, behave exactly as today
- if wrapper metadata exists, first adapt public arguments into underlying GI arguments
- then continue through the ordinary GI invoke path

This is the important boundary:

- overlay logic is argument adaptation metadata
- GI invocation stays centralized in one place


## Relationship To Augments

Overlays and augments are different tools.

Overlays should cover:

- exported-name redirection
- argument/default remapping
- convenience signatures that still map onto an introspected target

Augments should remain for behaviors that cannot be expressed through the normal GI callable path, such as:

- signal helpers
- APIs that need non-GI runtime behavior
- places where no introspected target exists

For the GLib `*_add` APIs, the intended end state is overlay-based wrapper metadata, not the current direct GLib helper implementation in `augment.c`.


## Required Refactor

The runtime should move from:

- `pygir_override_open()`
- `pygir_override_lookup()`
- `pygir_override_exec()`

to something closer to:

- `pygir_override_lookup_namespace(namespace, version)`
- `pygir_override_lookup_member(namespace_overrides, member_name)`

and then let the normal lazy/builder path do the rest.

Concretely:

1. `PygirLazyNamespace` should hold a pointer to compiled namespace overlay metadata, not an executable overlay handle.
2. `lazy.c` should use overlay metadata only to influence normal member construction.
3. `overlays.c` should become a small lookup module.
4. callable construction should gain optional overlay wrapper metadata.
5. the callable invoke path should apply wrapper remapping before normal GI invocation.


## Immediate Implementation Plan

1. Keep `GLib-2.0.toml` as the first overlay spec file.
2. Keep the generator focused on static metadata emission only.
3. Simplify `overlays.h/.c` to namespace/member lookup helpers.
4. Remove the current separate overlay-execution path from `lazy.c`.
5. Extend function descriptor construction to accept optional overlay metadata.
6. Extend the callable invoke path to apply:
   - keyword defaults
   - variadic packing
   - injected `None`
   - name redirection to the underlying identifier
7. After this works for GLib source helpers, extend the model to more PyGObject compatibility cases where a real wrapper is needed.


## Rule Of Thumb

If a behavior can be expressed as:

- “export this name”
- “invoke that introspected symbol”
- “reshape arguments/defaults first”

then it belongs in compiled overlays.

If it requires behavior that the normal GI invoke path cannot express, it belongs elsewhere.
