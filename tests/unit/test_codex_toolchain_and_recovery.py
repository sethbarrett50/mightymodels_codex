"""Codex-generated planning and recovery instructions must use actual native tools."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
translated = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))['translated']


@pytest.mark.unit
def test_toolchain_scout_uses_registered_codex_role() -> None:
    generated = translated(ROOT / 'skills/game-plan/SKILL.md')
    assert 'agent_type=mm-triage-terry-toolchain' in generated
    assert 'dispatch\n`mightymodels:triage:terry-toolchain` on `sonnet`' not in generated
    assert generated == (ROOT / '.codex/skills/game-plan/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_failure_recovery_requires_native_explicit_answer() -> None:
    generated = translated(ROOT / 'skills/whats-broken/SKILL.md')
    assert 'invoke native `request_user_input` when exposed' in generated
    assert 'present evidence to the user in ordinary chat' not in generated
    assert generated == (ROOT / '.codex/skills/whats-broken/SKILL.md').read_text(encoding='utf-8')
