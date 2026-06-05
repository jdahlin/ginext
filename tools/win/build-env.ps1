# Dot-source this to set up the Windows ARM64 build environment for ginext.
#   . .\tools\win\build-env.ps1
# Sets the MSVC ARM64 toolchain env (INCLUDE/LIB), puts clang-cl + vcpkg tools
# on PATH, and points pkg-config at the vcpkg arm64-windows install.
$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
cmd /c "`"$vcvars`" arm64 >nul 2>&1 && set" | ForEach-Object {
  if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "Env:\$($matches[1])" -Value $matches[2] }
}
$vcpkg = "C:\dev\vcpkg\installed\arm64-windows"
$vcpkgStatic = "C:\dev\vcpkg\installed\arm64-windows-static-md"
# tools\glib holds glib-compile-schemas/-resources, gdbus, etc. (used by tests).
$env:PATH = "C:\LLVM\bin;$vcpkg\tools\pkgconf;$vcpkg\tools\glib;$vcpkg\bin;" + $env:PATH
# static-md first so dependency('libffi') resolves to the static lib (avoids the
# dllimport-data static-initializer problem); dynamic install supplies the rest.
$env:PKG_CONFIG_PATH = "$vcpkgStatic\lib\pkgconfig;$vcpkg\lib\pkgconfig"
# Combined typelibs: vcpkg's (cairo etc.) + MSYS2 clangarm64 glib 2.88.1 ones
# (which add the native-ARM64 GIRepository-3.0.typelib vcpkg's glib lacks).
$env:GI_TYPELIB_PATH = "C:\dev\gitl"
# GStreamer plugins (fakesink/coreelements/etc.) live under plugins\gstreamer.
$env:GST_PLUGIN_PATH = "$vcpkg\plugins\gstreamer"
