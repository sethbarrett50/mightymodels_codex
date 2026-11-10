"""Opt-in one-shot App Server child telemetry in disposable /tmp repositories.

This program never verifies MightyModels task admission. Its flag is an
assertion only, not a security boundary. No host calls without --live.
"""

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import signal
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from codex_app_server_dispatch_summary import DispatchObserver

MAX_LINE = 1_000_000
MAX_TIMEOUT = 120
MIN_TIMEOUT = 10
THREAD_REQUEST_ID = 2
TURN_REQUEST_ID = 3
PROMPT = (
    'Use native spawn_agent once with mm-triage-code-scout to inspect the first '
    'heading of README.md. No edits, shell commands, other files, network, '
    'other agents, or retries. If dispatch is unavailable, report it and stop.'
)


def snapshot(root: Path) -> tuple[tuple[str, str, str], ...]:
    """Fingerprint a disposable fixture without exposing its names or contents."""
    records: list[tuple[str, str, str]] = []
    for item in root.rglob('*'):
        relative = item.relative_to(root)
        if relative.parts[0] == '.git':
            continue
        if item.is_symlink():
            kind, digest = 'link', hashlib.sha256(os.fsencode(item.readlink())).hexdigest()
        elif item.is_dir():
            kind, digest = 'directory', ''
        elif item.is_file():
            kind = 'file'
            with item.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        else:
            kind, digest = 'other', ''
        records.append((relative.as_posix(), kind, digest))
    return tuple(sorted(records))


async def send(proc: asyncio.subprocess.Process, message: dict) -> None:
    if proc.stdin is None:
        msg = 'stdin missing'
        raise RuntimeError(msg)
    proc.stdin.write((json.dumps(message) + '\n').encode())
    await proc.stdin.drain()


async def receive(proc: asyncio.subprocess.Process, deadline: float) -> dict | None:
    if proc.stdout is None:
        msg = 'stdout missing'
        raise RuntimeError(msg)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    try:
        raw = await asyncio.wait_for(proc.stdout.readline(), remaining)
    except TimeoutError, asyncio.LimitOverrunError:
        return None
    if not raw:
        return None
    if len(raw) > MAX_LINE:
        msg = 'oversized event'
        raise RuntimeError(msg)
    try:
        event = json.loads(raw)
    except ValueError:
        msg = 'invalid JSON'
        raise RuntimeError(msg) from None
    if not isinstance(event, dict):
        msg = 'invalid JSON-RPC event'
        raise TypeError(msg)
    return event


@dataclass
class Session:
    repo: Path
    observer: DispatchObserver = field(default_factory=DispatchObserver)
    phase: str = 'initialize'
    status: str = 'unverified'
    parent: str | None = None
    turn: str | None = None
    completion: tuple[str, str] | None = None

    def notice(self, method: str, params: dict) -> None:
        normalized = method.removeprefix('turn/') if method.startswith('turn/item/') else method
        self.observer.consume({'method': normalized, 'params': params})
        if method != 'turn/completed':
            return
        finished = params.get('turn')
        if not isinstance(finished, dict):
            return
        parent, turn = params.get('threadId'), finished.get('id')
        if isinstance(parent, str) and isinstance(turn, str):
            self.completion = (parent, turn)

    async def initialize(self, proc: asyncio.subprocess.Process, event: dict) -> None:
        if not isinstance(event.get('result'), dict):
            self.status = 'initialize_rejected'
            return
        await send(proc, {'method': 'initialized', 'params': {}})
        await send(
            proc,
            {
                'id': 2,
                'method': 'thread/start',
                'params': {
                    'cwd': str(self.repo),
                    'ephemeral': True,
                    'sandbox': 'read-only',
                    'approvalPolicy': 'never',
                },
            },
        )
        self.phase = 'thread_start'

    async def start_thread(self, proc: asyncio.subprocess.Process, event: dict) -> None:
        result = event.get('result')
        thread = result.get('thread') if isinstance(result, dict) else None
        identity = thread.get('id') if isinstance(thread, dict) else None
        if not isinstance(identity, str) or not identity:
            self.status = 'thread_rejected'
            return
        self.parent = identity
        await send(
            proc,
            {
                'id': 3,
                'method': 'turn/start',
                'params': {'threadId': identity, 'input': [{'type': 'text', 'text': PROMPT}]},
            },
        )
        self.phase = 'turn_start'

    def start_turn(self, event: dict) -> None:
        result = event.get('result')
        turn = result.get('turn') if isinstance(result, dict) else None
        identity = turn.get('id') if isinstance(turn, dict) else None
        if not isinstance(identity, str) or not identity:
            self.status = 'turn_rejected'
            return
        self.turn = identity
        self.phase = 'running'

    async def handle(self, proc: asyncio.subprocess.Process, event: dict) -> None:
        method, params = event.get('method'), event.get('params')
        if isinstance(method, str) and isinstance(params, dict):
            self.notice(method, params)
            return
        if event.get('id') == 1 and self.phase == 'initialize':
            await self.initialize(proc, event)
        elif event.get('id') == THREAD_REQUEST_ID and self.phase == 'thread_start':
            await self.start_thread(proc, event)
        elif event.get('id') == TURN_REQUEST_ID and self.phase == 'turn_start':
            self.start_turn(event)

    def done(self) -> bool:
        if self.status != 'unverified':
            return True
        if self.phase == 'running' and self.completion == (self.parent, self.turn):
            self.status = 'parent_completed'
            return True
        return False


