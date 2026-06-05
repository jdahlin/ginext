# One-time Windows build-environment setup for ginext (x64 or arm64).
#
#   powershell -File tools\win\setup.ps1
#   $env:GINEXT_TRIPLET='x64-windows'; powershell -File tools\win\setup.ps1
# (pwsh / PowerShell 7 works too if installed.)
#
# Creates the build venv, installs the Python build/test tooling, and
# editable-installs the ginext sub-packages so their `ginext.overlays` entry
# points register (path alone is not enough). It does NOT build the native deps;
# install those with vcpkg manifest mode (see tools\win\BOOTSTRAP.md):
#   * vcpkg install --triplet <triplet>            # uses repo-root vcpkg.json
#   * (typelib generation via the introspection overlays is a tracked follow-up)
[CmdletBinding()]
param(
    [string]$BasePython = $(if ($env:GINEXT_BASE_PYTHON) { $env:GINEXT_BASE_PYTHON } else { "C:\Python314-arm64\python.exe" })
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repo

if (-not $env:GINEXT_TRIPLET) {
    $isArm = $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64'
    $env:GINEXT_TRIPLET = if ($isArm) { 'arm64-windows' } else { 'x64-windows' }
}
$arch = $env:GINEXT_TRIPLET -replace '-windows$',''

if (-not (Test-Path $BasePython)) { throw "native CPython 3.14 not found: $BasePython (set GINEXT_BASE_PYTHON)" }

$venv = "$repo\.venv-win-$arch"
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
