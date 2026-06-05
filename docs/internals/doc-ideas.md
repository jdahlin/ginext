# Documentation site — ideas & plan

Brainstorming for a goi documentation site. Mostly user-facing (tutorial,
gallery, examples) with some developer-focused material.

## Tooling: MkDocs + Material

MkDocs with the Material theme is the leading candidate. It's what FastAPI uses
and gives a polished look with minimal config. Markdown-first, good built-ins
for tutorials/galleries (admonitions, tabs, code annotations, content tabs for
multi-language examples).

Tradeoffs vs alternatives:

- **vs Sphinx**: MkDocs is simpler and prettier out of the box. Sphinx
  traditionally wins on Python API autodoc, but `mkdocstrings[python]` closes
  most of that gap and would let us pull API docs from the `goi/` package
  automatically while writing narrative content in markdown.
- **vs Starlight/Docusaurus**: nicer for very interactive sites, but pull in a
  JS toolchain we don't want.

## Interactive in-browser examples (WASM)

We have a separate tree that builds GTK + Python + goi to WASM. Once that
lands, interactive examples in the docs become viable. First-visit download
will be heavy, but subsequent loads can be cached.

Existing MkDocs plugins for in-browser Python (`mkdocs-pyodide`, PyScript
snippets, JupyterLite embeds) all assume Pyodide as the runtime — they'd fight
our custom GTK+Python WASM bundle. Better to roll our own integration.

### Integration shape

1. **Custom MkDocs hook + fenced-code extension.** A hook that recognizes
   ` ```python {.goi-run} ` fences and emits a
   `<div class="goi-run" data-src="...">` placeholder with the code. One JS
   bundle on the page hydrates all placeholders with an editor + "Run" button.
   Material's `pymdownx.superfences` makes the custom fence trivial.

2. **One shared runtime per page (or per site).** Boot the WASM runtime once
   in a hidden iframe or dedicated worker; examples `postMessage` their code
   in and get framebuffer/stdout back. Avoids re-initializing GTK per snippet.

3. **Service Worker for the big download.** Cache WASM + typelibs + Python
   stdlib with versioned URLs so the first visit is the only slow one. Crib
   the JupyterLite/marimo-WASM cache-busting approach (hash in filename, long
   `Cache-Control`).

4. **Editor: CodeMirror 6.** Lighter than Monaco, plays nicely with Material's
   theming. No IntelliSense needed for short example snippets.

5. **Render target.** If the WASM build paints into a canvas, expose that
   canvas to the page; the "Run" button swaps the example's canvas in. For
   headless examples, capture stdout into a `<pre>`.

### Nice-to-haves

- "Open in full playground" link on each snippet, opening a dedicated
  `/playground/?gist=...` page with a larger editor and persistent state.
  Cheap once the runtime-hosting iframe exists.

## Fallbacks (before WASM is ready, or for content where WASM is overkill)

- Static + copy-button code blocks (Material default).
- Asciinema casts for terminal/REPL flows.
- Screenshots and short clips of the GTK example apps actually running — for
  a GUI binding, seeing the result matters more than editing in-browser.
- GitHub Codespaces / devcontainer "Open in" badge per example. One click
  spins up a full Linux env with GTK and toolchain — closest thing to
  "StackBlitz for native code."
- `mkdocs-jupyter` for tutorial notebooks if we want narrative + code cells
  executed at build time (not interactive in-browser, but renders nicely).

## Content shape (rough)

- **Tutorial** — guided intro, "your first GTK app with goi."
- **Gallery** — screenshots of the ported example apps under `apps/`, each
  linking to a short walkthrough + source.
- **How-to recipes** — signals, properties, templates, GObject subclassing,
  async/Gio, etc.
- **API reference** — auto-generated via `mkdocstrings` from `goi/`.
- **Developer docs** — invoke plans, overlays, JIT internals; can link to /
  pull from existing `docs/*.md`.

## Open questions

- Where does the doc site live (subdir, separate repo, gh-pages branch)?
- Versioning: `mike` for multi-version docs once we cut releases?
- Search: Material's built-in vs Algolia DocSearch.
