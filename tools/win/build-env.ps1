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
$arch = $env:GINEXT_TRIPLET -replace '-windows$',''

# --- locate toolchain roots ----------------------------------------------
$vcpkg = if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { 'C:\dev\vcpkg' }
$llvm  = if ($env:GINEXT_LLVM) { $env:GINEXT_LLVM } else { 'C:\LLVM' }
$vs    = if ($env:GINEXT_VS) { $env:GINEXT_VS } else {
  'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools'
}
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvarsall.bat'
if (-not (Test-Path $vcvars)) { throw "vcvarsall.bat not found: $vcvars (set GINEXT_VS)" }
if (-not (Test-Path $vcpkg))  { throw "vcpkg root not found: $vcpkg (set VCPKG_ROOT)" }

# Resolve the install tree. Manifest mode installs to either VCPKG_INSTALLED_DIR
# (what we pass run-vcpkg / vcpkg --x-install-root) or <repo>\vcpkg_installed;
# classic mode to <vcpkg>\installed. Order: explicit override, VCPKG_INSTALLED_DIR,
# repo manifest tree, classic.
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$manifestInstalled = Join-Path $repoRoot "vcpkg_installed\$($env:GINEXT_TRIPLET)"
$envInstalled = if ($env:VCPKG_INSTALLED_DIR) { Join-Path $env:VCPKG_INSTALLED_DIR $env:GINEXT_TRIPLET } else { $null }
if ($env:GINEXT_VCPKG_INSTALLED) {
  $installed = $env:GINEXT_VCPKG_INSTALLED
} elseif ($envInstalled -and (Test-Path $envInstalled)) {
  $installed = $envInstalled
} elseif (Test-Path $manifestInstalled) {
  $installed = $manifestInstalled
} else {
  $installed = Join-Path $vcpkg "installed\$($env:GINEXT_TRIPLET)"
}
# Export the resolved path so build.ps1 (and re-sources) reuse the exact tree.
$env:GINEXT_VCPKG_INSTALLED = $installed

# --- MSVC env for the target arch ----------------------------------------
cmd /c "`"$vcvars`" $vcArch >nul 2>&1 && set" | ForEach-Object {
  if ($_ -match '^([^=]+)=(.*)$') { Set-Item -Path "Env:\$($matches[1])" -Value $matches[2] }
}

# --- PATH: clang-cl + vcpkg tools (pkgconf, glib-compile-schemas, dlls) ---
# tools\glib holds glib-compile-schemas/-resources, gdbus, etc. (used by tests).
$env:PATH = "$llvm\bin;$installed\tools\pkgconf;$installed\tools\glib;$installed\bin;" + $env:PATH

# The overlay triplet builds libffi as a static lib in this same tree (so
# dependency('libffi') resolves to the static one, avoiding the dllimport-data
# static-initializer problem); everything else is dynamic.
$env:PKG_CONFIG_PATH = "$installed\lib\pkgconfig"

# Typelibs: vcpkg's own girepository-1.0 dir, plus any out-of-band extras
# (prepended) until the introspection overlays land. See tools\win\BOOTSTRAP.md.
$gitl = "$installed\lib\girepository-1.0"
$env:GI_TYPELIB_PATH = if ($env:GINEXT_TYPELIB_EXTRA) { "$($env:GINEXT_TYPELIB_EXTRA);$gitl" } else { $gitl }

# GStreamer plugins (fakesink/coreelements/etc.) live under plugins\gstreamer.
$env:GST_PLUGIN_PATH = "$installed\plugins\gstreamer"

# Pytest on Windows needs the vcpkg DLL dir registered explicitly (PATH alone is
# not enough for extension-module dependencies), and some subprocess/package-root
# runs only see the shared conftest helpers. Export the shared locations here so
# direct `uv run pytest` and spawned subprocesses can resolve the same runtime.
$testTypelibs = Join-Path $repoRoot "build\win-$arch\packages\typelib"
$coreSrc = Join-Path $repoRoot "build\win-$arch\src"
$packageSrcs = @(
  (Join-Path $repoRoot "packages\ginext-gio\src"),
  (Join-Path $repoRoot "packages\ginext-gtk\src"),
  (Join-Path $repoRoot "packages\ginext-gst\src"),
  (Join-Path $repoRoot "packages\ginext-libsoup\src"),
  (Join-Path $repoRoot "packages\ginext-gi-compat\src")
)
$overlayDirs = foreach ($srcDir in $packageSrcs) {
  if (-not (Test-Path $srcDir)) { continue }
  Get-ChildItem -Path $srcDir -Directory -Filter *_* -EA SilentlyContinue | ForEach-Object {
    $overlayDir = Join-Path $_.FullName "_overlays"
    if (Test-Path $overlayDir) { $overlayDir }
  }
}
$env:GINEXT_WIN_DLL_DIRS = "$installed\bin;$testTypelibs"
$env:GINEXT_CORE_TYPELIBS = $gitl
$env:GINEXT_GI_TESTS_BUILDDIR = $testTypelibs
$env:PYGIR_GI_TESTS_BUILDDIR = $testTypelibs
$env:GOI_BENCH_BUILDDIR = $testTypelibs
$pythonPathParts = @()
if (Test-Path $coreSrc) {
  $pythonPathParts += $coreSrc
}
$pythonPathParts += $packageSrcs
$pythonPathParts += $repoRoot
if ($env:PYTHONPATH) {
  $pythonPathParts += $env:PYTHONPATH -split ';'
}
$env:PYTHONPATH = ($pythonPathParts | Where-Object { $_ } | Select-Object -Unique) -join ';'
if ($overlayDirs) {
  $overlayPathParts = @($overlayDirs)
  if ($env:GINEXT_OVERLAY_PATH) {
    $overlayPathParts += $env:GINEXT_OVERLAY_PATH -split ';'
  }
  $env:GINEXT_OVERLAY_PATH = ($overlayPathParts | Where-Object { $_ } | Select-Object -Unique) -join ';'
}

Write-Host "ginext build-env: triplet=$($env:GINEXT_TRIPLET) arch=$vcArch vcpkg=$vcpkg"
