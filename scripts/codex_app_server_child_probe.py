"""Bounded, opt-in App Server child observation; no transcript retention.

By default this program makes no Codex calls. --live explicitly starts one
ephemeral, read-only parent turn in a disposable /tmp Git repository. It does
not establish authorization, sandbox enforcement, or provider billing proof.
"""

import argparse
import hashlib
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path

from codex_app_server_dispatch_summary import DispatchObserver

MAX_LINE = 1_000_000
MAX_TIMEOUT = 120
PROMPT = (
    'Use native spawn_agent once with mm-triage-code-scout to inspect the '
    'first heading of README.md. Do not edit files, run shell commands, '
    'read other files, use the network, or spawn additional agents. '
    'If dispatch is unavailable, say so and stop. No retries.'
)


def snapshot(root: Path) -> tuple[tuple[str, str, str], ...]:
    """Fingerprint disposable fixture paths without returning contents."""
    result: list[tuple[str, str, str]] = []
    for item in root.rglob('*'):
        relative = item.relative_to(root)
        if relative.parts[0] == '.git':
            continue
        if item.is_symlink():
            kind = 'link'
            raw = os.fsencode(item.readlink())
        elif item.is_file():
            kind = 'file'
            raw = item.read_bytes()
        elif item.is_dir():
            kind, raw = 'directory', b''
        else:
            kind, raw = 'other', b''
        result.append((relative.as_posix(), kind, hashlib.sha256(raw).hexdigest()))
    return tuple(sorted(result))


def request(identity: int, method: str, params: dict) -> bytes:
    return (json.dumps({'id': identity, 'method': method, 'params': params}) + '\n').encode()


def read_event(
    pipe: subprocess.Popen[bytes], selector: selectors.BaseSelector,
    pending: bytearray, deadline: float,
) -> dict | None:
    while time.monotonic() < deadline:
        if b'\n' in pending:
            raw, _, tail = pending.partition(b'\n')
            pending[:] = tail
            if len(raw) > MAX_LINE:
                raise RuntimeError('oversized event')
            try:
                event = json.loads(raw)
            except ValueError:
                raise RuntimeError('invalid JSON') from None
            if not isinstance(event, dict):
                raise RuntimeError('invalid event')
            return event
        if not selector.select(max(0.0, deadline - time.monotonic())):
            return None
        if pipe.stdout is None:
            return None
        chunk = os.read(pipe.stdout.fileno(), 4096)
        if not chunk:
            return None
        pending.extend(chunk)
        if len(pending) > MAX_LINE:
            raise RuntimeError('oversized event')
    return None


def _stop(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def run(repo: Path, timeout: int, *, codex: str = 'codex') -> dict[str, object]:
    before = snapshot(repo)
    observer = DispatchObserver()
    proc = subprocess.Popen(
        [codex, 'app-server', '--stdio'], cwd=repo,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    status = 'unverified'
    parent: str | None = None
    turn: str | None = None
    completion: tuple[str, str] | None = None
    phase = 'initialize'
    deadline = time.monotonic() + timeout
    pending = bytearray()
    selector = selectors.DefaultSelector()
    try:
        if proc.stdout is None or proc.stdin is None:
            raise RuntimeError('missing stdio')
        selector.register(proc.stdout, selectors.EVENT_READ)
        proc.stdin.write(request(1, 'initialize', {
            'clientInfo': {'name': 'mm_child_probe', 'title': 'Bounded Child Probe', 'version': '0.2'},
        }))
        proc.stdin.flush()
        while time.monotonic() < deadline:
            event = read_event(proc, selector, pending, deadline)
            if event is None:
                break
            method = event.get('method')
            params = event.get('params')
            if isinstance(method, str) and isinstance(params, dict):
                # Some app-server API versions namespace item notifications by turn.
                normalized = method.removeprefix('turn/') if method.startswith('turn/item/') else method
                observer.consume({'method': normalized, 'params': params})
                if method == 'turn/completed':
                    finished = params.get('turn')
                    if isinstance(finished, dict):
                        candidate = params.get('threadId'), finished.get('id')
                        if all(isinstance(value, str) for value in candidate):
                            completion = candidate
                if completion == (parent, turn) and phase == 'running':
                    status = 'parent_completed'
                    break
                continue
            rid = event.get('id')
            if rid == 1 and phase == 'initialize':
                if not isinstance(event.get('result'), dict):
                    status = 'initialize_rejected'
                    break
                proc.stdin.write(b'{"method":"initialized","params":{}}\n')
                proc.stdin.write(request(2, 'thread/start', {
                    'cwd': str(repo), 'ephemeral': True,
                    'sandbox': 'read-only', 'approvalPolicy': 'never',
                }))
                proc.stdin.flush()
                phase = 'thread_start'
            elif rid == 2 and phase == 'thread_start':
                response = event.get('result')
                thread = response.get('thread') if isinstance(response, dict) else None
                parent = thread.get('id') if isinstance(thread, dict) else None
                if not isinstance(parent, str) or not parent:
                    status = 'thread_rejected'
                    break
                proc.stdin.write(request(3, 'turn/start', {
                    'threadId': parent, 'input': [{'type': 'text', 'text': PROMPT}],
                }))
                proc.stdin.flush()
                phase = 'turn_start'
            elif rid == 3 and phase == 'turn_start':
                response = event.get('result')
                value = response.get('turn') if isinstance(response, dict) else None
                turn = value.get('id') if isinstance(value, dict) else None
                if not isinstance(turn, str) or not turn:
                    status = 'turn_rejected'
                    break
                phase = 'running'
                if completion == (parent, turn):
                    status = 'parent_completed'
                    break
        if status == 'unverified':
            status = 'timeout_or_stream_ended'
    finally:
        selector.close()
        _stop(proc)
        if proc.stdin is not None:
            proc.stdin.close()
        if proc.stdout is not None:
            proc.stdout.close()
    report = observer.report()
    report.update({
        'probe_status': status,
        'fixture_unchanged_verified': before == snapshot(repo),
        'live_host_emission_verified': (
            status == 'parent_completed'
            and report['observed_children'] > 0
        ),
        'quota_savings': 'not_measured',
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--authorized-task', action='store_true')
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not args.live or not args.authorized_task:
        print(json.dumps({'status': 'blocked: explicit live and task assertion required'}))
        return 2
    if (
        not repo.is_relative_to(Path('/tmp')) or repo == Path('/tmp')
        or not (repo / '.git').is_dir() or not (repo / 'README.md').is_file()
        or not 10 <= args.timeout <= MAX_TIMEOUT
    ):
        print(json.dumps({'status': 'blocked: invalid disposable fixture or timeout'}))
        return 2
    try:
        report = run(repo, args.timeout)
    except (OSError, RuntimeError, ValueError):
        print(json.dumps({'status': 'unverified: host or protocol error'}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if (
        report['probe_status'] == 'parent_completed'
        and report['fixture_unchanged_verified']
        and report['observed_children'] > 0
    ) else 2


if __name__ == '__main__':
    sys.exit(main())
