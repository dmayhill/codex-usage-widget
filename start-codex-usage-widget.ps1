param([switch]$ResetPosition)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Widget = Join-Path $ScriptDir "codex_usage_widget.py"
$Tried = New-Object System.Collections.Generic.List[string]
$DebugLauncher = $env:CODEX_USAGE_WIDGET_DEBUG -eq "1"

function Stop-ExistingWidgetProcesses {
    param([string]$WidgetPath)

    $pattern = [Regex]::Escape($WidgetPath)
    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $pattern
    }

    foreach ($Process in $processes) {
        try {
            Stop-Process -Id $Process.ProcessId -Force -ErrorAction Stop
        } catch {
            continue
        }
    }

    if ($processes) {
        Start-Sleep -Milliseconds 500
    }
}

function Wait-On-Error {
    param([string]$Message)

    if (-not $DebugLauncher) {
        exit 1
    }

    Write-Host ""
    Write-Host $Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Python candidates tried:"
    foreach ($Item in $Tried) {
        Write-Host "  - $Item"
    }
    Write-Host ""
    Read-Host "Press Enter to close"
}

# A PyInstaller parent can leak its bundled Tcl/Tk paths into this process.
# They are incompatible with the standalone Python runtime used by the widget.
Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue
Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue
Stop-ExistingWidgetProcesses -WidgetPath $Widget

if ($DebugLauncher) {
    $PythonCandidates = @(
        (Join-Path $ScriptDir ".venv\Scripts\python.exe"),
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
        "python",
        "py",
        (Join-Path $ScriptDir ".venv\Scripts\pythonw.exe"),
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe",
        "pythonw"
    )
} else {
    $PythonCandidates = @(
        (Join-Path $ScriptDir ".venv\Scripts\pythonw.exe"),
        (Join-Path $ScriptDir ".venv\Scripts\python.exe"),
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\pythonw.exe",
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
        "pythonw",
        "python",
        "py"
    )
}

foreach ($Candidate in $PythonCandidates) {
    try {
        $Tried.Add($Candidate)
        $Command = Get-Command $Candidate -ErrorAction Stop
        $WidgetArgs = @($Widget)
        if ($ResetPosition) {
            $WidgetArgs += "--reset-position"
        }
        & $Command.Source @WidgetArgs
        $ExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
        if ($ExitCode -ne 0) {
            Wait-On-Error "The widget exited with code $ExitCode."
        }
        exit $ExitCode
    } catch {
        $Tried.Add("$Candidate ($($_.Exception.Message))")
        continue
    }
}

Wait-On-Error "Could not find Python. Install Python 3, or run this with a project .venv."
exit 1
