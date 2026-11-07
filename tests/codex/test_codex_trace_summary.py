"""Codex JSONL telemetry reports do not leak raw agent text or tool arguments."""

import io
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
METRICS = SimpleNamespace(**runpy.run_path(str(ROOT / 'scripts/codex_trace_summary.py')))


@pytest.mark.unit
def test_counts_events_and_token_usage_without_exposing_secret_fields() -> None:
    events = [
        {'type': 'thread.started', 'thread_id': 'SECRET_SESSION_IDENTIFIER'},
        {'type': 'turn.started'},
        {
            'type': 'item.started',
            'item': {'id': 'a', 'type': 'mcp_tool_call', 'arguments': 'TOKEN_SECRET'},
        },
        {
            'type': 'item.completed',
            'item': {'type': 'agent_message', 'text': 'PRIVATE_DISCUSSION'},
        },
        {'type': 'turn.completed', 'usage': {
            'input_tokens': 100,
            'cached_input_tokens': 80,
            'output_tokens': 12,
            'reasoning_output_tokens': 4,
        }},
    ]
    report = METRICS.summarize(io.StringIO(''.join(json.dumps(e) + '\n' for e in events)))
    assert report['events']['mcp_calls'] == 1
    assert report['events']['turn_started'] == 1
    assert report['events']['turn_completed'] == 1
    assert report['usage']['input_tokens'] == 100
    assert report['usage']['cached_input_tokens'] == 80
    assert report['effective_model_identity'] == 'unverified'
    assert report['quota_savings'] == 'not_measured'
    serialized = json.dumps(report)
    assert 'SECRET_SESSION_IDENTIFIER' not in serialized
    assert 'TOKEN_SECRET' not in serialized
    assert 'PRIVATE_DISCUSSION' not in serialized


@pytest.mark.unit
def test_ignores_invalid_usage_values_and_unknown_events() -> None:
    records = [
        {'type': 'turn.completed', 'usage': {
            'input_tokens': True,
            'cached_input_tokens': -1,
            'output_tokens': 'secret',
        }},
        {'type': 'turn.completed', 'usage': {'input_tokens': 7}},
        {'type': 'new-event-with-SECRET'},
    ]
    stream = io.StringIO(''.join(json.dumps(e) + '\n' for e in records) + '{oops\n')
    report = METRICS.summarize(stream)
    assert report['usage']['input_tokens'] == 7
    assert report['usage']['cached_input_tokens'] == 0
    assert report['usage']['output_tokens'] == 0
    assert report['events']['malformed_events'] == 1
    assert report['events']['unknown_events'] == 1


@pytest.mark.unit
def test_records_only_known_item_types_and_does_not_count_item_updates() -> None:
    events = [
        {'type': 'item.started', 'item': {'type': 'command_execution'}},
        {'type': 'item.updated', 'item': {'type': 'command_execution'}},
        {'type': 'item.completed', 'item': {'type': 'command_execution'}},
        {'type': 'item.started', 'item': {'type': 'unknown-secret-type'}},
        {'type': 'turn.failed', 'error': 'SECRET'},
    ]
    report = METRICS.summarize(io.StringIO(''.join(json.dumps(e) + '\n' for e in events)))
    assert report['events']['items_started'] == 2
    assert report['events']['command_executions'] == 1
    assert report['events']['other_items'] == 1
    assert report['events']['turn_failed'] == 1
