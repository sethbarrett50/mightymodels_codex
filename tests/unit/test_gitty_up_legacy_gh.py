"""gitty-up checks remain safe when gh pr checks lacks --json."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'bin/gitty-up'


@pytest.fixture
def fake_gh(tmp_path: Path) -> Path:
    tool = tmp_path / 'gh'
    tool.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = pr ] && [ "$2" = view ]; then\n'
        '  if [ "${GITTY_FAKE_ERROR:-}" = 1 ]; then\n'
        '    echo "API unavailable" >&2\n'
        '    exit 1\n'
        '  fi\n'
        '  printf "%s\\n" "$GITTY_FAKE_ROLLUP"\n'
        'else\n'
        '  echo "unsupported gh command: $*" >&2\n'
        '  exit 2\n'
        'fi\n'
    )
    tool.chmod(0o755)
    return tmp_path


def run_gitty(
    fake_gh: Path, checks: object, command: str, *, api_error: bool = False
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env['PATH'] = str(fake_gh) + os.pathsep + env['PATH']
    env['GITTY_FAKE_ROLLUP'] = json.dumps({'statusCheckRollup': checks})
    env['GITTY_FAKE_ERROR'] = '1' if api_error else '0'
    args = [str(SCRIPT), command, '--pr', '254']
    if command == 'wait':
        args.extend(['--deadline', '1', '--register-by', '1'])
    return subprocess.run(  # noqa: S603
        args, env=env, capture_output=True, text=True, timeout=10, check=False
    )


@pytest.mark.unit
@pytest.mark.skipif(shutil.which('jq') is None, reason='jq required')
def test_legacy_gh_rollup_success_and_skip(fake_gh: Path) -> None:
    checks = [
        {'__typename': 'CheckRun', 'name': 'tests', 'status': 'COMPLETED',
         'conclusion': 'SUCCESS', 'detailsUrl': 'https://example.test/test'},
        {'__typename': 'StatusContext', 'context': 'lint', 'state': 'SUCCESS',
         'targetUrl': 'https://example.test/lint'},
        {'__typename': 'CheckRun', 'name': 'optional', 'status': 'COMPLETED',
         'conclusion': 'SKIPPED', 'detailsUrl': 'https://example.test/skip'},
    ]
    wait = run_gitty(fake_gh, checks, 'wait')
    verdict = run_gitty(fake_gh, checks, 'verdict')
    assert wait.returncode == 0 and 'GITTY SETTLED' in wait.stdout
    assert verdict.returncode == 0 and 'GITTY VERDICT pass' in verdict.stdout
    assert 'pass\ttests\thttps://example.test/test' in verdict.stdout
    assert 'pass\tlint\thttps://example.test/lint' in verdict.stdout
    assert 'skipping\toptional' in verdict.stdout


@pytest.mark.unit
@pytest.mark.skipif(shutil.which('jq') is None, reason='jq required')
def test_pending_and_missing_checks_never_pass(fake_gh: Path) -> None:
    pending = [{'__typename': 'CheckRun', 'name': 'CI', 'status': 'IN_PROGRESS'}]
    assert 'GITTY TIMEOUT pending=1' in run_gitty(fake_gh, pending, 'wait').stdout
    assert 'GITTY VERDICT error' in run_gitty(fake_gh, pending, 'verdict').stdout
    assert 'GITTY NO_CHECKS' in run_gitty(fake_gh, [], 'wait').stdout
    assert 'GITTY VERDICT error' in run_gitty(fake_gh, [], 'verdict').stdout


@pytest.mark.unit
@pytest.mark.skipif(shutil.which('jq') is None, reason='jq required')
@pytest.mark.parametrize(
    'check',
    [
        {'__typename': 'CheckRun', 'name': 'CI', 'status': 'COMPLETED',
         'conclusion': 'FAILURE'},
        {'__typename': 'StatusContext', 'context': 'CI', 'state': 'ERROR'},
        {'__typename': 'CheckRun', 'name': 'CI', 'status': 'COMPLETED',
         'conclusion': 'CANCELLED'},
    ],
)
def test_failed_or_cancelled_checks_never_pass(fake_gh: Path, check: dict[str, object]) -> None:
    result = run_gitty(fake_gh, [check], 'verdict')
    assert result.returncode == 0
    assert 'GITTY VERDICT fail' in result.stdout


@pytest.mark.unit
@pytest.mark.skipif(shutil.which('jq') is None, reason='jq required')
def test_unknown_and_bad_payloads_fail_closed(fake_gh: Path) -> None:
    unknown = [{'__typename': 'CheckRun', 'name': 'CI', 'status': 'COMPLETED',
                'conclusion': 'FUTURE_STATUS'}]
    assert 'GITTY VERDICT error' in run_gitty(fake_gh, unknown, 'verdict').stdout
    bad = run_gitty(fake_gh, None, 'verdict')
    assert bad.returncode == 1 and 'GITTY ERROR' in bad.stdout
    denied = run_gitty(fake_gh, [], 'verdict', api_error=True)
    assert denied.returncode == 1 and 'GITTY ERROR' in denied.stdout
