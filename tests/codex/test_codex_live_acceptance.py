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
        args=[],
        returncode=0,
        stdout='{"type":"turn.completed","usage":{"input_tokens":15}}\n'
        '{"type":"item.completed","item":{"text":"SECRET_API_KEY_DO_NOT_LOG"}}\n',
        stderr='SECRET_AUTH_LOG_DO_NOT_LOG',
    )
    result = SCRIPT.summarize_result(completed, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert result['status'] == 'read_only_smoke_completed'
    assert result['fixture_unchanged'] is True
    assert result['usage']['input_tokens'] == 15
    assert result['host_denial_verified'] is False
    assert result['child_model_verified'] is False
    assert result['secret_transcripts_retained'] is False
    assert 'SECRET_' not in str(result)


@pytest.mark.unit
def test_failed_executable_and_suspicious_version_are_not_reported_as_success() -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=1,
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


@pytest.mark.unit
def test_disposable_fixture_snapshot_detects_modification_and_extra_files(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('baseline', encoding='utf-8')
    baseline = SCRIPT.fixture_snapshot(tmp_path)
    (tmp_path / 'README.md').write_text('modified', encoding='utf-8')
    assert SCRIPT.fixture_snapshot(tmp_path) != baseline
    (tmp_path / 'README.md').write_text('baseline', encoding='utf-8')
    assert SCRIPT.fixture_snapshot(tmp_path) == baseline
    (tmp_path / 'unexpected.txt').write_text('marker', encoding='utf-8')
    assert SCRIPT.fixture_snapshot(tmp_path) != baseline


@pytest.mark.unit
def test_fixture_mutation_cannot_be_reported_as_read_only_success() -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout='{"type":"turn.completed","usage":{"input_tokens":8}}\n',
        stderr='',
    )
    report = SCRIPT.summarize_result(
        completed, version='codex-cli 0.167.0', fixture_unchanged=False
    )
    assert report['status'] == 'read_only_smoke_unverified'
    assert report['fixture_unchanged'] is False
    assert report['host_denial_verified'] is False


@pytest.mark.unit
def test_fixture_snapshot_detects_symlink_retargeting(tmp_path: Path) -> None:
    (tmp_path / 'first.txt').write_text('same', encoding='utf-8')
    (tmp_path / 'second.txt').write_text('same', encoding='utf-8')
    link = tmp_path / 'shortcut.txt'
    link.symlink_to('first.txt')
    baseline = SCRIPT.fixture_snapshot(tmp_path)
    link.unlink()
    link.symlink_to('second.txt')
    assert SCRIPT.fixture_snapshot(tmp_path) != baseline
    # The fingerprint is a digest, never the raw destination.
    link_record = next(row for row in SCRIPT.fixture_snapshot(tmp_path) if row[0] == 'shortcut.txt')
    assert link_record[2] != 'second.txt'


@pytest.mark.unit
def test_fixture_snapshot_does_not_follow_external_symlinks(tmp_path: Path) -> None:
    link = tmp_path / 'external.txt'
    link.symlink_to('../outside.txt')
    before = SCRIPT.fixture_snapshot(tmp_path)
    assert SCRIPT.fixture_snapshot(tmp_path) == before


@pytest.mark.unit
def test_multibyte_output_exceeding_byte_limit_is_rejected() -> None:
    # Fewer than one million Unicode code points, but more than one million bytes.
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout='界' * 400000, stderr='')
    report = SCRIPT.summarize_result(completed, version='codex-cli 0.167.0', fixture_unchanged=True)
    assert report['status'].startswith('unverified:')
    assert '界' not in str(report)


@pytest.mark.unit
@pytest.mark.parametrize('problem', ['error', 'turn.failed'])
def test_completed_turn_with_streamed_error_is_not_clean_acceptance(problem: str) -> None:
    completed = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=(
            '{"type":"turn.completed","usage":{"input_tokens":15}}\n'
            + '{"type":"' + problem + '","message":"SECRET_DO_NOT_ECHO"}\n'
        ),
        stderr='',
    )
    report = SCRIPT.summarize_result(
        completed, version='codex-cli 0.167.0', fixture_unchanged=True
    )
    assert report['status'] == 'read_only_smoke_unverified'
    assert report['fixture_unchanged'] is True
    assert report['failure_category'] == 'unclassified'
    assert 'SECRET_' not in str(report)
