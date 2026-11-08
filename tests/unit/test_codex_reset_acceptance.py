"""No-quota preflight and one-attempt live acceptance must not overclaim."""

import sys
from pathlib import Path
from runpy import run_path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    SCRIPT = run_path(str(ROOT / 'scripts/codex_reset_acceptance.py'))
report = SCRIPT['report']


@pytest.mark.unit
def test_preflight_does_not_call_codex_smoke(tmp_path: Path) -> None:
    smoke = Mock()
    with patch.dict(
        report.__globals__,
        {'diagnose': Mock(return_value=(['[OK] installed'], True)), 'run_probe': smoke},
    ):
        result, code = report(home=tmp_path, root=tmp_path, live=False, timeout=90)
    assert code == 0
    assert result['status'] == 'preflight_passed_live_unverified'
    assert result['host_hook_delivery_verified'] is False
    assert result['agent_model_identity_verified'] is False
    smoke.assert_not_called()


@pytest.mark.unit
def test_broken_preflight_blocks_live_smoke_before_token_usage(tmp_path: Path) -> None:
    smoke = Mock()
    with patch.dict(
        report.__globals__,
        {'diagnose': Mock(return_value=(['[FAIL] missing MCP'], False)), 'run_probe': smoke},
    ):
        result, code = report(home=tmp_path, root=tmp_path, live=True, timeout=90)
    assert code == 1
    assert result['status'] == 'blocked: static installation checks failed'
    assert 'smoke' not in result
    smoke.assert_not_called()


@pytest.mark.unit
def test_live_pass_only_validates_smoke_not_other_host_capabilities(tmp_path: Path) -> None:
    smoke = Mock(return_value={'status': 'read_only_smoke_completed', 'fixture_unchanged': True})
    with patch.dict(
        report.__globals__,
        {'diagnose': Mock(return_value=(['[OK] installed'], True)), 'run_probe': smoke},
    ):
        result, code = report(home=tmp_path, root=tmp_path, live=True, timeout=72)
    assert code == 0
    smoke.assert_called_once_with(72)
    assert result['status'] == 'read_only_smoke_passed_host_acceptance_incomplete'
    assert result['full_lifecycle_verified'] is False
    assert result['host_admission_verified'] is False
    assert result['agent_model_identity_verified'] is False


@pytest.mark.unit
def test_rate_limited_smoke_stops_without_retry_or_raw_error(tmp_path: Path) -> None:
    smoke = Mock(
        return_value={
            'status': 'read_only_smoke_unverified',
            'failure_category': 'possible_usage_or_rate_limit',
        }
    )
    with patch.dict(
        report.__globals__,
        {'diagnose': Mock(return_value=([], True)), 'run_probe': smoke},
    ):
        result, code = report(home=tmp_path, root=tmp_path, live=True, timeout=90)
    assert code == 1
    smoke.assert_called_once_with(90)
    assert result['status'] == 'live_smoke_unverified_stop'
    assert 'do not retry automatically' in result['next_action']


@pytest.mark.unit
def test_unclassified_live_failure_is_not_reinterpreted_as_quota(tmp_path: Path) -> None:
    smoke = Mock(return_value={'status': 'unverified: process unavailable or timed out'})
    with patch.dict(
        report.__globals__,
        {'diagnose': Mock(return_value=([], True)), 'run_probe': smoke},
    ):
        result, code = report(home=tmp_path, root=tmp_path, live=True, timeout=90)
    assert code == 1
    smoke.assert_called_once_with(90)
    assert 'quota' not in result['next_action']
