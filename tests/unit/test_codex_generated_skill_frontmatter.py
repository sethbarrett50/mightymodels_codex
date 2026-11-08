"""Generated skill metadata must not misstate Codex decision gates or model scope."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = SYNC['translated']
native_baton_pass_frontmatter = SYNC['native_baton_pass_frontmatter']


@pytest.mark.unit
def test_baton_pass_summary_requires_real_chat_answers() -> None:
    generated = translated(ROOT / 'skills/baton-pass/SKILL.md')
    assert generated == (ROOT / '.codex/skills/baton-pass/SKILL.md').read_text(encoding='utf-8')
    front = generated.split('---', 2)[1]
    assert 'asks in ordinary chat' in front
    assert 'awaits explicit user answers' in front
    assert 'Codex user decision gate' not in front
    assert 'asks in one' not in front


@pytest.mark.unit
def test_review_summary_keeps_native_model_pins_fixed() -> None:
    generated = translated(ROOT / 'skills/review-circus/SKILL.md')
    assert generated == (ROOT / '.codex/skills/review-circus/SKILL.md').read_text(
        encoding='utf-8'
    )
    front = generated.split('---', 2)[1]
    assert 'review depth (quick, standard, deep), persona' in front
    assert 'scope without changing native reviewer model pins' in front
    assert 'model pins, persona' not in front


@pytest.mark.unit
def test_baton_pass_frontmatter_translation_rejects_source_drift() -> None:
    with pytest.raises(ValueError, match='baton-pass frontmatter decision clause'):
        native_baton_pass_frontmatter('unknown')
