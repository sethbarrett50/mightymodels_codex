"""Native Codex assembly escalation must request explicit user input."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))


@pytest.mark.unit
def test_assembly_escalation_uses_native_tool() -> None:
    generated = SYNC['translated'](ROOT / 'skills/agents-assemble/SKILL.md')
    assert generated == (ROOT / '.codex/skills/agents-assemble/SKILL.md').read_text()
    assert 'Off → invoke native `request_user_input` in Default or Plan mode' in generated
    assert 'keep escalation pending' in generated
    assert 'Off → ask the user in ordinary chat' not in generated


@pytest.mark.unit
def test_assembly_translation_detects_source_drift() -> None:
    with pytest.raises(ValueError, match='exactly one assembly dispatch or decision instruction'):
        SYNC['native_assembly_roles']('missing')
