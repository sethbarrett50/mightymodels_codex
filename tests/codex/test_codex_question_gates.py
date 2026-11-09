"""Codex question-gate instructions must require real tool invocation."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize(
    'path',
    [
        'AGENTS.md',
        'skills/lets-investigate/SKILL.md',
        'skills/what-we-know/SKILL.md',
        'skills/ask-an-adult/SKILL.md',
    ],
)
def test_codex_user_gates_use_native_tool(path: str) -> None:
    content = (ROOT / path).read_text(encoding='utf-8')
    assert 'request_user_input' in content
    assert 'free-text' in content
    assert 'AskUserQuestion' in content


@pytest.mark.unit
def test_codex_question_gate_docs_keep_user_setting_separate() -> None:
    docs = (ROOT / 'docs/CODEX.md').read_text(encoding='utf-8')
    assert 'default_mode_request_user_input = true' in docs
    assert 'not' in docs.lower()
    assert 'timeout' in docs.lower()


@pytest.mark.unit
def test_codex_docs_never_direct_required_gates_to_plain_chat() -> None:
    docs = (ROOT / 'docs/CODEX.md').read_text(encoding='utf-8')
    assert 'required decisions still use ordinary chat' not in docs
    assert 'Do not suppress the interactive UI merely because the session is in Default' in docs
    assert 'the gate remains pending and the user must switch to Plan mode' in docs
    assert 'claiming a popup opened counts as tool invocation' in docs


@pytest.mark.unit
def test_default_mode_native_choices_are_not_approval() -> None:
    instructions = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
    assert 'do **not** refuse to ask solely' in instructions
    assert 'Default-mode dialogs may auto-resolve' in instructions
    assert 'leave the gate pending' in instructions
