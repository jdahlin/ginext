#ifndef GINEXT_PROPERTY_DESCR_H
#define GINEXT_PROPERTY_DESCR_H

#include "common.h"

extern PyTypeObject GinextPropertyDescriptorType;

PyObject *
pygi_declared_property_new_full (PyObject *spec,
                                 PyObject *owner,
                                 PyObject *prop_id_obj,
                                 PyObject *pspec_obj,
                                 int coerce_gtype_int);

#endif /* GINEXT_PROPERTY_DESCR_H */
