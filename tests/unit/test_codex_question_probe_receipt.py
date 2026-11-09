"""Opt-in Codex question hook receipt never stores answer data."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
question_probe_receipt = run_path(str(ROOT / 'hooks/codex_bridge.py'))['question_probe_receipt']


@pytest.mark.unit
def test_question_probe_off_does_not_write(tmp_path: Path) -> None:
    event = {'hook_event_name': 'PostToolUse', 'tool_name': 'request_user_input'}
    question_probe_receipt(event, {'HOME': str(tmp_path)})
    assert not (tmp_path / '.local/state/mightymodels/codex-question-probe.log').exists()


@pytest.mark.unit
def test_question_probe_records_only_structural_boolean_fields(tmp_path: Path) -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'default',
        'session_id': 'SECRET_SESSION_123',
        'tool_input': {'questions': [{'id': 'a', 'question': 'SECRET_QUESTION_123'}]},
        'tool_response': {'answers': {'a': {'answers': ['SECRET_ANSWER_123']}}},
    }
    question_probe_receipt(
        event,
        {'HOME': str(tmp_path), 'MIGHTYMODELS_CODEX_QUESTION_PROBE': '1'},
    )
    path = tmp_path / '.local/state/mightymodels/codex-question-probe.log'
    record = path.read_text(encoding='utf-8')
    assert 'mode=default' in record
    assert 'answers_object=True' in record
    assert 'timeout_field=False' in record
    assert 'SECRET_' not in record
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.unit
def test_question_probe_does_not_treat_presence_as_consent(tmp_path: Path) -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'default',
        'tool_response': {'answers': {}, 'afkTimeoutMs': None},
    }
    question_probe_receipt(
        event,
        {'HOME': str(tmp_path), 'MIGHTYMODELS_CODEX_QUESTION_PROBE': '1'},
    )
    record = (tmp_path / '.local/state/mightymodels/codex-question-probe.log').read_text()
    assert 'answers_object=True' in record
    assert 'timeout_field=True' in record
    assert 'approved' not in record
