/* Windows backing for the minimal <dlfcn.h> shim (see dlfcn.h). */
#include <dlfcn.h>

#include <windows.h>
#include <psapi.h>

static char dl_last_error[256];

void *
dlopen (const char *filename, int flags)
{
  (void)flags;
  if (filename == NULL)
    return GetModuleHandleW (NULL);
  /* Search the directories registered via os.add_dll_directory()
     (LOAD_LIBRARY_SEARCH_DEFAULT_DIRS covers them, plus the app dir and
     system32) so loading a typelib's shared library by bare name finds DLLs
     in a GTK/runtime dir the embedder added — POSIX dlopen-by-soname relies on
     a configured search path, and plain LoadLibraryA does not consult those.
     Fall back to the standard PATH-based search. */
  HMODULE h = LoadLibraryExA (filename, NULL, LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
  if (h == NULL)
    h = LoadLibraryA (filename);
  return (void *)h;
}

int
dlclose (void *handle)
{
  if (handle == NULL)
    return 0;
  return FreeLibrary ((HMODULE)handle) ? 0 : -1;
}

void *
dlsym (void *handle, const char *symbol)
{
  if (handle != RTLD_DEFAULT && handle != RTLD_NEXT)
    return (void *)GetProcAddress ((HMODULE)handle, symbol);

  /* RTLD_DEFAULT / RTLD_NEXT: scan every module loaded in this process and
     return the first matching export. */
  HMODULE modules[1024];
  DWORD needed = 0;
  HANDLE proc = GetCurrentProcess ();

  if (!EnumProcessModules (proc, modules, sizeof (modules), &needed))
    {
      dl_last_error[0] = '\0';
      return NULL;
    }

  DWORD count = needed / sizeof (HMODULE);
  if (count > 1024)
    count = 1024;
  for (DWORD i = 0; i < count; i++)
    {
      FARPROC addr = GetProcAddress (modules[i], symbol);
      if (addr != NULL)
        return (void *)addr;
    }

  dl_last_error[0] = '\0';
  return NULL;
}

char *
dlerror (void)
{
  return dl_last_error[0] ? dl_last_error : NULL;
}
