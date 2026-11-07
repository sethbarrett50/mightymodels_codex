"""Isolated tests for user-scoped Codex installation and uninstall."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / 'scripts/install_codex_user.py'


def invoke(home: Path, *, uninstall: bool = False) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(INSTALLER), '--home', str(home), '--root', str(ROOT)]
    if uninstall:
        args.append('--uninstall')
    return subprocess.run(  # noqa: S603
        args, text=True, capture_output=True, check=False, cwd=ROOT
    )


@pytest.mark.unit
def test_user_install_round_trip_preserves_existing_config(tmp_path: Path) -> None:  # noqa: PLR0915
    codex = tmp_path / '.codex'
    codex.mkdir()
    config = codex / 'config.toml'
    config.write_text('sandbox_mode = "workspace-write"\n\n[other]\nvalue = 7\n')
    instructions = codex / 'AGENTS.md'
    instructions.write_text('# Existing policies\n')
    first = invoke(tmp_path)
    assert first.returncode == 0, first.stderr
    assert len(list((codex / 'agents').glob('mm-*.toml'))) == 11
    assert len(list((tmp_path / '.agents/skills').iterdir())) == 19
    for skill in (tmp_path / '.agents/skills').iterdir():
        assert skill.resolve() == (ROOT / '.codex/skills' / skill.name).resolve()
    conf = tomllib.loads(config.read_text())
    assert conf['sandbox_mode'] == 'workspace-write'
    assert conf['other']['value'] == 7
    roles = {name: value for name, value in conf['agents'].items() if name.startswith('mm-')}
    assert len(roles) == 11
    assert 'mm-triage-wingman' not in roles
    assert roles['mm-triage-code-scout']['config_file'] == str(
        ROOT / '.codex/agents/mm-triage-code-scout.toml'
    )
    assert roles['mm-triage-code-scout']['description']
    assert conf['mcp_servers']['mighty_mcp']['args'] == [str(ROOT / 'bin/mightymodels-mcp-codex')]
    hooks = json.loads((codex / 'hooks.json').read_text())
    command = hooks['hooks']['PreToolUse'][0]['hooks'][0]['command']
    assert str(ROOT / 'hooks/codex_bridge.py') in command
    assert 'git rev-parse' not in command
    assert invoke(tmp_path).returncode == 0
    undone = invoke(tmp_path, uninstall=True)
    assert undone.returncode == 0, undone.stderr
    assert not list((codex / 'agents').glob('mm-*.toml'))
    assert not list((tmp_path / '.agents/skills').iterdir())
    assert not (codex / 'hooks.json').exists()
    assert tomllib.loads(config.read_text()) == {
        'sandbox_mode': 'workspace-write',
        'other': {'value': 7},
    }
    assert instructions.read_text().strip() == '# Existing policies'


@pytest.mark.unit
def test_refuses_unmanaged_skill(tmp_path: Path) -> None:
    existing = tmp_path / '.agents/skills/agents-assemble'
    existing.mkdir(parents=True)
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert 'Unmanaged path' in result.stderr
    assert not (tmp_path / '.codex/config.toml').exists()


@pytest.mark.unit
def test_refuses_unmanaged_mcp_config(tmp_path: Path) -> None:
    config = tmp_path / '.codex/config.toml'
    config.parent.mkdir()
    original = '[mcp_servers.mighty_mcp]\ncommand = "elsewhere"\n'
    config.write_text(original)
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert config.read_text() == original
    assert not (tmp_path / '.codex/agents').exists()


@pytest.mark.unit
def test_refuses_unmanaged_hook_file(tmp_path: Path) -> None:
    hooks = tmp_path / '.codex/hooks.json'
    hooks.parent.mkdir()
    hooks.write_text('{"hooks": {}}\n')
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert hooks.read_text() == '{"hooks": {}}\n'


@pytest.mark.unit
def test_uninstall_preserves_unrelated_entries(tmp_path: Path) -> None:
    root = tmp_path / '.codex'
    root.mkdir()
    (root / 'config.toml').write_text('[env]\nmode = "test"\n')
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    result = invoke(tmp_path, uninstall=True)
    assert result.returncode == 0, result.stderr
    assert tomllib.loads((root / 'config.toml').read_text()) == {'env': {'mode': 'test'}}


@pytest.mark.unit
def test_unowned_custom_role_is_not_overwritten(tmp_path: Path) -> None:
    config = tmp_path / '.codex/config.toml'
    config.parent.mkdir()
    original = '[agents."mm-triage-code-scout"]\ndescription = "custom"\n'
    config.write_text(original)
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert 'unowned MightyModels agent role' in result.stderr
    assert config.read_text() == original


@pytest.mark.unit
def test_upgrade_removes_obsolete_wingman_link(tmp_path: Path) -> None:
    retired = tmp_path / '.codex/agents/mm-triage-wingman.toml'
    retired.parent.mkdir(parents=True)
    retired.symlink_to(ROOT / '.codex/agents/mm-triage-wingman.toml')
    installed = invoke(tmp_path)
    assert installed.returncode == 0, installed.stderr
    assert not retired.is_symlink()
    assert len(list(retired.parent.glob('mm-*.toml'))) == 11


@pytest.mark.unit
def test_reinstall_upgrades_owned_previous_hook_manifest(tmp_path: Path) -> None:
    first = invoke(tmp_path)
    assert first.returncode == 0, first.stderr
    hooks = tmp_path / '.codex/hooks.json'
    current = json.loads(hooks.read_text())
    previous = dict(current)
    previous['hooks'] = {
        key: value
        for key, value in current['hooks'].items()
        if key not in ('SessionStart', 'PostToolUse')
    }
    hooks.write_text(json.dumps(previous, indent=2) + '\n')
    second = invoke(tmp_path)
    assert second.returncode == 0, second.stderr
    assert json.loads(hooks.read_text()) == current


@pytest.mark.unit
def test_existing_foreign_hook_event_is_not_removed(tmp_path: Path) -> None:
    current = json.loads((ROOT / '.codex/hooks.json').read_text())
    current['hooks']['PreToolUse'].append({'matcher': 'Bash', 'hooks': []})
    hooks = tmp_path / '.codex/hooks.json'
    hooks.parent.mkdir(parents=True)
    original = json.dumps(current, indent=2) + '\n'
    hooks.write_text(original)
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert 'Unmanaged hooks' in result.stderr
    assert hooks.read_text() == original


@pytest.mark.unit
def test_upgrade_reconciles_old_owned_skill_links(tmp_path: Path) -> None:
    prior = tmp_path / '.agents/skills/lets-investigate'
    prior.parent.mkdir(parents=True)
    prior.symlink_to(ROOT / 'skills/lets-investigate', target_is_directory=True)
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stderr
    assert prior.is_symlink()
    assert prior.resolve() == (ROOT / '.codex/skills/lets-investigate').resolve()
    assert (prior / 'references').is_dir()
