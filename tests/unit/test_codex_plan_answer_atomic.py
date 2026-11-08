"""Do not treat an incomplete Codex Plan-mode dialog as persisted decisions."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
translate_plan_answers = run_path(str(ROOT / 'hooks/codex_bridge.py'))['translate_plan_answers']


def request(
    *,
    second: object = None,
    secret: bool = False,
) -> dict[str, object]:
    return {
        'hook_event_name': 'PostToolUse',
        'permission_mode': 'plan',
        'session_id': 'session-1',
        'cwd': str(ROOT),
        'tool_input': {
            'questions': [
                {'id': 'one', 'question': 'First decision?'},
                {'id': 'two', 'question': 'Second decision?', 'is_secret': secret},
            ]
        },
        'tool_response': {
            'answers': {
                'one': {'answers': ['approve']},
                **({'two': second} if second is not None else {}),
            }
        },
    }


@pytest.mark.unit
def test_incomplete_nonsecret_dialog_is_not_forwarded() -> None:
    assert translate_plan_answers(request()) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    'missing',
    [
        {'answers': []},
        {'answers': ['   ']},
        {'answers': ['']},
        {'answers': [None]},
        'not a selection object',
    ],
)
def test_empty_or_invalid_nonsecret_answer_rejects_entire_batch(missing: object) -> None:
    assert translate_plan_answers(request(second=missing)) is None


@pytest.mark.unit
def test_all_explicit_nonsecret_answers_are_forwarded() -> None:
    translated = translate_plan_answers(request(second={'answers': ['revise']}))
    assert translated is not None
    assert translated['tool_response']['answers'] == {
        'First decision?': 'approve',
        'Second decision?': 'revise',
    }


@pytest.mark.unit
def test_secret_question_is_never_forwarded_and_does_not_block_public_answer() -> None:
    translated = translate_plan_answers(request(second={'answers': ['PRIVATE']}, secret=True))
    assert translated is not None
    assert translated['tool_response']['answers'] == {'First decision?': 'approve'}
    assert 'PRIVATE' not in str(translated)


@pytest.mark.unit
def test_default_mode_never_persists_dialog_without_explicit_plan_mode() -> None:
    incoming = request(second={'answers': ['revise']})
    incoming['permission_mode'] = 'default'
    assert translate_plan_answers(incoming) is None
