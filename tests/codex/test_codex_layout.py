"""Structural smoke tests for Codex plugin and project packaging."""

import json
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_all_codex_roles_are_discoverable() -> None:
    originals = list((ROOT / 'agents').rglob('*.md'))
    converted = list((ROOT / '.codex' / 'agents').glob('*.toml'))
    assert len(originals) == 12
    assert len(converted) == 11
    assert not (ROOT / '.codex/agents/mm-triage-wingman.toml').exists()
    for path in converted:
        role = tomllib.loads(path.read_text(encoding='utf-8'))
        for required in ('name', 'description', 'developer_instructions'):
            assert isinstance(role.get(required), str)
            assert role[required]
        assert role['name'] == path.stem
        assert role['model'] in {'gpt-6-luna', 'gpt-6.1-sol'}
        assert role['model_reasoning_effort'] in {'medium', 'high'}


@pytest.mark.unit
def test_plugin_and_mcp_metadata() -> None:
    manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
    mcp = json.loads((ROOT / 'mcp.json').read_text(encoding='utf-8'))
    assert manifest['extensions']['com.openai']['hooks'] == './hooks/codex-hooks.json'
    server = mcp['mcpServers']['mighty-mcp']
    assert server['type'] == 'stdio'
    assert server['command'] == './bin/mightymodels-mcp-codex'
    assert (ROOT / server['command']).is_file()
    assert (ROOT / server['command']).stat().st_mode & 0o111


@pytest.mark.unit
def test_project_scoped_skills() -> None:
    source = sorted((ROOT / 'skills').glob('*/SKILL.md'))
    assert len(source) == 19
    for item in source:
        skill = ROOT / '.agents' / 'skills' / item.parent.name
        assert skill.is_symlink()
        generated = ROOT / '.codex' / 'skills' / item.parent.name
        assert skill.resolve() == generated.resolve()
        assert 'Native Codex workflow (generated)' in (skill / 'SKILL.md').read_text()
        assert 'Codex runtime adapter (MightyModels fork)' in item.read_text(encoding='utf-8')


@pytest.mark.unit
def test_generated_skills_avoid_claude_runtime_assumptions() -> None:
    for skill in (ROOT / '.codex/skills').glob('*/SKILL.md'):
        instructions = skill.read_text(encoding='utf-8')
        assert '${CLAUDE_PLUGIN_ROOT}' not in instructions
        assert 'Models are the fixed aliases `subagent-models` lists' not in instructions
        assert 'Claude Codex user decision gate recorder' not in instructions


@pytest.mark.unit
def test_native_roles_do_not_require_legacy_claude_tools_or_skill_preloads() -> None:
    role_files = sorted((ROOT / '.codex/agents').glob('mm-*.toml'))
    assert len(role_files) == 11
    forbidden = (
        '`Read`',
        '`Grep`',
        '`Glob`',
        '`Bash`',
        '`Agent`',
        '`Edit`',
        '`Write`',
        'preloaded `prompting-subagents` skill',
        'preloaded `becoming-merge-vader` skill',
        'preloaded `becoming-uncle-bob` skill',
    )
    for path in role_files:
        role = tomllib.loads(path.read_text(encoding='utf-8'))
        instructions = role['developer_instructions']
        assert all(legacy not in instructions for legacy in forbidden), path.name
        assert 'Load required skills explicitly from $HOME/.agents/skills' in instructions
        assert 'NOT automatically enforced by Codex' in instructions


@pytest.mark.unit
def test_hook_configurations_parse() -> None:
    for path in ('hooks/codex-hooks.json', 'hooks/codex-global-template.json'):
        data = json.loads((ROOT / path).read_text(encoding='utf-8'))
        group = data['hooks']['PreToolUse'][0]
        assert 'Agent' in group['matcher']
        assert group['hooks'][0]['type'] == 'command'
    project = tomllib.loads((ROOT / '.codex/config.toml').read_text(encoding='utf-8'))
    assert 'mighty_mcp' not in project.get('mcp_servers', {})
    local_hooks = json.loads((ROOT / '.codex/hooks.json').read_text(encoding='utf-8'))
    assert set(local_hooks['hooks']) == {'PreToolUse', 'PostToolUse'}
    assert 'apply_patch' in local_hooks['hooks']['PreToolUse'][0]['matcher']
    post_edit = local_hooks['hooks']['PostToolUse'][0]
    assert post_edit['matcher'] == '^apply_patch


@pytest.mark.unit
def test_shell_launcher_syntax() -> None:
    subprocess.run(  # noqa: S603
        [shutil.which('sh') or '/bin/sh', '-n', 'bin/mightymodels-mcp-codex'],
        check=True,
        cwd=ROOT,
    )

    assert 'codex_post_edit_check.py' in post_edit['hooks'][0]['command']
    assert 'spawn_agent' not in json.dumps(local_hooks)


@pytest.mark.unit
def test_shell_launcher_syntax() -> None:
    subprocess.run(  # noqa: S603
        [shutil.which('sh') or '/bin/sh', '-n', 'bin/mightymodels-mcp-codex'],
        check=True,
        cwd=ROOT,
    )
