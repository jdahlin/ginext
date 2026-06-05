# Gsk (render nodes)

> GTK4's render layer. Widgets emit *render nodes* (a tree of drawing operations) rather than calling Cairo directly. Most app developers never touch this — but if you write custom widgets or push GTK hard, you'll meet it.

## What this chapter covers

- The model: a render-node tree per frame; the renderer (GL or Vulkan) walks it.
- `Gtk.Snapshot`: the API for emitting render nodes. Replaces GTK3's `draw` signal.
- The node types:
    - `ColorNode`, `LinearGradientNode`, `RadialGradientNode`.
    - `BorderNode`, `OutsetShadowNode`, `InsetShadowNode`.
    - `TextureNode`, `TextNode`, `BlurNode`, `OpacityNode`, `ClipNode`, `RoundedClipNode`, `TransformNode`.
    - `CairoNode` — escape hatch for Cairo drawing inside the render graph.
- When to use Gsk directly: custom widgets with GPU-friendly operations (gradients, blurs, transforms).
- Mixing Cairo and Gsk: use Cairo where Cairo is better; wrap in a `CairoNode`.
- Renderer selection (`GSK_RENDERER` env var) and what to test against.
- Performance characteristics: GPU draw is fast for simple primitives; Cairo nodes hit a slower path.

## What you'll be able to do

- Emit render nodes from a custom widget.
- Pick GPU-friendly primitives where possible.
- Diagnose "this is slow" custom widgets by counting nodes.

## Notes for the writer

- Advanced. Many readers will skip. That's fine.
- Cross-link to [Custom widgets](custom-widgets.md) which is where readers first hit `Gtk.Snapshot`.
