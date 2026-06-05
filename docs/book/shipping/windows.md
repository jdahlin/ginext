# Windows installers

> Bundling GTK + Python + your app into something Windows users can install. The single biggest pain point in cross-platform GTK; this chapter is the survival kit.

## What this chapter covers

- The two build approaches:
    - **MSYS2-based**: build under MSYS2, copy the runtime into your installer.
    - **gvsbuild**: native MSVC-compiled GTK, leaner runtime, more setup.
- The bundling problem: Python interpreter, GTK DLLs, GdkPixbuf loaders, GLib schemas, GI typelibs, GResources, icons, locales.
- Recipe shape:
    1. Build/install everything into a staging dir.
    2. Run a tree-pruner to remove dev artifacts and unused locales.
    3. Verify the staged tree launches your app standalone.
    4. Wrap it in an installer.
- Installers:
    - **Inno Setup**: simplest, widely used, free.
    - **NSIS**: older, scriptable.
    - **WiX / MSI**: required for enterprise/Group Policy deployments.
    - **MSIX (Microsoft Store)**: modern packaging, App Installer integration.
- Code signing: certificate options (regular vs EV), `signtool` usage. Without it, SmartScreen will scare your users.
- File associations: registering `.ext` handlers correctly.
- Auto-updates: WinSparkle, Squirrel.Windows, or DIY.
- Common failures at runtime:
    - GTK can't find typelibs → `GI_TYPELIB_PATH`.
    - PNG icons not loading → missing GdkPixbuf loaders.
    - "Schema not found" → missing `gschemas.compiled`.
    - Crash on launch → wrong DLL search path.

## What you'll be able to do

- Produce a signed Windows installer that runs on a clean Windows machine.
- Diagnose the most common Windows-runtime failures.

## Notes for the writer

- This chapter ages slowly but does age. Pin years.
- Include a "what to bundle" tree as the reference artifact.
