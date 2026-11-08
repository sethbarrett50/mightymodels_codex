"""Regression tests for native Codex review routing and doctrine loading."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_review_routing = SYNC['native_review_routing']


@pytest.mark.unit
def test_generated_review_uses_native_models_and_explicit_doctrine() -> None:
    generated = translate(ROOT / 'skills/review-circus/SKILL.md')
    assert generated == (ROOT / '.codex/skills/review-circus/SKILL.md').read_text(encoding='utf-8')
    assert 'without changing native reviewer model pins' in generated
    assert 'native Codex reviewers use their registered Sol' in generated
    assert 'must explicitly read its installed doctrine skill' in generated
    assert 'preloads its doctrine as a skill' not in generated
    assert 'quick is one persona on sonnet' not in generated


@pytest.mark.unit
def test_review_routing_translation_refuses_source_drift() -> None:
    with pytest.raises(ValueError, match='review routing frontmatter clause'):
        native_review_routing('no review model summary', 'no body')
