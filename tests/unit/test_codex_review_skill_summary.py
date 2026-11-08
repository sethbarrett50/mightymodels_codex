"""Review-circus frontmatter must not advertise unavailable Codex UI actions."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = SYNC['translated']
native_review_routing = SYNC['native_review_routing']


@pytest.mark.unit
def test_generated_review_summary_requires_real_user_decisions() -> None:
    generated = translated(ROOT / 'skills/review-circus/SKILL.md')
    assert generated == (ROOT / '.codex/skills/review-circus/SKILL.md').read_text(encoding='utf-8')
    front = generated.split('---', 2)[1]
    assert 'An ordinary-chat decision sets review depth' in front
    assert 'presented by id for explicit ordinary-chat decisions' in front
    assert 'One\n  An ordinary-chat' not in front
    assert 'Codex user decision gate gate' not in front
    assert 'through Codex user decision gate' not in front


@pytest.mark.unit
def test_review_frontmatter_translation_rejects_missing_source_clauses() -> None:
    with pytest.raises(ValueError, match='review routing frontmatter clause'):
        native_review_routing('unknown', 'unknown')
