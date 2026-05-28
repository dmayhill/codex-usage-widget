$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Uv = Join-Path $env:USERPROFILE ".local\bin\uv.exe"

function Command-Exists {
    param([string]$Name)
    return $null -ne (Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host "Codex Usage Widget installer"
Write-Host ""

if (-not (Command-Exists "uv") -and -not (Test-Path $Uv)) {
    Write-Host "Installing uv..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
}

if (Test-Path $Uv) {
    & $Uv tool install codex-cli-usage
} else {
    uv tool install codex-cli-usage
}

Write-Host ""
Write-Host "Checking codex-cli-usage..."
if (Command-Exists "codex-cli-usage") {
    codex-cli-usage json
} else {
    & (Join-Path $env:USERPROFILE ".local\bin\codex-cli-usage.exe") json
}

Write-Host ""
Write-Host "Install complete."
Write-Host "Run the widget with:"
Write-Host "  $ScriptDir\start-codex-usage-widget.cmd"
