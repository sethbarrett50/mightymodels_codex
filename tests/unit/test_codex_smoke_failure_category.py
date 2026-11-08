"""Failed Codex smoke reports sanitized failure hints without leaking content."""

import json
import subprocess
import sys
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    SCRIPT = run_path(str(ROOT / 'scripts/codex_live_acceptance.py'))
summarize_result = SCRIPT['summarize_result']


@pytest.mark.unit
@pytest.mark.parametrize(
    ('message', 'expected'),
    [
        ('You have hit your limit. Try again in 5 hours.', 'possible_usage_or_rate_limit'),
        ('Rate limit exceeded for this organization', 'possible_usage_or_rate_limit'),
        ('insufficient_quota', 'possible_usage_or_rate_limit'),
        ('Authentication failed for request', 'possible_authentication_problem'),
        ('Unexpected upstream error', 'unclassified'),
    ],
)
def test_bounded_error_classification_keeps_messages_private(message: str, expected: str) -> None:
    events = [
        {'type': 'turn.started'},
        {'type': 'error', 'message': message + ' confidential-client-prompt'},
        {'type': 'turn.failed', 'error': {'message': message}},
    ]
    trace = subprocess.CompletedProcess(
        args=['codex'],
        returncode=1,
        stdout=''.join(json.dumps(event) + '\n' for event in events),
        stderr='private-stderr',
    )
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['status'] == 'read_only_smoke_unverified'
    assert report['failure_category'] == expected
    assert 'confidential-client-prompt' not in json.dumps(report)
    assert 'private-stderr' not in json.dumps(report)
    assert message not in json.dumps(report)


@pytest.mark.unit
def test_failed_turn_without_error_message_remains_unclassified() -> None:
    trace = subprocess.CompletedProcess(
        args=['codex'],
        returncode=1,
        stdout='{"type":"turn.started"}\n{"type":"error"}\n{"type":"turn.failed"}\n',
        stderr='',
    )
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['failure_category'] == 'unclassified'
    assert report['usage']['input_tokens'] == 0


@pytest.mark.unit
def test_success_has_no_failure_category() -> None:
    trace = subprocess.CompletedProcess(
        args=['codex'],
        returncode=0,
        stdout='{"type":"turn.completed","usage":{}}\n',
        stderr='',
    )
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['status'] == 'read_only_smoke_completed'
    assert 'failure_category' not in report


@pytest.mark.unit
def test_unexpected_nonzero_exit_is_distinguished_without_logging_stderr() -> None:
    trace = subprocess.CompletedProcess(
        args=['codex'],
        returncode=1,
        stdout='{"type":"turn.started"}\n',
        stderr='some secret error',
    )
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['failure_category'] == 'nonzero_exit_without_streamed_failure'
    assert 'some secret error' not in json.dumps(report)
