"""Opt-in bounded Codex read-only smoke test in a disposable Git repository.

Only sanitized version and aggregate JSONL counters are printed. Full
host-level admission, sandbox and effective model verification require
additional external evidence; this smoke test cannot prove those properties.
"""

import argparse
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_trace_summary import summarize

MAX_OUTPUT_BYTES = 1_000_000
MIN_TIMEOUT = 15
MAX_TIMEOUT = 300
PROBE_ERRORS = (OSError, subprocess.TimeoutExpired, ValueError)
PROMPT = (
    'Read-only acceptance probe: inspect README.md and report its one-line purpose. '
    'Do not edit any files, install packages, dispatch child agents, or use secrets.'
)
VERSION = re.compile(r'\Acodex(?:-cli)? [0-9A-Za-z.+-]+\Z')


def summarize_result(
    result: subprocess.CompletedProcess[str],
    *,
    version: str,
) -> dict[str, object]:
    """Exclude the host's raw responses, prompts, IDs and stderr."""
    safe_version = version.strip() if VERSION.fullmatch(version.strip()) else 'unverified'
    data: dict[str, object] = {
        'probe': 'disposable-read-only-codex-exec',
        'codex_version': safe_version,
        'sandbox_requested': 'read-only',
        'host_denial_verified': False,
        'child_model_verified': False,
        'secret_transcripts_retained': False,
    }
    if len(result.stdout) > MAX_OUTPUT_BYTES:
        data['status'] = 'unverified: output size exceeded safe processing limit'
        return data
    metrics = summarize(io.StringIO(result.stdout))
    data['status'] = (
        'read_only_smoke_completed'
        if result.returncode == 0 and metrics['events'].get('turn_completed', 0) > 0
        else 'read_only_smoke_unverified'
    )
    data['events'] = metrics['events']
    data['usage'] = metrics['usage']
    return data


def _invoke_codex(
    codex: str, git: str, timeout: int
) -> tuple[str, subprocess.CompletedProcess[str]] | None:
    version = subprocess.run(  # noqa: S603
        [codex, '--version'],
        text=True,
        capture_output=True,
        check=False,
        timeout=MIN_TIMEOUT,
    )
    with TemporaryDirectory(prefix='mm-codex-readonly-') as temporary:
        worktree = Path(temporary)
        (worktree / 'README.md').write_text(
            '# Read-only acceptance fixture\nThis is a disposable repository.\n',
            encoding='utf-8',
        )
        initialized = subprocess.run(  # noqa: S603
            [git, 'init', '--quiet'],
            cwd=worktree,
            text=True,
            capture_output=True,
            check=False,
            timeout=MIN_TIMEOUT,
        )
        if initialized.returncode:
            return None
        execution = subprocess.run(  # noqa: S603
            [codex, 'exec', '--json', '--sandbox', 'read-only', PROMPT],
            cwd=worktree,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    return version.stdout, execution


def run_probe(timeout: int) -> dict[str, object]:
    codex = shutil.which('codex')
    git = shutil.which('git')
    if not codex or not git:
        return {'status': 'blocked: codex or git unavailable', 'host_denial_verified': False}
    try:
        outcome = _invoke_codex(codex, git, timeout)
    except PROBE_ERRORS:
        return {'status': 'unverified: process unavailable or timed out'}
    if outcome is None:
        return {'status': 'blocked: temporary Git initialization failed'}
    version, execution = outcome
    return summarize_result(execution, version=version)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Run live Codex CLI probe')
    parser.add_argument('--timeout', type=int, default=90)
    args = parser.parse_args()
    if not args.live:
        parser.error('Explicitly pass --live to invoke Codex in a disposable repository')
    if not MIN_TIMEOUT <= args.timeout <= MAX_TIMEOUT:
        parser.error('Timeout must be between 15 and 300 seconds')
    report = run_probe(args.timeout)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get('status') == 'read_only_smoke_completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
