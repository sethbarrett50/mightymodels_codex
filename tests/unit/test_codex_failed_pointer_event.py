"""Do not persist pointers based on explicitly unsuccessful MCP tool calls."""

import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = run_path(str(ROOT / 'hooks/codex_bridge.py'))
translate_pointer_event = BRIDGE['translate_pointer_event']


def event(response: object) -> dict[str, object]:
    return {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'mcp__mighty_mcp__ticket_show',
        'session_id': 'session-one',
        'cwd': str(ROOT),
        'tool_input': {'slug': 'ticket-one'},
        'tool_response': response,
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'response',
    [
        {'isError': True},
        {'status': 'failed'},
        {'status': 'error'},
        '{"isError": true, "content": "private"}',
        json.dumps({'status': 'failed', 'text': 'private'}),
    ],
)
def test_explicit_failed_mcp_calls_do_not_update_session_pointer(response: object) -> None:
    assert translate_pointer_event(event(response)) is None


@pytest.mark.unit
@pytest.mark.parametrize('response', [None, {'isError': False}, {'status': 'success'}])
def test_success_or_legacy_unspecified_outcome_keeps_pointer_compatibility(
    response: object,
) -> None:
    translated = translate_pointer_event(event(response))
    assert translated is not None
    assert translated['tool_input'] == {'slug': 'ticket-one'}
    assert 'tool_response' not in translated


@pytest.mark.unit
def test_failed_tool_response_never_leaks_raw_text() -> None:
    result = translate_pointer_event(
        event({'status': 'failed', 'content': 'sensitive secret material'})
    )
    assert result is None
