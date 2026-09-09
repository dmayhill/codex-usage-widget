$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $PSScriptRoot
$Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"
$VersionFile = Join-Path $ScriptDir "dependency-versions.ps1"

if (-not (Test-Path -LiteralPath $VersionFile)) {
    throw "Dependency version source was not found: $VersionFile"
}
. $VersionFile

function Command-Exists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host "Codex Usage Widget installer"
Write-Host ""

if (Command-Exists "uv") {
    $UvCommand = (Get-Command "uv").Source
} elseif (Test-Path -LiteralPath $Uv) {
    $UvCommand = $Uv
} else {
    Write-Host "uv is required but was not found. Install it manually, then rerun this script:"
    Write-Host "  https://docs.astral.sh/uv/getting-started/installation/"
    Write-Host ""
    Write-Host "Official Windows package-manager option:"
    Write-Host "  winget install --id=astral-sh.uv -e"
    exit 1
}

& $UvCommand tool install --force "codex-cli-usage==$CodexCliUsageVersion"
if ($LASTEXITCODE -ne 0) {
    throw "Could not install codex-cli-usage==$CodexCliUsageVersion."
}

Write-Host ""
Write-Host "Checking codex-cli-usage..."
if (Command-Exists "codex-cli-usage") {
    & (Get-Command "codex-cli-usage").Source json
} elseif (Test-Path -LiteralPath (Join-Path $env:USERPROFILE ".local\bin\codex-cli-usage.exe")) {
    & (Join-Path $env:USERPROFILE ".local\bin\codex-cli-usage.exe") json
} else {
    & $UvCommand tool run --from "codex-cli-usage==$CodexCliUsageVersion" codex-cli-usage json
}
if ($LASTEXITCODE -ne 0) {
    throw "codex-cli-usage did not return usage JSON."
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Run the widget with:"
Write-Host "  $Root\start-codex-usage-widget.vbs"
