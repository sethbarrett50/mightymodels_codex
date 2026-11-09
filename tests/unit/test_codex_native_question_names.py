"""Generated Codex skill decisions name the real host tool, not a fake dialog."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
translated = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))['translated']


@pytest.mark.unit
@pytest.mark.parametrize(
    'name', ['cross-examine', 'game-plan', 'one-shot', 'prune-ticket', 'what-we-know']
)
def test_native_question_instructions_do_not_name_fake_tool(name: str) -> None:
    generated = translated(ROOT / 'skills' / name / 'SKILL.md')
    assert 'Codex user decision gate' not in generated
    assert 'native `request_user_input`' in generated
    assert generated == (ROOT / '.codex/skills' / name / 'SKILL.md').read_text(encoding='utf-8')
