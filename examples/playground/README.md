# Pygir Playground

This directory is a draft home for a Swift Playground-style workbench for
pygir. The goal is not only to provide a richer REPL, but to make the
application itself a showcase for the same technologies the bundled examples
teach.

## Package

The playground is an installable package:

```sh
uv run --project src/playground ginext-playground
```

Runtime Python dependencies are declared in `pyproject.toml`:

- `ginext`
- `ginext-gio`
- `ginext-gtk`

The UI source is Blueprint (`playground/ui/*.blp`) with generated `.ui` files
checked in for now. Regenerate after changing Blueprint files:

```sh
blueprint-compiler compile playground/ui/window.blp --output playground/ui/window.ui
blueprint-compiler compile playground/ui/template-row.blp --output playground/ui/template-row.ui
```

## Goals

- Provide an interactive place to explore pygir/PyGObject APIs.
- Keep preview execution isolated from the workbench process.
- Hide preview runner restarts from the user whenever possible.
- Demonstrate real GNOME application patterns in the workbench
  implementation.
- Provide focused gallery examples for individual APIs and idioms.
- Keep optional technologies optional, especially Blueprint, WebKit, and
  Casilda.
- Borrow the best UX ideas from Xcode and Swift Playground: immediate
  feedback, visible runtime state, guided examples, and rich inspection.
- Present the gallery as a polished modern Adwaita application, not as a list
  of scripts.
- Treat AI assistance as part of the normal exploration workflow, with support
  for Claude, Codex, Antigravity, OpenRouter, and bring-your-own LLM backends.
- Make gallery templates extensible, similar to Xcode templates.

## Two Showcase Axes

### Workbench implementation

The playground app should be written as a serious pygir application, not as a
thin script around an editor widget. It should use the technologies we want
users to learn:

- `Adw.Application` or `Gtk.Application` for the app shell.
- `Gio.Action`, menus, accelerators, and command state.
- `Gio.Settings` for preferences and recent state.
- `Gtk.Template` for the main window and reusable UI components.
- Blueprint UI files where the build environment provides the compiler.
- `GResource` for templates, CSS, icons, and built-in snippets.
- `Gio.ListModel`, `Gio.ListStore`, and `Gtk.ListView` for the gallery.
- `GtkSourceView` for source editing when available.
- `Casilda` for embedded isolated preview when available.
- `Gio.Subprocess` plus async stream IO for the runner protocol.
- GLib main loop integration and Python `asyncio` where it clarifies async
  examples.
- An AI integration layer for code changes, explanations, and lab generation.

This makes the workbench itself a reference app and a useful integration
target for pygir runtime behavior.

### Gallery examples

The gallery should contain small runnable labs. Each lab should focus on one
technology or pattern, and should be useful both as teaching material and as a
manual smoke test.

Labs are not read-only examples. They should be starter templates that a user
can begin working from immediately: change values, handlers, widget structure,
async timing, settings keys, or data models and immediately see the result. The
default source should be concise enough to understand, but complete enough to
export into a real application.

Initial gallery candidates:

- GObject subclassing, properties, `notify`, and custom signals.
- Gtk widgets, layout, actions, shortcuts, and application structure.
- `Gtk.Template` and resource-backed UI.
- Blueprint as a friendlier authoring format for complex GTK UI files.
- `Gio.Settings` schemas and live widget binding.
- `Gio.File`, input/output streams, memory streams, and cancellables.
- GLib/Gio async callbacks and Python `asyncio` integration.
- `Gio.ListStore`, `Gio.ListModel`, list factories, and selection models.
- `GLib.Variant` construction and unpacking.
- `GResource` packaging for templates and assets.
- Gdk clipboard, textures, colors, and small event examples.
- Optional WebKit lab when WebKitGTK is importable.

## Template Extensibility

Gallery templates should be extensible. The built-in templates are only the
default catalog; users and projects should be able to add their own templates
without patching the playground itself.

Template sources should be layered:

- **Built-in templates** shipped with the playground.
- **User templates** stored in the user's data directory.
- **Project templates** discovered from the current checkout.
- **Provider templates** installed by optional packages or plugins.
- **AI-generated templates** saved from the AI workflow after review.

