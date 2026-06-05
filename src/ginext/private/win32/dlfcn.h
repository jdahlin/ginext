/* Minimal <dlfcn.h> shim for Windows.
 *
 * ginext resolves GObject-introspection C symbols (and a few cairo helpers) at
 * runtime via dlsym(RTLD_DEFAULT, name). POSIX dlopen/dlsym/dlclose/dlerror do
 * not exist on Windows, so this header provides just enough of the surface that
 * ginext uses, backed by LoadLibrary/GetProcAddress and an enumeration of the
 * process's already-loaded modules for the RTLD_DEFAULT case.
 *
 * This file is only on the include path for Windows builds (see src/meson.build),
 * so `#include <dlfcn.h>` resolves here on Windows and to the real header
 * elsewhere.
 */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

/* RTLD_DEFAULT: search every module currently loaded in the process. */
#define RTLD_DEFAULT ((void *)0)
#define RTLD_NEXT    ((void *)-1)
#define RTLD_LAZY    0x0001
#define RTLD_NOW     0x0002
#define RTLD_GLOBAL  0x0100
#define RTLD_LOCAL   0x0000

void *dlopen (const char *filename, int flags);
int dlclose (void *handle);
void *dlsym (void *handle, const char *symbol);
char *dlerror (void);

#ifdef __cplusplus
}
#endif
