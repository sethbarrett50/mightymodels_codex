"""Generated task splitting asks for real user approval, not a fake dialog."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = SYNC['translated']
native_task_split_decisions = SYNC['native_task_split_decisions']


@pytest.mark.unit
def test_task_split_needs_explicit_chat_reply() -> None:
    output = translated(ROOT / 'skills/break-it-down/SKILL.md')
    assert 'then ask in ordinary chat whether to split, keep, or revise' in output
    assert 'End the turn until the user explicitly responds.' in output
    assert 'as the user explicitly approved' in output
    assert 'open one\\n`Codex user decision gate`' not in output
    assert output == (ROOT / '.codex/skills/break-it-down/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_task_split_translation_rejects_missing_source_instruction() -> None:
    with pytest.raises(ValueError, match='exactly one task split approval instruction'):
        native_task_split_decisions('missing')
