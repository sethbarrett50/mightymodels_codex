"""Guard the Codex Fable-disabled decision route across its consumers."""

from pathlib import Path

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