async def stop(proc: asyncio.subprocess.Process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGTERM)
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(proc.wait(), 3)
    if proc.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
    if proc.stdin is not None:
        proc.stdin.close()
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            await proc.stdin.wait_closed()


async def observe(session: Session, duration: int, codex: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        codex,
        'app-server',
        '--stdio',
        cwd=session.repo,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + duration
        await send(
            proc,
            {
                'id': 1,
                'method': 'initialize',
                'params': {
                    'clientInfo': {
                        'name': 'mm_child_probe',
                        'title': 'Bounded Child Probe',
                        'version': '0.3',
                    }
                },
            },
        )
        while not session.done():
            event = await receive(proc, deadline)
            if event is None:
                break
            await session.handle(proc, event)
        if session.status == 'unverified':
            session.status = 'timeout_or_stream_ended'
    finally:
        await stop(proc)


def run(repo: Path, timeout: int, *, codex: str = 'codex') -> dict[str, object]:
    before = snapshot(repo)
    session = Session(repo=repo)
    asyncio.run(observe(session, timeout, codex))
    report = session.observer.report()
    report.update({
        'probe_status': session.status,
        'fixture_unchanged_verified': before == snapshot(repo),
        'live_host_emission_verified': (
            session.status == 'parent_completed' and report['observed_children'] > 0
        ),
        'quota_savings': 'not_measured',
    })
    return report


def valid_fixture(repo: Path, duration: int) -> bool:
    temp_root = Path(tempfile.gettempdir()).resolve()
    if repo == temp_root or not repo.is_relative_to(temp_root):
        return False
    if not (repo / '.git').is_dir() or not (repo / 'README.md').is_file():
        return False
    return MIN_TIMEOUT <= duration <= MAX_TIMEOUT


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--authorized-task', action='store_true')
    args = parser.parse_args()
    if not args.live or not args.authorized_task:
        print(json.dumps({'status': 'blocked: explicit live and task assertion required'}))
        return 2
    repo = args.repo.resolve()
    if not valid_fixture(repo, args.timeout):
        print(json.dumps({'status': 'blocked: invalid disposable fixture or timeout'}))
        return 2
    try:
        report = run(repo, args.timeout)
    except OSError, RuntimeError, TypeError, ValueError:
        print(json.dumps({'status': 'unverified: host or protocol error'}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return (
        0
        if (
            report['probe_status'] == 'parent_completed'
            and report['fixture_unchanged_verified']
            and report['observed_children'] > 0
        )
        else 2
    )


if __name__ == '__main__':
    raise SystemExit(main())
