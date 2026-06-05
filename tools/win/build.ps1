# Configure and build ginext on Windows ARM64 (clang-cl + MSVC ABI).
#
#   powershell -File tools\win\build.ps1            # configure (if needed) + compile
#   powershell -File tools\win\build.ps1 -Reconfigure
# (pwsh / PowerShell 7 works too if installed.)
#
# Prerequisites (one-time, see tools\win\setup.ps1 / the port notes):
#   * Visual Studio 2022 Build Tools with the ARM64 toolchain + Windows SDK.
#   * LLVM (clang-cl + lld-link) at C:\LLVM.
#   * vcpkg at C:\dev\vcpkg with arm64-windows deps installed:
#       gobject-introspection[core,cairo], cairo[gobject], pkgconf,
#       libffi:arm64-windows-static-md, and (for GTK) gtk + its stack.
#   * Native CPython 3.14 at C:\Python314-arm64 and a build venv at
#       .venv-win-arm64 with: meson, ninja, meson-python, setuptools, pytest,
#       pytest-xdist, pytest-timeout, pycairo, tzdata.
#   * Typelibs in C:\dev\gitl (vcpkg core + MSYS2 GIRepository-3.0/GLibWin32/
#       GioWin32 + the generated GTK-stack typelibs).
[CmdletBinding()]
param(
    [switch]$Reconfigure,
    [string]$BuildDir = "build\win-arm64",
    [switch]$WithGiTests = $true
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo

# 1. Toolchain environment (vcvars ARM64 + clang-cl + vcpkg pkgconfig + typelibs).
. "$repo\tools\win\build-env.ps1"

# 2. Build venv tooling (meson 1.x). The venv python matches the native 3.14.
$venvPy = "$repo\.venv-win-arm64\Scripts\python.exe"
$meson = "$repo\.venv-win-arm64\Scripts\meson.exe"
if (-not (Test-Path $venvPy)) { throw "build venv missing: $venvPy (run tools\win\setup.ps1)" }

# 3. Configure (first time) or reconfigure on request.
$giTests = if ($WithGiTests) { "true" } else { "false" }
if (-not (Test-Path "$repo\$BuildDir\build.ninja")) {
    & $meson setup $BuildDir --native-file native-win-arm64.ini `
        "-Dbuild_gi_tests=$giTests" -Dwerror=false
    if ($LASTEXITCODE -ne 0) { throw "meson setup failed ($LASTEXITCODE)" }
} elseif ($Reconfigure) {
    & $meson setup --reconfigure $BuildDir "-Dbuild_gi_tests=$giTests" -Dwerror=false
    if ($LASTEXITCODE -ne 0) { throw "meson reconfigure failed ($LASTEXITCODE)" }
}

# 4. Compile.
& $meson compile -C $BuildDir
if ($LASTEXITCODE -ne 0) { throw "meson compile failed ($LASTEXITCODE)" }

Write-Host "ginext built: $repo\$BuildDir\src\_gobject.cp314-win_arm64.pyd"
