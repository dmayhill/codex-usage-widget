$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Entry = Join-Path $Root "codex_usage_widget.py"
$VersionFile = Join-Path $PSScriptRoot "dependency-versions.ps1"

if (-not (Test-Path -LiteralPath $VersionFile)) {
    throw "Dependency version source was not found: $VersionFile"
}
. $VersionFile

$Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
$PyInstallerRequirement = "pyinstaller==$PyInstallerVersion"

if (Get-Command uvx -ErrorAction SilentlyContinue) {
    $Runner = (Get-Command uvx).Source
    $RunnerArguments = @("--from", $PyInstallerRequirement, "pyinstaller")
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    $Runner = (Get-Command uv).Source
    $RunnerArguments = @("tool", "run", "--from", $PyInstallerRequirement, "pyinstaller")
} elseif (Test-Path -LiteralPath $Uv) {
    $Runner = $Uv
    $RunnerArguments = @("tool", "run", "--from", $PyInstallerRequirement, "pyinstaller")
} else {
    Write-Host "uv is required but was not found. Install it manually, then rerun this script:"
    Write-Host "  https://docs.astral.sh/uv/getting-started/installation/"
    Write-Host ""
    Write-Host "Official Windows package-manager option:"
    Write-Host "  winget install --id=astral-sh.uv -e"
    exit 1
}

& $Runner @RunnerArguments --noconfirm --onefile --windowed --name CodexUsageWidget $Entry
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller $PyInstallerVersion build failed."
}

Write-Host ""
Write-Host "Built:"
Write-Host "  $Root\dist\CodexUsageWidget.exe"
