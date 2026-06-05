/*
 * goi-bench: a tiny GObject-introspectable typelib of no-op functions
 * with controlled signature shapes. Used by examples/draw-bench/microbench.py
 * to measure pygir's per-call invoke overhead without GTK / GLib internal
 * machinery contaminating the numbers.
 *
 * Every function's body is `return first-arg` (or void return). C-side cost
 * is one mov + ret, so wall-clock per call ≈ pygir / PyGObject overhead.
 */
#pragma once
#include <glib.h>

#ifdef _WIN32
#ifdef GOI_BENCH_BUILDING
#define GOI_BENCH_API __declspec (dllexport)
#else
#define GOI_BENCH_API __declspec (dllimport)
#endif
#else
#define GOI_BENCH_API __attribute__ ((visibility ("default")))
#endif

/**
 * goi_bench_noop_void:
 *
 * 0 args, void return. Baseline call overhead.
 */
GOI_BENCH_API void
goi_bench_noop_void (void);

/**
 * goi_bench_noop_int:
 *
 * 0 args, int return. Baseline + return-marshal cost.
 *
 * Returns: 0
 */
GOI_BENCH_API gint
goi_bench_noop_int (void);

/**
 * goi_bench_in_1_int:
 * @a:
 *
 * 1 IN int → int. Single-arg-marshal baseline.
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_1_int (gint a);

/**
 * goi_bench_in_2_int:
 * @a:
 * @b:
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_2_int (gint a, gint b);

/**
 * goi_bench_in_3_int:
 * @a:
 * @b:
 * @c:
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_3_int (gint a, gint b, gint c);

/**
 * goi_bench_in_4_int:
 * @a:
 * @b:
 * @c:
 * @d:
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_4_int (gint a, gint b, gint c, gint d);

/**
 * goi_bench_in_5_int:
 * @a:
 * @b:
 * @c:
 * @d:
 * @e:
 *
 * 5 IN int args (last one spills off SysV's 6-int-register window once
 * self/this fills rdi). Body: `return a;`
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_5_int (gint a, gint b, gint c, gint d, gint e);

/**
 * goi_bench_in_6_int:
 * @a:
 * @b:
 * @c:
 * @d:
 * @e:
 * @f:
 *
 * 6 IN int args (fills the SysV register window).
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_6_int (gint a, gint b, gint c, gint d, gint e, gint f);

/**
 * goi_bench_in_5_mixed:
 * @a:
 * @b:
 * @c:
 * @d:
 * @e:
 *
 * Mixed scalar shapes (i32/i64/double/i32/u32). Tests the FFI register
 * lane mux (integer vs xmm).
 *
 * Returns: @a
 */
GOI_BENCH_API gint
goi_bench_in_5_mixed (gint a, gint64 b, gdouble c, gint d, guint e);

/**
 * GoiBenchCallbackNoArgs:
 *
 * Callback with the smallest possible C->Python closure shape.
 */
typedef void (*GoiBenchCallbackNoArgs) (void);

/**
 * GoiBenchCallbackInt:
 * @value:
 *
 * Scalar argument plus scalar return.
 *
 * Returns: callback result
 */
typedef gint (*GoiBenchCallbackInt) (gint value);

/**
 * GoiBenchCallbackOutInt:
 * @value:
 * @out_value: (out):
 *
 * Scalar argument plus OUT-parameter writeback.
 */
typedef void (*GoiBenchCallbackOutInt) (gint value, gint *out_value);

/**
 * GoiBenchCallbackMixed:
 * @a:
 * @b:
 * @c:
 * @flag:
 * @text:
 *
 * Mixed integer, floating point, boolean, and pointer lanes.
 *
 * Returns: callback result
 */
typedef gint (
    *GoiBenchCallbackMixed) (gint a, gint64 b, gdouble c, gboolean flag, const char *text);

/**
 * GoiBenchCallbackWithUserData:
 * @value:
 * @user_data: (closure):
 *
 * Callback with explicit closure data.
 *
 * Returns: callback result
 */
typedef gint (*GoiBenchCallbackWithUserData) (gint value, gpointer user_data);

/**
 * goi_bench_callback_no_args_loop:
 * @callback: (scope call):
 * @n:
 *
 * Calls @callback @n times from C and returns the number of invocations.
 *
 * Returns: invocation count
 */
GOI_BENCH_API gint
goi_bench_callback_no_args_loop (GoiBenchCallbackNoArgs callback, gint n);

/**
 * goi_bench_callback_int_loop:
 * @callback: (scope call):
 * @n:
 *
 * Calls @callback with an int argument @n times and accumulates int returns.
 *
 * Returns: accumulated callback results
 */
GOI_BENCH_API gint64
goi_bench_callback_int_loop (GoiBenchCallbackInt callback, gint n);

/**
 * goi_bench_callback_out_int_loop:
 * @callback: (scope call):
 * @n:
 *
 * Calls @callback with an int argument and one int OUT parameter @n times.
 *
 * Returns: accumulated OUT values
 */
GOI_BENCH_API gint64
goi_bench_callback_out_int_loop (GoiBenchCallbackOutInt callback, gint n);

/**
 * goi_bench_callback_mixed_loop:
 * @callback: (scope call):
 * @n:
 *
 * Calls @callback with mixed scalar and pointer lanes @n times.
 *
 * Returns: accumulated callback results
 */
