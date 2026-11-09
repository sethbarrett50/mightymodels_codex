"""Generated assembly dispatches must name installed native Codex agents."""

import tomllib
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATE = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = GENERATE['translated']
native_assembly_roles = GENERATE['native_assembly_roles']


@pytest.mark.unit
def test_assembly_uses_registered_roles_and_actual_user_input() -> None:
    generated = translated(ROOT / 'skills/agents-assemble/SKILL.md')
    roles = ('mm-workers-engineer', 'mm-workers-intern', 'mm-review-fact-checker')
    for name in roles:
        path = ROOT / '.codex/agents' / f'{name}.toml'
        assert tomllib.loads(path.read_text(encoding='utf-8'))['name'] == name
        assert name in generated
    assert 'mightymodels:workers:intern' not in generated
    assert 'mightymodels:review:fact-checker' not in generated
    assert 'Stop until a verified explicit answer' in generated
    assert 'Use the registered `mm-workers-engineer` native role model' in generated
    assert "The engineer's model is `sonnet`" not in generated
    assert 'Request an explicit user decision before changing native routing' in generated
    assert generated == (ROOT / '.codex/skills/agents-assemble/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_assembly_translation_fails_when_source_steps_change() -> None:
    with pytest.raises(ValueError, match='exactly one assembly dispatch or decision'):
        native_assembly_roles('missing required instructions')
