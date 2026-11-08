"""Read-only smoke must reject explicitly observed out-of-scope Codex actions."""

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


def make_trace(*events: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=['codex'], returncode=0, stdout=''.join(json.dumps(x) + '\n' for x in events)
    )


@pytest.mark.unit
def test_bounded_clean_smoke_can_complete() -> None:
    trace = make_trace({'type': 'turn.completed', 'usage': {}})
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['status'] == 'read_only_smoke_completed'
    assert report['observed_scope_violation'] is False
    assert report['child_model_verified'] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    'item_type',
    ['collab_tool_call', 'file_change'],
)
def test_observed_out_of_scope_actions_invalidate_smoke(item_type: str) -> None:
    trace = make_trace(
        {'type': 'item.started', 'item': {'type': item_type, 'tool': 'spawn_agent'}},
        {'type': 'turn.completed', 'usage': {}},
    )
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['status'] == 'read_only_smoke_unverified'
    assert report['observed_scope_violation'] is True
    assert report['host_denial_verified'] is False


@pytest.mark.unit
def test_fixture_change_invalidates_smoke_without_streamed_event() -> None:
    trace = make_trace({'type': 'turn.completed', 'usage': {}})
    report = summarize_result(trace, version='codex-cli 0.167.0', fixture_unchanged=False)
    assert report['status'] == 'read_only_smoke_unverified'
    assert report['observed_scope_violation'] is False
