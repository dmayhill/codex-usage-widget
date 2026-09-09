from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8")
BUILD_SCRIPT = (ROOT / "scripts" / "build-exe.ps1").read_text(encoding="utf-8")
VERSION_SOURCE = (ROOT / "scripts" / "dependency-versions.ps1").read_text(encoding="utf-8")
START_SCRIPT = (ROOT / "scripts" / "start-codex-usage-widget.ps1").read_text(encoding="utf-8")
RESET_SCRIPT = (ROOT / "scripts" / "reset-codex-usage-widget.ps1").read_text(encoding="utf-8")
START_DEBUG = (ROOT / "scripts" / "start-codex-usage-widget-debug.cmd").read_text(encoding="utf-8")
RESET_DEBUG = (ROOT / "scripts" / "reset-codex-usage-widget-debug.cmd").read_text(encoding="utf-8")
VBS_LAUNCHER = (ROOT / "start-codex-usage-widget.vbs").read_text(encoding="utf-8")


def test_installer_and_build_use_the_shared_exact_versions():
    assert '$CodexCliUsageVersion = "0.1.7"' in VERSION_SOURCE
    assert '$PyInstallerVersion = "6.21.0"' in VERSION_SOURCE
    assert '. $VersionFile' in INSTALLER
    assert '. $VersionFile' in BUILD_SCRIPT
    assert '"codex-cli-usage==$CodexCliUsageVersion"' in INSTALLER
    assert '"pyinstaller==$PyInstallerVersion"' in BUILD_SCRIPT


def test_missing_uv_guidance_does_not_execute_a_remote_script():
    for script in (INSTALLER, BUILD_SCRIPT):
        lowered = script.lower()
        assert "irm https://" not in lowered
        assert "| iex" not in lowered
        assert "winget install --id=astral-sh.uv -e" in lowered
        assert "https://docs.astral.sh/uv/getting-started/installation/" in lowered


def test_operational_launchers_live_under_scripts_and_resolve_the_project_root():
    assert not (ROOT / "install-windows.ps1").exists()
    assert not (ROOT / "start-codex-usage-widget.ps1").exists()
    assert not (ROOT / "start-codex-usage-widget-debug.cmd").exists()
    assert not (ROOT / "reset-codex-usage-widget.ps1").exists()
    assert not (ROOT / "reset-codex-usage-widget-debug.cmd").exists()
    assert '"scripts\\start-codex-usage-widget.ps1"' in VBS_LAUNCHER
    assert '$Root = Split-Path -Parent $PSScriptRoot' in START_SCRIPT
    assert 'Join-Path $Root "codex_usage_widget.py"' in START_SCRIPT
    assert 'Join-Path $Root ".venv\\Scripts\\pythonw.exe"' in START_SCRIPT
    assert 'Join-Path $Root ".venv\\Scripts\\python.exe"' in START_SCRIPT
    assert '$StartScript = Join-Path $ScriptDir "start-codex-usage-widget.ps1"' in RESET_SCRIPT
    assert 'set "PS1=%SCRIPT_DIR%start-codex-usage-widget.ps1"' in START_DEBUG
    assert 'set "PS1=%SCRIPT_DIR%reset-codex-usage-widget.ps1"' in RESET_DEBUG
    assert 'Join-Path $Root "scripts\\dependency-versions.ps1"' not in INSTALLER


def test_documented_launch_commands_match_the_relocated_files():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ".\\scripts\\install-windows.ps1" in readme
    assert ".\\scripts\\start-codex-usage-widget-debug.cmd" in readme
    assert ".\\scripts\\reset-codex-usage-widget-debug.cmd" in readme
    assert ".\\install-windows.ps1" not in readme
    assert ".\\start-codex-usage-widget-debug.cmd" not in readme
    assert ".\\reset-codex-usage-widget-debug.cmd" not in readme
    assert "start-codex-usage-widget.cmd" not in readme
    assert "start-codex-usage-widget.cmd" not in INSTALLER
