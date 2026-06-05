#ifndef GINEXT_DECLARED_PROPERTY_H
#define GINEXT_DECLARED_PROPERTY_H

#include "common.h"

extern PyTypeObject GinextDeclaredPropertyType;

PyObject *
pygi_declared_property_new_full (PyObject *spec,
                                 PyObject *owner,
                                 PyObject *prop_id_obj,
                                 PyObject *pspec_obj,
                                 int coerce_gtype_int);

#endif /* GINEXT_DECLARED_PROPERTY_H */
