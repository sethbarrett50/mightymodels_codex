'''Regression checks for native Codex task-split approval instructions.'''

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_task_split_decisions = SYNC['native_task_split_decisions']
native_task_split_frontmatter = SYNC['native_task_split_frontmatter']


@pytest.mark.unit
def test_task_split_requires_real_chat_approval() -> None:
    generated = translate(ROOT / 'skills/break-it-down/SKILL.md')
    assert 'Ends by asking in ordinary chat' in generated
    assert 'Until the user explicitly answers the blocking question' in generated
    assert 'ask again in\nordinary chat' in generated
    assert 'do not\nask in prose instead' not in generated
    assert 'Until the dialog in step 4' not in generated
    assert 'Ends in one Codex user decision gate dialog' not in generated
    assert generated == (ROOT / '.codex/skills/break-it-down/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_task_split_translation_fails_closed_on_source_drift() -> None:
    with pytest.raises(ValueError, match='exactly one task split approval instruction'):
        native_task_split_decisions('missing')
    with pytest.raises(ValueError, match='exactly one task split frontmatter dialog'):
        native_task_split_frontmatter('missing')
