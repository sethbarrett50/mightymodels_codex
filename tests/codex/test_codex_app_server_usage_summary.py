"""Synthetic App Server notifications must never leak content or overclaim usage."""

import io
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
OBSERVER = SimpleNamespace(**runpy.run_path(
    str(ROOT / 'scripts/codex_app_server_usage_summary.py')
))


def _stream(*events: dict) -> io.StringIO:
    return io.StringIO(''.join(json.dumps(e) + '\n' for e in events))


def _thread(identity: str, parent: str | None, role: str = 'mm-triage-code-scout') -> dict:
    return {
        'method': 'thread/started',
        'params': {'thread': {
            'id': identity, 'parentThreadId': parent, 'agentRole': role,
            'model': 'SECRET_CONFIG', 'preview': 'PRIVATE_PROMPT',
        }},
    }


def _usage(identity: str, input_tokens: int, output: int, reasoning: int = 0) -> dict:
    return {
        'method': 'thread/tokenUsage/updated',
        'params': {
            'threadId': identity, 'turnId': 'SECRET_TURN',
            'tokenUsage': {'total': {
                'inputTokens': input_tokens, 'cachedInputTokens': 0,
                'outputTokens': output, 'reasoningOutputTokens': reasoning,
                'totalTokens': input_tokens + output,
            }},
        },
    }


@pytest.mark.unit
def test_child_usage_is_observed_only_and_cumulative_not_added_twice() -> None:
    report = OBSERVER.summarize(_stream(
        _usage('child-private', 10, 2),
        _thread('parent-private', None),
        _thread('child-private', 'parent-private'),
        _usage('child-private', 20, 4),
        _usage('parent-private', 1000, 500),
    ))
    assert report['observed_children'] == 1
    assert report['children_with_valid_usage'] == 1
    assert report['observed_child_roles'] == {'mm-triage-code-scout': 1}
    assert report['observed_child_token_totals']['inputTokens'] == 20
    assert report['observed_child_token_totals']['outputTokens'] == 4
    assert report['complete_child_usage_verified'] is False
    assert report['quota_savings'] == 'not_measured'
    assert 'PRIVATE_' not in json.dumps(report)
    assert 'SECRET_' not in json.dumps(report)
    assert 'child-private' not in json.dumps(report)


@pytest.mark.unit
def test_missing_usage_is_not_zero() -> None:
    report = OBSERVER.summarize(_stream(_thread('child', 'parent')))
    assert report['children_without_valid_usage'] == 1
    assert report['observed_child_token_totals'] is None


@pytest.mark.unit
def test_invalid_or_regressing_usage_is_excluded() -> None:
    bad = _usage('child', 10, 2, 3)
    report = OBSERVER.summarize(_stream(
        _thread('child', 'parent'), bad, _usage('child', 20, 2)
    ))
    assert report['children_with_valid_usage'] == 0
    assert report['errors']['invalid_usage_notifications'] == 1

    report = OBSERVER.summarize(_stream(
        _thread('child', 'parent'),
        _usage('child', 20, 3),
        _usage('child', 10, 3),
    ))
    assert report['children_with_valid_usage'] == 0
    assert report['errors']['regressing_usage_notifications'] == 1


@pytest.mark.unit
def test_unrecognized_role_never_echoed() -> None:
    report = OBSERVER.summarize(_stream(
        _thread('child', 'parent', 'PRIVATE_ROLE'), _usage('child', 10, 2)
    ))
    assert report['observed_child_roles'] == {'other': 1}
    assert 'PRIVATE_ROLE' not in json.dumps(report)


@pytest.mark.unit
def test_malformed_stream_is_counted_without_echo() -> None:
    report = OBSERVER.summarize(io.StringIO(
        '{PRIVATE_RAW\n' + json.dumps(_thread('child', 'parent')) + '\n'
    ))
    assert report['errors']['invalid_events'] == 1
    assert report['observed_children'] == 1
    assert 'PRIVATE_RAW' not in json.dumps(report)


@pytest.mark.unit
def test_parentless_and_unobserved_child_usage_are_excluded() -> None:
    report = OBSERVER.summarize(_stream(
        _thread('parent', None), _usage('parent', 100, 10),
        _usage('unmatched', 1000, 100),
    ))
    assert report['observed_children'] == 0
    assert report['observed_child_token_totals'] is None
