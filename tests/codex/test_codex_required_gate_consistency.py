"""All Codex skill gates use one fail-closed user-input policy."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = sorted((ROOT / 'skills').glob('*/SKILL.md'))


@pytest.mark.unit
@pytest.mark.parametrize('path', SKILLS, ids=lambda path: path.parent.name)
def test_required_user_input_contract_present(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    assert 'Codex required user-input contract (all skills)' in text
    assert 'In Default mode, a question that gates further action MUST be asked' in text
    assert 'automatic resolution never count as consent' in text
    assert 'This is Codex-only' in text


@pytest.mark.unit
def test_no_conflicting_old_codex_gate_preambles() -> None:
    for name in ('lets-investigate', 'what-we-know', 'ask-an-adult'):
        body = (ROOT / 'skills' / name / 'SKILL.md').read_text(encoding='utf-8')
        assert '**Codex user-question gates:**' not in body
        assert '**Codex interactive-mode questions:**' not in body
        assert '**Codex user decision gate:**' not in body
