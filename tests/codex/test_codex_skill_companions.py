"""Generated Codex skills must resolve source companion files from unrelated repos."""

import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATE = runpy.run_path(str(ROOT / 'scripts/sync_codex_skills.py'))['translated']


@pytest.mark.unit
@pytest.mark.parametrize('name', ['prompting-subagents', 'baton-pass'])
def test_generated_skill_resolves_canonical_companions(name: str) -> None:
    source = ROOT / 'skills' / name / 'SKILL.md'
    generated = ROOT / '.codex/skills' / name / 'SKILL.md'
    body = GENERATE(source)

    assert generated.read_text(encoding='utf-8') == body
    assert f'$HOME/.agents/skills/{name}' in body
    assert f'skills/{name}/<relative companion path>' in body
    assert 'Do not look for those files in the unrelated target repository' in body
    assert 'realpath' in body


@pytest.mark.unit
def test_original_claude_skill_is_not_rewritten() -> None:
    source = (ROOT / 'skills/prompting-subagents/SKILL.md').read_text()
    native = (ROOT / '.codex/skills/prompting-subagents/SKILL.md').read_text()
    assert 'Codex companion paths' not in source
    assert 'Codex companion paths' in native


@pytest.mark.unit
def test_open_ticket_metadata_requires_real_chat_instead_of_nonexistent_dialog() -> None:
    source = ROOT / 'skills/open-ticket/SKILL.md'
    rendered = GENERATE(source)
    installed = (ROOT / '.codex/skills/open-ticket/SKILL.md').read_text()
    assert rendered == installed
    assert 'a blocking ordinary-chat interview' in rendered
    assert 'one Codex user decision gate interview' not in rendered
    assert 'no native dialog API is implied' in rendered


@pytest.mark.unit
def test_generated_prompting_subagents_requires_explicit_reviewer_doctrine() -> None:
    source = ROOT / 'skills/prompting-subagents/SKILL.md'
    generated = GENERATE(source)
    installed = (ROOT / '.codex/skills/prompting-subagents/SKILL.md').read_text()
    assert generated == installed
    assert 'each preloads its doctrine' not in generated
    for name in ('becoming-merge-vader', 'becoming-uncle-bob'):
        assert f'$HOME/.agents/skills/{name}/SKILL.md' in generated
    assert 'Codex does not guarantee skill preloads' in generated
