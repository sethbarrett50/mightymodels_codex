"""Summarize observed App Server child usage without retaining sensitive event content.

Synthetic/offline input only. Accepts JSON-RPC notifications on standard input.
Does not connect to Codex, resume threads, or perform inference.
"""

import json
import sys
from collections import Counter
from typing import TextIO

MAX_LINE_BYTES = 1_000_000
MAX_THREADS = 10_000
USAGE = ('inputTokens', 'cachedInputTokens', 'outputTokens', 'reasoningOutputTokens')
KNOWN_ROLES = frozenset({
    'mm-review-fact-checker',
    'mm-review-merge-vader',
    'mm-review-qualitylens',
    'mm-review-uncle-bob',
    'mm-triage-code-scout',
    'mm-triage-terry-toolchain',
    'mm-triage-web-scout',
    'mm-workers-architect',
    'mm-workers-engineer',
    'mm-workers-gitty-up',
    'mm-workers-intern',
})


def _counts(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None
    values = [value.get(key) for key in USAGE]
    if any(type(n) is not int or n < 0 for n in values):
        return None
    input_tokens, cached, output, reasoning = values
    if cached > input_tokens or reasoning > output:
        return None
    return input_tokens, cached, output, reasoning


def _parse(line: str) -> dict | None:
    if len(line.encode('utf-8', errors='replace')) > MAX_LINE_BYTES:
        return None
    try:
        parsed = json.loads(line)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


class Observer:
    """Keep only bounded, volatile thread IDs needed for in-memory correlation."""

    def __init__(self) -> None:
        self.threads: dict[str, tuple[str, str | None]] = {}
        self.usage: dict[str, tuple[int, int, int, int]] = {}
        self.invalid_usage: set[str] = set()
        self.counters: Counter[str] = Counter()

    def record_thread(self, params: dict) -> None:
        thread = params.get('thread')
        if not isinstance(thread, dict):
            return
        thread_id, parent = thread.get('id'), thread.get('parentThreadId')
        if not isinstance(thread_id, str) or not thread_id:
            self.counters['invalid_events'] += 1
            return
        if parent is not None and (not isinstance(parent, str) or not parent):
            self.counters['invalid_events'] += 1
            return
        if thread_id not in self.threads and len(self.threads) >= MAX_THREADS:
            self.counters['capacity_exceeded'] += 1
            return
        role = thread.get('agentRole')
        role = role if isinstance(role, str) and role in KNOWN_ROLES else 'other'
        self.threads[thread_id] = (role, parent)

    def record_usage(self, params: dict) -> None:
        thread_id = params.get('threadId')
        if not isinstance(thread_id, str) or not thread_id:
            self.counters['invalid_events'] += 1
            return
        if (
            thread_id not in self.usage
            and thread_id not in self.invalid_usage
            and len(self.usage) + len(self.invalid_usage) >= MAX_THREADS
        ):
            self.counters['capacity_exceeded'] += 1
            return
        token_usage = params.get('tokenUsage')
        total = token_usage.get('total') if isinstance(token_usage, dict) else None
        measured = _counts(total)
        if measured is None:
            self.invalid_usage.add(thread_id)
            self.usage.pop(thread_id, None)
            self.counters['invalid_usage_notifications'] += 1
            return
        if thread_id in self.invalid_usage:
            return
        previous = self.usage.get(thread_id)
        if previous is not None and any(
            a < b for a, b in zip(measured, previous, strict=True)
        ):
            self.invalid_usage.add(thread_id)
            self.usage.pop(thread_id, None)
            self.counters['regressing_usage_notifications'] += 1
            return
        self.usage[thread_id] = measured

    def report(self) -> dict[str, object]:
        children = [
            (thread_id, role)
            for thread_id, (role, parent) in self.threads.items()
            if parent is not None
        ]
        measured = [(tid, role) for tid, role in children if tid in self.usage]
        totals = [sum(self.usage[tid][index] for tid, _ in measured) for index in range(4)]
        counts = Counter(role for _, role in children)
        return {
            'source': 'codex-app-server-notifications',
            'scope': 'observed_child_threads_only; not complete provider accounting',
            'observed_threads': len(self.threads),
            'observed_children': len(children),
            'children_with_valid_usage': len(measured),
            'children_without_valid_usage': len(children) - len(measured),
            'observed_child_roles': dict(sorted(counts.items())),
            'observed_child_token_totals': (
                dict(zip(USAGE, totals, strict=True)) if measured else None
            ),
            'errors': dict(sorted(self.counters.items())),
            'effective_child_models_verified': False,
            'effective_child_effort_verified': False,
            'complete_child_usage_verified': False,
            'quota_savings': 'not_measured',
            'privacy': 'Aggregates only; no IDs, paths, transcripts, model labels, or prompts',
        }


def summarize(lines: TextIO) -> dict[str, object]:
    """Consume only nominated notification fields; never output raw payloads."""
    observer = Observer()
    for line in lines:
        event = _parse(line)
        if event is None:
            observer.counters['invalid_events'] += 1
            continue
        params = event.get('params')
        if not isinstance(params, dict):
            continue
        method = event.get('method')
        if method == 'thread/started':
            observer.record_thread(params)
        elif method == 'thread/tokenUsage/updated':
            observer.record_usage(params)
    return observer.report()


def main() -> int:
    print(json.dumps(summarize(sys.stdin), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
