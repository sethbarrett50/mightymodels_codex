"""Live acceptance CLI reports are sanitized and never echo model transcripts."""

import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
SCRIPT = SimpleNamespace(**runpy.run_path(str(ROOT / 'scripts/codex_live_acceptance.py')))


@pytest.mark.unit
def test_successful_read_only_smoke_emits_only_counters_and_unverified_flags() -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0,
        stdout='{"type":"turn.completed","usage":{"input_tokens":15}}\n'
        '{"type":"item.completed","item":{"text":"SECRET_API_KEY_DO_NOT_LOG"}}\n',
        stderr='SECRET_AUTH_LOG_DO_NOT_LOG',
    )
    result = SCRIPT.summarize_result(completed, version='codex-cli 0.167.0')
    assert result['status'] == 'read_only_smoke_completed'
    assert result['usage']['input_tokens'] == 15
    assert result['host_denial_verified'] is False
    assert result['child_model_verified'] is False
    assert result['secret_transcripts_retained'] is False
    assert 'SECRET_' not in str(result)


@pytest.mark.unit
def test_failed_executable_and_suspicious_version_are_not_reported_as_success() -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=1,
        stdout='{"type":"turn.failed","error":"SECRET"}\n',
        stderr='SECRET',
    )
    result = SCRIPT.summarize_result(completed, version='codex-cli 0.1\nSECRET_LOG')
    assert result['status'] == 'read_only_smoke_unverified'
    assert result['codex_version'] == 'unverified'
    assert 'SECRET' not in str(result)


@pytest.mark.unit
def test_oversize_output_is_never_echoed_or_called_complete() -> None:
    completed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='SECRET' * 170000, stderr=''
    )
    result = SCRIPT.summarize_result(completed, version='codex-cli 0.167.0')
    assert result['status'].startswith('unverified:')
    assert 'SECRET' not in str(result)