GOI_BENCH_API gint64
goi_bench_callback_mixed_loop (GoiBenchCallbackMixed callback, gint n);

/**
 * goi_bench_callback_user_data_loop:
 * @callback: (scope call) (closure user_data):
 * @user_data:
 * @n:
 *
 * Calls @callback with explicit user-data closure @n times.
 *
 * Returns: accumulated callback results
 */
GOI_BENCH_API gint64
goi_bench_callback_user_data_loop (GoiBenchCallbackWithUserData callback,
                                   gpointer user_data,
                                   gint n);

/* ---------------------------------------------------------------------- */
/* GoiBenchObject — a minimal GObject for benching the call shapes that */
/* dominate real GUI traces (drawing-app sample 2026-05-10):              */
/*   set_enabled(action, bool) → void          ~ 12 hits                  */
/*   lookup_action(win, str)   → GObject       ~  6 hits                  */
/*   set_label(widget, str)    → void          ~  5 hits                  */
/*   get_current_page(nb)      → int           ~  4 hits                  */
/*   get_nth_page(nb, int)     → GObject       ~  3 hits                  */
/*                                                                        */
/* Method bodies are stubs (return `self`, `self->index`, or no-op) so    */
/* wall-clock per call ≈ pygir/PyGObject dispatch + marshal overhead.     */
/* Signal "tick" + int property "value" carry the closure / property     */
/* benches. No fields are exposed on the instance struct — those go on    */
/* GoiBench.Box (a separate boxed type) once it lands.                  */
/* ---------------------------------------------------------------------- */

#include <glib-object.h>

#define GOI_BENCH_TYPE_OBJECT (goi_bench_object_get_type ())

GOI_BENCH_API
G_DECLARE_FINAL_TYPE (GoiBenchObject, goi_bench_object, GOI_BENCH, OBJECT, GObject)

GOI_BENCH_API GoiBenchObject *
goi_bench_object_new (void);

/**
 * goi_bench_object_set_flag:
 * @self:
 * @v:
 *
 * (self, bool) → void. Mirrors `Gio.SimpleAction.set_enabled`.
 */
GOI_BENCH_API void
goi_bench_object_set_flag (GoiBenchObject *self, gboolean v);

/**
 * goi_bench_object_set_label:
 * @self:
 * @s: (nullable):
 *
 * (self, utf8?) → void. Mirrors `Gtk.Label.set_label` /
 * `Gtk.Widget.set_tooltip_text` (nullable string).
 */
GOI_BENCH_API void
goi_bench_object_set_label (GoiBenchObject *self, const char *s);

/**
 * goi_bench_object_get_label:
 * @self:
 *
 * (self) → utf8. Borrowed return.
 *
 * Returns: (nullable) (transfer none):
 */
GOI_BENCH_API const char *
goi_bench_object_get_label (GoiBenchObject *self);

/**
 * goi_bench_object_lookup:
 * @self:
 * @name:
 *
 * (self, utf8) → GObject. Mirrors `Gtk.Window.lookup_action`. Always
 * returns @self (transfer none) so we measure dispatch, not lookup cost.
 *
 * Returns: (transfer none):
 */
GOI_BENCH_API GoiBenchObject *
goi_bench_object_lookup (GoiBenchObject *self, const char *name);

/**
 * goi_bench_object_get_index:
 * @self:
 *
 * (self) → int. Mirrors `Gtk.Notebook.get_current_page` /
 * `GdkPixbuf.Pixbuf.get_width`.
 */
GOI_BENCH_API gint
goi_bench_object_get_index (GoiBenchObject *self);

/**
 * goi_bench_object_nth:
 * @self:
 * @i:
 *
 * (self, int) → GObject. Mirrors `Gtk.Notebook.get_nth_page`.
 *
 * Returns: (transfer none):
 */
GOI_BENCH_API GoiBenchObject *
goi_bench_object_nth (GoiBenchObject *self, gint i);

/**
 * goi_bench_object_index_of:
 * @self:
 * @child:
 *
 * (self, GObject) → int. Mirrors `Gtk.Notebook.page_num`.
 */
GOI_BENCH_API gint
goi_bench_object_index_of (GoiBenchObject *self, GoiBenchObject *child);

/**
 * goi_bench_object_children:
 * @self:
 *
 * (self) → GList<GoiBenchObject>. Mirrors `Gtk.Notebook.get_children`.
 * Not yet covered by the narrow JIT — drives the GList specialization
 * phase.
 *
 * Returns: (transfer container) (element-type GoiBenchObject):
 */
GOI_BENCH_API GList *
goi_bench_object_children (GoiBenchObject *self);

/**
 * goi_bench_g_object_get_int_loop:
 * @obj:
 * @name:
 * @n:
 *
 * Repeatedly reads int property @name with `g_object_get()` and accumulates
 * the results. Used to benchmark and validate Python-defined property access
 * through the native GObject property machinery.
 *
 * Returns: accumulated property values
 */
GOI_BENCH_API gint64
goi_bench_g_object_get_int_loop (GObject *obj, const char *name, gint n);

/**
 * goi_bench_object_tick:
 * @self:
 *
 * Emit the "tick" signal. (self) → void.
 */
GOI_BENCH_API void
goi_bench_object_tick (GoiBenchObject *self);
