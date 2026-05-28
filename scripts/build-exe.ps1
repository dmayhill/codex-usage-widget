$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Entry = Join-Path $Root "codex_usage_widget.py"

if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
    Write-Host "uvx was not found. Install uv first:"
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    exit 1
}

uvx pyinstaller --noconfirm --onefile --windowed --name CodexUsageWidget $Entry

Write-Host ""
Write-Host "Built:"
Write-Host "  $Root\dist\CodexUsageWidget.exe"