Each template should have a small manifest entry:

- stable id
- title
- summary
- technologies used
- required and optional dependencies
- source files
- resources, settings schemas, Blueprint files, or `.ui` files
- thumbnail or screenshot source
- default variant values
- export behavior

The gallery should merge these sources into one catalog and mark unavailable
templates clearly when optional dependencies are missing. User/project templates
should be editable and removable from the workbench; built-in templates should
be copy-on-edit.

This also gives AI-generated work a clean home. A model can propose a new
template, but the workbench should still validate the manifest, show the diff,
run the preview, and only then save it into the user's template catalog.

## AI Integration

AI assistance should be a first-class workflow, not a bolt-on chat window. The
useful loop is: pick a starter template, ask for a focused change, inspect the
patch, run it, and keep iterating with the preview visible.

Initial AI providers should include:

- Claude.
- Codex.
- Antigravity.
- OpenRouter.
- Bring-your-own LLM endpoint.

The workbench should keep provider-specific behavior behind a small adapter
layer. The rest of the app should talk in terms of requests like "explain this
lab", "modify this template", "fix this diagnostic", or "create a new lab",
not in terms of one provider's API shape.

Core AI workflows:

- **Explain current lab**: summarize the API concepts used by the selected
  template and connect them to the visible preview.
- **Make a focused change**: generate a patch against the editable source, such
  as "add a filter entry", "make this async", or "bind this to settings".
- **Fix diagnostics**: include source, traceback, stdout/stderr, and dependency
  state so the model can propose a narrow correction.
- **Generate a variant**: produce a new lab variant from the current template
  while preserving the original.
- **Create a starter template**: generate a new gallery entry with source,
  metadata, dependency declarations, and a preview thumbnail plan.
- **Ask about APIs**: answer questions using available GI metadata, docs, and
  the current source context.

AI edits should be inspectable before they are applied. The default should be a
diff view with apply/discard actions, followed by a preview reload after apply.
For small safe changes, the app can later offer an auto-apply mode, but the
first version should optimize for trust and clear review.

Context sent to an AI provider should be explicit and bounded:

- Current lab metadata and source.
- Selected text or selected object metadata when relevant.
- Current diagnostics and recent output.
- Dependency availability.
- API metadata and docs snippets once the docs lookup exists.
- A short description of the current preview state, not arbitrary process
  memory.

Provider configuration should live in workbench settings. Secrets must not be
stored in gallery templates or exported examples. The bring-your-own backend
should allow at least a base URL, model name, API key source, and provider
profile describing whether the backend supports chat, tool calls, streaming,
and patch output.

## Experience Direction

The playground should feel closer to Swift Playground than to a terminal REPL.
The important idea is not syntax magic; it is that code, results, state, and
documentation sit next to each other while the user explores.

The outer shell should feel like a modern Adwaita app: quiet chrome, clear
navigation, strong typography, predictable controls, and no demo-app clutter.
The first screen should be the usable workbench, not a landing page.

The gallery should have rich visual entries. Each lab should provide a preview
image or generated screenshot showing the expected result, plus concise metadata
such as title, technologies used, optional dependencies, and difficulty. Gallery
cards should be for selecting real runnable labs, not marketing tiles.

Borrowed UX ideas worth adapting:

- **Run visible slices**: each lab should have a clear run button, reset button,
  and execution state. Running code should update the preview and output panes
  without making the user reconstruct state manually.
- **Starter templates**: every gallery item should open as editable source that
  is already useful as the seed of a small application or feature.
- **Editable examples**: changing the code is part of the main workflow. The
  source pane should be writable by default, with clear actions to restore the
  original lab source or save a copy.
- **Inline results**: simple expression results, printed output, warnings, and
  errors should be connected back to source locations where possible.
- **Live preview**: widget-producing code should show an actual GTK preview, not
  only textual output. The preview should stay visible while the source changes.
- **Preview thumbnails**: gallery entries should use screenshots captured from
  the labs where possible, so users can choose by visual result as well as API
  topic.
