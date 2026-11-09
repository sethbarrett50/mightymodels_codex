"""Read-only doctor cannot disclose secrets or silently bless missing setup."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'scripts/install_codex_user.py'
DOCTOR = ROOT / 'scripts/codex_doctor.py'


def run_script(script: Path, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, str(script), '--home', str(home), '--root', str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
    )


@pytest.mark.unit
def test_doctor_reports_missing_install_without_modifying_home(tmp_path: Path) -> None:
    check = run_script(DOCTOR, tmp_path)
    assert check.returncode == 1
    assert '[FAIL]' in check.stdout
    assert not (tmp_path / '.codex').exists()


@pytest.mark.unit
def test_doctor_verifies_installed_roles_skills_and_hooks(tmp_path: Path) -> None:
    result = run_script(INSTALLER, tmp_path)
    assert result.returncode == 0, result.stderr
    check = run_script(DOCTOR, tmp_path)
    assert check.returncode == 0, check.stderr
    assert '11/11' in check.stdout
    assert '19/19' in check.stdout
    assert 'runtime trust not verified' in check.stdout
    assert 'project-scoped mighty_mcp' not in check.stdout
    assert 'Active project and global Codex hooks coexist' in check.stdout


@pytest.mark.unit
def test_installer_migrates_owned_legacy_role_links_without_changing_explicit_roles(
    tmp_path: Path,
) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    config = tmp_path / '.codex/config.toml'
    before = config.read_text(encoding='utf-8')
    agents_dir = tmp_path / '.codex/agents'
    agents_dir.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / '.codex/agents').glob('mm-*.toml'):
        (agents_dir / source.name).symlink_to(source)
    check = run_script(DOCTOR, tmp_path)
    assert check.returncode == 1
    assert '0/11' in check.stdout

    migrated = run_script(INSTALLER, tmp_path)
    assert migrated.returncode == 0, migrated.stderr
    assert config.read_text(encoding='utf-8') == before
    assert not list(agents_dir.glob('mm-*.toml'))
    check = run_script(DOCTOR, tmp_path)
    assert check.returncode == 0, check.stderr
    assert '11/11' in check.stdout


@pytest.mark.unit
def test_installer_refuses_unmanaged_agent_file_without_changes(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    config = tmp_path / '.codex/config.toml'
    before = config.read_bytes()
    agents_dir = tmp_path / '.codex/agents'
    agents_dir.mkdir(parents=True, exist_ok=True)
    foreign = agents_dir / 'mm-workers-engineer.toml'
    foreign.write_text('foreign role', encoding='utf-8')
    rerun = run_script(INSTALLER, tmp_path)
    assert rerun.returncode != 0
    assert foreign.read_text(encoding='utf-8') == 'foreign role'
    assert config.read_bytes() == before


@pytest.mark.unit
def test_doctor_never_outputs_unrelated_config_secret_values(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    config = tmp_path / '.codex/config.toml'
    config.write_text('secret_canary = "DO_NOT_LOG_TOKEN_1234"\n' + config.read_text())
    result = run_script(DOCTOR, tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'DO_NOT_LOG_TOKEN_1234' not in result.stdout + result.stderr


@pytest.mark.unit
def test_doctor_detects_foreign_hook_configuration(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    hooks = tmp_path / '.codex/hooks.json'
    hooks.write_text('{"hooks":{"Other":[]}}\n')
    result = run_script(DOCTOR, tmp_path)
    assert result.returncode == 1
    assert 'hook groups missing or different' in result.stdout
    assert hooks.read_text() == '{"hooks":{"Other":[]}}\n'


@pytest.mark.unit
def test_doctor_accepts_owned_hooks_alongside_foreign_groups(tmp_path: Path) -> None:
    hooks = tmp_path / '.codex/hooks.json'
    hooks.parent.mkdir()
    original = {
        'description': 'user hooks',
        'hooks': {'PreToolUse': [{'matcher': 'Bash', 'hooks': []}]},
    }
    hooks.write_text(json.dumps(original) + '\n')
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    result = run_script(DOCTOR, tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'runtime trust not verified' in result.stdout


@pytest.mark.unit
def test_doctor_fails_when_uv_is_not_on_path(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    empty_bin = tmp_path / 'empty-bin'
    empty_bin.mkdir()
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(DOCTOR), '--home', str(tmp_path), '--root', str(ROOT)],
        text=True,
        capture_output=True,
        check=False,
        cwd=ROOT,
        env={**os.environ, 'PATH': str(empty_bin)},
    )
    assert result.returncode == 1
    assert '[FAIL] uv executable unavailable for MightyModels MCP launcher' in result.stdout
    assert '11/11' in result.stdout
    assert '19/19' in result.stdout


@pytest.mark.unit
def test_doctor_rejects_explicitly_disabled_mcp_registration(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    config = tmp_path / '.codex/config.toml'
    content = config.read_text(encoding='utf-8')
    marker = '[mcp_servers.mighty_mcp]'
    assert marker in content
    config.write_text(content.replace(marker, marker + '\nenabled = false', 1), encoding='utf-8')
    result = run_script(DOCTOR, tmp_path)
    assert result.returncode == 1
    assert 'MCP registration missing or unexpected' in result.stdout


@pytest.mark.unit
def test_doctor_rejects_wrong_toml_table_types_without_traceback(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr
    config = tmp_path / '.codex/config.toml'
    config.write_text('mcp_servers = "invalid"\nagents = "invalid"\n')
    result = run_script(DOCTOR, tmp_path)
    assert result.returncode == 1
    assert 'MCP registration missing or unexpected' in result.stdout
    assert '0/11' in result.stdout
    assert 'Traceback' not in result.stderr


@pytest.mark.unit
def test_doctor_rejects_mismatched_skill_manifest_name(tmp_path: Path) -> None:
    installed = run_script(INSTALLER, tmp_path)
    assert installed.returncode == 0, installed.stderr

    # Inspect a malformed manifest without modifying installed skill sources.
    fixture_root = tmp_path / 'source-checkout'
    source = ROOT / '.codex/skills/lets-investigate/SKILL.md'
    destination = fixture_root / '.codex/skills/lets-investigate/SKILL.md'
    destination.parent.mkdir(parents=True)
    destination.write_text(
        source.read_text(encoding='utf-8').replace(
            'name: lets-investigate', 'name: wrong-name', 1
        ),
        encoding='utf-8',
    )
    from runpy import run_path

    doctor = run_path(str(DOCTOR))
    assert not doctor['skill_manifest_named'](destination)
    assert doctor['skill_manifest_named'](source)
