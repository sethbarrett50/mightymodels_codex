"""All generated Codex skills must request actual native interactive questions."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATE = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))['translated']
SKILLS = sorted((ROOT / 'skills').glob('*/SKILL.md'))


@pytest.mark.unit
@pytest.mark.parametrize('source', SKILLS, ids=lambda path: path.parent.name)
def test_every_generated_skill_requires_native_question_ui(source: Path) -> None:
    generated = GENERATE(source)
    installed = ROOT / '.codex/skills' / source.parent.name / 'SKILL.md'
    assert generated == installed.read_text(encoding='utf-8')
    assert 'Always invoke real `request_user_input`' in generated
    assert 'blocking Plan-mode input' in generated
    assert 'A required decision in Default mode uses ordinary chat' not in generated
    if source.parent.name != 'ask-an-adult':
        assert 'Codex native user questions (all skills)' in generated
        assert 'do not substitute an ordinary-chat question or proceed' in generated


@pytest.mark.unit
def test_global_policy_rejects_textual_popup_imitation() -> None:
    policy = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'never a plain-text' in policy
    assert 'Required decisions must use genuinely blocking native input in Plan mode' in policy
    assert 'Do not claim to have opened a popup unless you called the tool' in policy


@pytest.mark.unit
def test_critical_question_skills_require_blocking_plan_input() -> None:
    for name in ('ask-an-adult', 'lets-investigate', 'open-ticket'):
        skill = (ROOT / '.codex/skills' / name / 'SKILL.md').read_text()
        assert 'request_user_input' in skill
        assert 'Plan mode' in skill
        assert 'automatically resolved' in skill or 'automatic resolution' in skill
