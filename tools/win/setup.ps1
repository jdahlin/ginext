# One-time Windows ARM64 build-environment setup for ginext.
#
#   powershell -File tools\win\setup.ps1
# (pwsh / PowerShell 7 works too if installed.)
#
# Creates the build venv, installs the Python build/test tooling, and
# editable-installs the ginext sub-packages so their `ginext.overlays` entry
# points register (path alone is not enough). It does NOT build the native deps
# (vcpkg) or the typelibs -- those are heavy and documented in the port notes:
#   * vcpkg install gobject-introspection[core,cairo] cairo[gobject] pkgconf
#       libffi:arm64-windows-static-md ; and (for GTK) gtk --allow-unsupported.
#   * GTK-stack typelibs are generated from the vcpkg buildtrees (see
#       C:\dev\gir-build.ps1) since the ports ship introspection disabled.
[CmdletBinding()]
param(
    [string]$BasePython = "C:\Python314-arm64\python.exe"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo

if (-not (Test-Path $BasePython)) { throw "native CPython 3.14 not found: $BasePython" }

$venv = "$repo\.venv-win-arm64"
$venvPy = "$venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating build venv at $venv"
    & $BasePython -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

# Build + test tooling. setuptools provides the distutils shim removed in 3.14
# (g-ir-scanner needs it); tzdata supplies the IANA zone db (no system one on
# Windows); pycairo builds against the vcpkg cairo (needed for foreign support).
$pkgs = @(
    "meson", "ninja", "meson-python",
    "setuptools", "pytest", "pytest-xdist", "pytest-timeout",
    "pycairo", "tzdata"
)
Write-Host "Installing build/test tooling: $($pkgs -join ', ')"
uv pip install --python $venvPy @pkgs
if ($LASTEXITCODE -ne 0) { throw "tooling install failed" }

# Editable-install the sub-packages (no deps) so their overlay entry points
# register for the test runs.
foreach ($p in @("ginext-gio", "ginext-gtk", "ginext-gst", "ginext-libsoup", "ginext-gi-compat")) {
    if (Test-Path "$repo\packages\$p\pyproject.toml") {
        Write-Host "Editable-installing $p"
        uv pip install --python $venvPy --no-deps -e "packages\$p"
        if ($LASTEXITCODE -ne 0) { throw "editable install of $p failed" }
    }
}

Write-Host "Setup complete. Next: pwsh -File tools\win\build.ps1"
