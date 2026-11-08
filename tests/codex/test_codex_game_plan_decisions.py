"""Generated game-plan instructions must block on real Codex chat decisions."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translate = SYNC['translated']
native_game_plan_decisions = SYNC['native_game_plan_decisions']


@pytest.mark.unit
def test_generated_game_plan_uses_chat_for_all_three_decision_gates() -> None:
    generated = translate(ROOT / 'skills/game-plan/SKILL.md')
    assert 'Ask in ordinary chat, at most four risks per turn' in generated
    assert 'Ask one blocking question in ordinary chat' in generated
    assert 'stop for an explicit choice: approve, revise, or abandon' in generated
    assert 'One `Codex user decision gate` dialog' not in generated
    assert generated == (ROOT / '.codex/skills/game-plan/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_game_plan_translation_rejects_missing_required_step() -> None:
    with pytest.raises(ValueError, match='exactly one game-plan user decision instruction'):
        native_game_plan_decisions('no real decision procedure')
