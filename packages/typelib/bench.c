#define GOI_BENCH_BUILDING 1
#include "bench.h"

void
goi_bench_noop_void (void)
{
}
gint
goi_bench_noop_int (void)
{
  return 0;
}
gint
goi_bench_in_1_int (gint a)
{
  return a;
}
gint
goi_bench_in_2_int (gint a, gint b)
{
  (void)b;
  return a;
}
gint
goi_bench_in_3_int (gint a, gint b, gint c)
{
  (void)b;
  (void)c;
  return a;
}
gint
goi_bench_in_4_int (gint a, gint b, gint c, gint d)
{
  (void)b;
  (void)c;
  (void)d;
  return a;
}
gint
goi_bench_in_5_int (gint a, gint b, gint c, gint d, gint e)
{
  (void)b;
  (void)c;
  (void)d;
  (void)e;
  return a;
}
gint
goi_bench_in_6_int (gint a, gint b, gint c, gint d, gint e, gint f)
{
  (void)b;
  (void)c;
  (void)d;
  (void)e;
  (void)f;
  return a;
}
gint
goi_bench_in_5_mixed (gint a, gint64 b, gdouble c, gint d, guint e)
{
  (void)b;
  (void)c;
  (void)d;
  (void)e;
  return a;
}

gint
goi_bench_callback_no_args_loop (GoiBenchCallbackNoArgs callback, gint n)
{
  gint count = 0;

  if (callback == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    {
      callback ();
      count++;
    }

  return count;
}

gint64
goi_bench_callback_int_loop (GoiBenchCallbackInt callback, gint n)
{
  gint64 sum = 0;

  if (callback == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    sum += callback (i);

  return sum;
}

gint64
goi_bench_callback_out_int_loop (GoiBenchCallbackOutInt callback, gint n)
{
  gint64 sum = 0;

  if (callback == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    {
      gint out_value = 0;
      callback (i, &out_value);
      sum += out_value;
    }

  return sum;
}

gint64
goi_bench_callback_mixed_loop (GoiBenchCallbackMixed callback, gint n)
{
  gint64 sum = 0;

  if (callback == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    sum += callback (i, (gint64)i * 2, (gdouble)i + 0.5, (i & 1) == 0, "bench");

  return sum;
}

gint64
goi_bench_callback_user_data_loop (GoiBenchCallbackWithUserData callback,
                                   gpointer user_data,
                                   gint n)
{
  gint64 sum = 0;

  if (callback == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    sum += callback (i, user_data);

  return sum;
}

/* ---------------------------------------------------------------------- */
/* GoiBenchObject                                                       */
/* ---------------------------------------------------------------------- */

struct _GoiBenchObject
{
  GObject parent_instance;
  gboolean flag;
  gint value;
  gint index;
  char *label;
};

G_DEFINE_TYPE (GoiBenchObject, goi_bench_object, G_TYPE_OBJECT)

enum
{
  PROP_0,
  PROP_VALUE,
  N_PROPS,
};

enum
{
  SIG_TICK,
  N_SIGNALS,
};

static GParamSpec *goi_bench_object_props[N_PROPS];
static guint goi_bench_object_signals[N_SIGNALS];

static void
goi_bench_object_init (GoiBenchObject *self)
{
  self->flag = FALSE;
  self->value = 0;
  self->index = 0;
  self->label = NULL;
}

static void
goi_bench_object_finalize (GObject *gobject)
{
  GoiBenchObject *self = (GoiBenchObject *)gobject;
  g_free (self->label);
  G_OBJECT_CLASS (goi_bench_object_parent_class)->finalize (gobject);
}

static void
goi_bench_object_get_property (GObject *gobject, guint prop_id, GValue *value, GParamSpec *pspec)
{
  GoiBenchObject *self = (GoiBenchObject *)gobject;
  switch (prop_id)
    {
    case PROP_VALUE:
      g_value_set_int (value, self->value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (gobject, prop_id, pspec);
    }
}

static void
goi_bench_object_set_property (GObject *gobject,
                               guint prop_id,
                               const GValue *value,
                               GParamSpec *pspec)
{
  GoiBenchObject *self = (GoiBenchObject *)gobject;
  switch (prop_id)
    {
    case PROP_VALUE:
      self->value = g_value_get_int (value);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (gobject, prop_id, pspec);
    }
}

static void
goi_bench_object_class_init (GoiBenchObjectClass *klass)
{
  GObjectClass *object_class = G_OBJECT_CLASS (klass);
  object_class->finalize = goi_bench_object_finalize;
  object_class->get_property = goi_bench_object_get_property;
  object_class->set_property = goi_bench_object_set_property;

  goi_bench_object_props[PROP_VALUE]
      = g_param_spec_int ("value",
                          "value",
                          "Integer property for prop_bench",
                          G_MININT,
                          G_MAXINT,
                          0,
                          G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS);
  g_object_class_install_properties (object_class, N_PROPS, goi_bench_object_props);

  goi_bench_object_signals[SIG_TICK] = g_signal_new ("tick",
                                                     GOI_BENCH_TYPE_OBJECT,
                                                     G_SIGNAL_RUN_LAST,
                                                     0,
                                                     NULL,
                                                     NULL,
                                                     NULL,
                                                     G_TYPE_NONE,
                                                     0);
}

GoiBenchObject *
goi_bench_object_new (void)
{
  return g_object_new (GOI_BENCH_TYPE_OBJECT, NULL);
}

void
goi_bench_object_set_flag (GoiBenchObject *self, gboolean v)
{
  self->flag = v;
}

void
goi_bench_object_set_label (GoiBenchObject *self, const char *s)
{
  char *old = self->label;
  self->label = s ? g_strdup (s) : NULL;
  g_free (old);
}

const char *
goi_bench_object_get_label (GoiBenchObject *self)
{
  return self->label;
}

GoiBenchObject *
goi_bench_object_lookup (GoiBenchObject *self, const char *name)
{
  (void)name;
  return self;
}

gint
goi_bench_object_get_index (GoiBenchObject *self)
{
  return self->index;
}

GoiBenchObject *
goi_bench_object_nth (GoiBenchObject *self, gint i)
{
  (void)i;
  return self;
}

gint
goi_bench_object_index_of (GoiBenchObject *self, GoiBenchObject *child)
{
  return (self == child) ? 0 : -1;
}

GList *
goi_bench_object_children (GoiBenchObject *self)
{
  return g_list_prepend (NULL, self);
}

gint64
goi_bench_g_object_get_int_loop (GObject *obj, const char *name, gint n)
{
  gint64 sum = 0;

  if (obj == NULL || name == NULL || n <= 0)
    return 0;

  for (gint i = 0; i < n; i++)
    {
      /* The declared Python `int` property is registered as G_TYPE_INT64, so
         g_object_get collects 8 bytes — read into a gint64, not a gint, or it
         overruns the stack slot (caught as a fast-fail under MSVC /GS). */
      gint64 value = 0;
      g_object_get (obj, name, &value, NULL);
      sum += value;
    }

  return sum;
}

void
goi_bench_object_tick (GoiBenchObject *self)
{
  g_signal_emit (self, goi_bench_object_signals[SIG_TICK], 0);
}