- **Timeline/output area**: async examples need a structured event log so users
  can see callbacks, cancellations, stream reads, timeouts, and task completion
  in order.
- **Object inspector**: selected preview objects should expose type, GType,
  properties, signals, actions, and implemented interfaces. Property editing can
  come later, but read-only inspection should be part of the core experience.
- **Guided labs**: examples should include a short task flow and editable code,
  not just static snippets. A user should be able to tweak values and immediately
  see what changed.
- **Variant controls**: common tweak points can be exposed as small controls
  next to the editor, such as colors, delays, list sizes, selected file paths, or
  settings values. These controls should update the source or runner state in a
  transparent way so the user still learns the underlying API.
- **AI-assisted iteration**: a user should be able to request a small change,
  review the generated diff, apply it, and reload the preview without leaving
  the workbench.
- **Rich diagnostics**: tracebacks should be readable, source-linked, and kept
  out of the preview area. Runtime errors are part of exploration, not a modal
  failure state.
- **Reset as a first-class action**: because GObject state is sticky, the UI
  should make it obvious when a fresh runner has been started.
- **Invisible runner reloads**: the workbench should be able to restart the
  preview process without making the user feel like the whole playground reset.
  The last rendered frame should remain visible until the new runner produces a
  replacement frame.
- **Progressive disclosure**: the first view should be useful without knowing
  GI terminology, while inspectors and metadata panels should expose the deeper
  binding details for advanced users.
- **Shareable examples**: a lab should eventually be exportable as a standalone
  Python file or a small project skeleton.
- **Extensible gallery**: templates should come from layered catalogs so users,
  projects, optional packages, and AI workflows can add new starting points.

The app can borrow from IDEs, but the first implementation should stay focused
on the preview/gallery workflow: choose a starter template, inspect its result,
edit a small amount of code, and reload the preview. Project management,
debugging, packaging, and large-file editing can stay out of scope unless they
directly support that loop.

The primary workflow should be:

1. Browse a visual gallery of starter templates.
2. Open a template into the workbench.
3. See the rendered preview immediately.
4. Edit the source or tweak exposed variant controls.
5. Reload invisibly when possible, preserving the last frame and workbench
   state.
6. Save/export the edited template once it becomes useful.

## Architecture Draft

The app should have two cooperating processes:

1. The workbench process owns the application UI, editor, gallery, inspector,
   output panels, settings, and command actions.
2. The runner process imports pygir, executes the selected lab or user code,
   creates preview widgets/windows, and reports structured state back to the
   workbench.

The process split is intentional. User code can register GTypes, connect
signals, block the main loop, leak state, or crash. Restarting a child process
is a much clearer reset model than trying to unload arbitrary GObject and
Python state from the workbench process.

The restart model should still feel continuous. The workbench owns durable UI
state: selected lab, source buffer, scroll positions, inspector selection,
settings, output history, and the last successful preview metadata. The runner
owns disposable execution state: imported modules, registered types, live
widgets, connected signals, and pending async operations. When the runner is
restarted, the workbench should replay the selected lab/source and restore the
visible workbench state around it.

Preview reloads should use a double-buffered handoff:

1. Keep the old preview surface or a captured last frame visible.
2. Start a fresh runner and replay the current source.
3. Wait for `preview-ready` from the new runner.
4. Swap the embedded preview to the new runner.
5. Tear down the old runner after the new preview is visible.

If a true old surface cannot stay alive during handoff, the fallback should be
a still snapshot of the last rendered frame with a small busy indicator. The
user should see continuity first and process mechanics second.

When Casilda is available, the runner should create a normal GTK window and
connect to the Casilda compositor socket exposed by the workbench. The preview
then appears embedded in the main playground window. Without Casilda, the
runner can fall back to a separate preview window.

The protocol between workbench and runner should start small and structured:

- `run`: execute a lab or user source buffer.
- `reset`: terminate the current runner and start a fresh one.
- `reload`: start a fresh runner, replay the current source, and swap previews
  only after the new runner is ready.
