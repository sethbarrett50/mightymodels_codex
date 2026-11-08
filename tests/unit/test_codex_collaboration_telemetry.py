"""Codex collaboration telemetry counts only observed JSONL operations."""

import io
import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
summarize = run_path(str(ROOT / 'scripts/codex_trace_summary.py'))['summarize']


@pytest.mark.unit
def test_collaboration_counts_exclude_prompts_and_agent_ids() -> None:
    events = [
        {'type': 'item.started', 'item': {
            'type': 'collab_tool_call', 'tool': 'spawn_agent',
            'prompt': 'do-not-log-secret', 'receiver_thread_ids': ['private-id'],
        }},
        {'type': 'item.completed', 'item': {
            'type': 'collab_tool_call', 'tool': 'spawn_agent',
        }},
        {'type': 'item.started', 'item': {
            'type': 'collab_tool_call', 'tool': 'wait', 'receiver_thread_ids': ['private-id'],
        }},
        {'type': 'turn.completed', 'usage': {'input_tokens': 14, 'output_tokens': 2}},
    ]
    report = summarize(io.StringIO(''.join(json.dumps(x) + '\n' for x in events)))
    assert report['events']['collaboration_calls'] == 2
    assert report['events']['agent_spawn_calls_streamed'] == 1
    assert report['events']['agent_wait_calls_streamed'] == 1
    assert report['usage']['input_tokens'] == 14
    serialized = json.dumps(report)
    assert 'do-not-log-secret' not in serialized
    assert 'private-id' not in serialized


@pytest.mark.unit
def test_missing_spawn_event_does_not_claim_no_dispatch() -> None:
    events = [
        {'type': 'item.started', 'item': {'type': 'collab_tool_call', 'tool': 'wait'}},
        {'type': 'turn.completed', 'usage': {}},
    ]
    report = summarize(io.StringIO(''.join(json.dumps(x) + '\n' for x in events)))
    assert report['events']['agent_wait_calls_streamed'] == 1
    assert 'agent_spawn_calls_streamed' not in report['events']
    assert report['agent_dispatch_observability'].startswith('partial:')
    assert report['effective_model_identity'] == 'unverified'


@pytest.mark.unit
def test_unknown_collaboration_tool_is_counted_not_named() -> None:
    trace = json.dumps({'type': 'item.started', 'item': {
        'type': 'collab_tool_call', 'tool': 'private-custom-tool',
        'prompt': 'secret',
    }})
    report = summarize(io.StringIO(trace + '\n'))
    assert report['events']['other_collaboration_calls_streamed'] == 1
    assert 'private-custom-tool' not in json.dumps(report)
