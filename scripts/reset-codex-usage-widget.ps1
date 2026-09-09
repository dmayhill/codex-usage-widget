param()

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$StartScript = Join-Path $ScriptDir "start-codex-usage-widget.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartScript -ResetPosition

exit $LASTEXITCODE
