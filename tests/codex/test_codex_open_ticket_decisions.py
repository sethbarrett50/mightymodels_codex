"""Codex open-ticket must pause for actual user input instead of fake dialogs."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = GENERATOR['translated']
native_open_ticket_decisions = GENERATOR['native_open_ticket_decisions']


@pytest.mark.unit
def test_open_ticket_decisions_are_blocking_and_generated_output_is_current() -> None:
    generated = translated(ROOT / 'skills/open-ticket/SKILL.md')
    assert 'ask only unanswered interview questions in ordinary chat' in generated
    assert 'end the turn until the user explicitly responds' in ' '.join(generated.split())
    assert 'then call `ticket_write` again using those actual answers' in generated
    assert 'Ask once in ordinary chat, then end the turn' in generated
    assert 'One `Codex user decision gate` dialog' not in generated
    assert 'one `Codex user decision gate` dialog' not in generated
    assert generated == (ROOT / '.codex/skills/open-ticket/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_missing_open_ticket_questions_are_not_silently_accepted() -> None:
    with pytest.raises(ValueError, match='exactly one open-ticket decision instruction'):
        native_open_ticket_decisions('No interview steps available')