- `stdout` / `stderr`: stream process output.
- `ready`: runner imported dependencies and is ready for commands.
- `preview-ready`: runner created a preview window.
- `snapshot`: runner provides or confirms a last-frame fallback for reload.
- `selected-object`: runner reports the current object id and type.
- `inspect-object`: workbench asks for properties, signals, methods, and type
  metadata for an object id.
- `diagnostic`: syntax/runtime errors with line and traceback information.
- `lab-metadata`: title, description, technologies, dependencies, thumbnail,
  and editable defaults for a gallery lab.
- `lab-state`: current edited source, dirty state, selected variant controls,
  and last successful run metadata.
- `ai-request`: bounded context for explanation, patch generation, diagnostic
  repair, or new-template generation.
- `ai-patch`: proposed source and metadata changes that can be reviewed before
  applying.

JSON over stdin/stdout is enough for the first version. A socket can come later
if the protocol needs independent output channels or binary payloads.

## Rough Module Layout

```text
src/playground/
  README.md
  playground/
    __init__.py
    app.py
    window.py
    actions.py
    settings.py
    resources.py
    runner.py
    protocol.py
    inspector.py
    gallery.py
    lab_state.py
    templates.py
    ai.py
    dependencies.py
    ui/
      window.blp
      window.ui
      preferences.blp
      preferences.ui
      inspector.blp
      inspector.ui
    data/
      playground.gresource.xml
      org.ginext.playground.gschema.xml
      style.css
      thumbnails/
    labs/
      manifest.json
      gobject_properties.py
      gtk_template.py
      blueprint.py
      gio_settings.py
      gio_streams.py
      gio_async.py
      list_model.py
      gresource.py
      webkit.py
    ai/
      providers.py
      context.py
      patch.py
    templates/
      loader.py
      manifest.py
      catalog.py
  runner/
    __init__.py
    __main__.py
    execute.py
    preview.py
    inspect.py
```

The exact package shape can change once this is wired into the build, but the
separation should stay: workbench UI code on one side, runner execution code on
the other.

## MVP

The first useful slice should avoid completion and deep documentation support.
Those are valuable, but they should not block proving the architecture.

1. Adwaita/Gtk application shell with a visual gallery, editor, preview, and
   output panes.
2. Built-in starter templates loaded from resources or package data.
3. Visual gallery entries backed by template metadata and preview thumbnails.
4. Writable source buffer with restore-original and save-copy support.
5. Runner process managed through `Gio.Subprocess`.
6. Async stdout/stderr/protocol reading.
7. Preview embedded through Casilda when available, with a separate-window
   fallback.
8. Dependency detection for `Adw`, `GtkSourceView`, Blueprint, `Casilda`, and
   WebKitGTK.
9. Five initial starter templates: Gtk basics, GObject properties/signals,
   `Gtk.Template`, `Gio.Settings`, and Gio async/streams.
10. AI provider configuration and one patch-based workflow: "make a focused
    change to this template".
11. Template catalog loading from built-in and user template directories.

## Later Work

- GI-aware completion in GtkSourceView.
- Inline docs using the future runtime docs lookup path.
- AI explanation, diagnostic repair, and new-template generation.
- Blueprint-backed labs and template editing.
- Object inspector with live property editing.
- Signal monitor and action inspector.
- Snapshot/smoke runner for selected gallery examples.
- Snippet save/export/import.
- WebKit and GStreamer optional labs.
- Hot reload support once the runtime has a reliable reload story.

## Open Questions

- Should the playground live as a first-party example, a separately installable
  package, or both?
- Should gallery labs be plain Python files, structured metadata, or a small
  manifest plus source file?
- What should the stable template manifest schema look like, and how much of
  it should be treated as public?
- How much of the runner protocol should be considered public or stable?
- Should optional dependencies be represented as disabled gallery entries or
  hidden entirely when unavailable?
- Should Blueprint be required for building the playground from source, or
  should generated `.ui` files be checked in so the runtime remains usable
  without the compiler?
- Should AI provider integrations live in the playground package, or should
  they be separate optional packages so provider dependencies stay isolated?
- What is the minimum common patch format for Claude, Codex, Antigravity,
  OpenRouter, and bring-your-own backends?
- How should settings schemas and resources be compiled for local development
  without making the example hard to run from the checkout?
