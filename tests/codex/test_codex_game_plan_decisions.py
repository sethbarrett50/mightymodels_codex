"""Generated game-plan instructions must use native Codex questions."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_game_plan_decisions = SYNC['native_game_plan_decisions']


@pytest.mark.unit
def test_generated_game_plan_uses_native_questions_for_all_three_gates() -> None:
    generated = translate(ROOT / 'skills/game-plan/SKILL.md')
    assert 'Invoke native `request_user_input` when exposed, at most four risks per call' in generated
    assert 'Invoke native `request_user_input` for one question' in generated
    assert 'stop for an explicit choice: approve, revise, or abandon' in generated
    assert 'If native input is unavailable, leave the risk handling pending' in generated
    assert 'If native input is unavailable, leave the escalation choice pending' in generated
    assert 'ask in chat with both answers' not in generated
    assert 'One `Codex user decision gate` dialog' not in generated
    assert generated == (ROOT / '.codex/skills/game-plan/SKILL.md').read_text(encoding='utf-8')


@pytest.mark.unit
def test_game_plan_translation_rejects_missing_required_step() -> None:
    with pytest.raises(ValueError, match='exactly one game-plan user decision instruction'):
        native_game_plan_decisions('no real decision procedure')
