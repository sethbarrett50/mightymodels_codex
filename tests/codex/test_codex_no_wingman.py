"""Guard the Codex Fable-disabled decision route across its consumers."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]

SKILLS = (
    'ask-an-adult',
    'prompting-subagents',
    'whats-broken',
    'game-plan',
    'cross-examine',
    'review-circus',
)


@pytest.mark.unit
@pytest.mark.parametrize('skill', SKILLS)
def test_codex_fable_avoidance_before_claude_workflow(skill: str) -> None:
    text = (ROOT / 'skills' / skill / 'SKILL.md').read_text(encoding='utf-8')
    marker = text.index('Codex-only')
    first_heading = text.index('\n# ', marker)
    policy = text[marker:first_heading]
    assert 'Fable' in policy or 'Wingman' in policy
    assert 'Codex' in policy


@pytest.mark.unit
def test_codex_global_policy_does_not_substitute_fable() -> None:
    text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'no Fable/Wingman agent' in text
    assert 'unanswered/timeout' in text


@pytest.mark.unit
def test_installed_codex_ask_an_adult_never_uses_claude_wingman_dispatch() -> None:
    rendered = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))['translated'](
        ROOT / 'skills/ask-an-adult/SKILL.md'
    )
    installed = (ROOT / '.codex/skills/ask-an-adult/SKILL.md').read_text()
    assert rendered == installed
    assert 'Codex user decision gate' not in rendered
    assert 'wingman returns a' not in rendered.lower()
    assert 'ticket_update_context' in rendered
    assert 'investigation_add' in rendered
    assert 'investigation_render' in rendered
    assert 'Use the actual native `request_user_input` question tool in Default or Plan mode' in rendered
    assert 'No Wingman/Fable agent or substitute dispatch is available' in rendered
