# Dot-source this to set up a Windows build environment for ginext.
#   . .\tools\win\build-env.ps1                       # auto-detect arch
#   $env:GINEXT_TRIPLET='x64-windows'; . .\tools\win\build-env.ps1
#
# Sets the MSVC toolchain env (INCLUDE/LIB) for the target arch, puts clang-cl +
# vcpkg tools on PATH, and points pkg-config / GI_TYPELIB_PATH at the vcpkg
# install tree. Everything is parameterized so the same script drives both
# arm64-windows and x64-windows; override via these env vars (defaults shown):
#   GINEXT_TRIPLET   arm64-windows on ARM hosts, else x64-windows
#   VCPKG_ROOT       C:\dev\vcpkg
#   GINEXT_LLVM      C:\LLVM
#   GINEXT_VS        the VS 2022 BuildTools install
#   GINEXT_TYPELIB_EXTRA  extra dir(s) prepended to GI_TYPELIB_PATH (out-of-band
#                         typelibs until the introspection overlays land)

# --- resolve target triplet / arch ---------------------------------------
if (-not $env:GINEXT_TRIPLET) {
  $isArm = $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64'
  $env:GINEXT_TRIPLET = if ($isArm) { 'arm64-windows' } else { 'x64-windows' }
}
switch ($env:GINEXT_TRIPLET) {
  'arm64-windows' { $vcArch = 'arm64' }
  'x64-windows'   { $vcArch = 'amd64' }
  default { throw "unsupported GINEXT_TRIPLET '$($env:GINEXT_TRIPLET)' (use arm64-windows or x64-windows)" }
}

# --- locate toolchain roots ----------------------------------------------
$vcpkg = if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { 'C:\dev\vcpkg' }
$llvm  = if ($env:GINEXT_LLVM) { $env:GINEXT_LLVM } else { 'C:\LLVM' }
$vs    = if ($env:GINEXT_VS) { $env:GINEXT_VS } else {
  'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools'
}
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvarsall.bat'
if (-not (Test-Path $vcvars)) { throw "vcvarsall.bat not found: $vcvars (set GINEXT_VS)" }
if (-not (Test-Path $vcpkg))  { throw "vcpkg root not found: $vcpkg (set VCPKG_ROOT)" }

$installed       = Join-Path $vcpkg "installed\$($env:GINEXT_TRIPLET)"
$installedStatic = Join-Path $vcpkg "installed\$($env:GINEXT_TRIPLET)-static-md"

# --- MSVC env for the target arch ----------------------------------------
cmd /c "`"$vcvars`" $vcArch >nul 2>&1 && set" | ForEach-Object {
  if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "Env:\$($matches[1])" -Value $matches[2] }
}

# --- PATH: clang-cl + vcpkg tools (pkgconf, glib-compile-schemas, dlls) ---
# tools\glib holds glib-compile-schemas/-resources, gdbus, etc. (used by tests).
$env:PATH = "$llvm\bin;$installed\tools\pkgconf;$installed\tools\glib;$installed\bin;" + $env:PATH

# static-md first so dependency('libffi') resolves to the static lib (avoids the
# dllimport-data static-initializer problem); dynamic install supplies the rest.
$env:PKG_CONFIG_PATH = "$installedStatic\lib\pkgconfig;$installed\lib\pkgconfig"

# Typelibs: vcpkg's own girepository-1.0 dir, plus any out-of-band extras
# (prepended) until the introspection overlays land. See tools\win\BOOTSTRAP.md.
$gitl = "$installed\lib\girepository-1.0"
$env:GI_TYPELIB_PATH = if ($env:GINEXT_TYPELIB_EXTRA) { "$($env:GINEXT_TYPELIB_EXTRA);$gitl" } else { $gitl }

# GStreamer plugins (fakesink/coreelements/etc.) live under plugins\gstreamer.
$env:GST_PLUGIN_PATH = "$installed\plugins\gstreamer"

Write-Host "ginext build-env: triplet=$($env:GINEXT_TRIPLET) arch=$vcArch vcpkg=$vcpkg"
