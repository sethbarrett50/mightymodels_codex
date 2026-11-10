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
    'mm-review-fact-checker', 'mm-review-merge-vader', 'mm-review-qualitylens',
    'mm-review-uncle-bob', 'mm-triage-code-scout', 'mm-triage-terry-toolchain',
    'mm-triage-web-scout', 'mm-workers-architect', 'mm-workers-engineer',
    'mm-workers-gitty-up', 'mm-workers-intern',
})


def _counts(value: object) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None
    values = [value.get(key) for key in USAGE]
    if any(type(n) is not int or n < 0 for n in values):
        return None
    a, cached, output, reasoning = values
    if cached > a or reasoning > output:
        return None
    return a, cached, output, reasoning


def summarize(lines: TextIO) -> dict[str, object]:
    """Ingest only nominated notification fields; never output IDs or raw payloads."""
    threads: dict[str, tuple[str, str | None]] = {}
    usage: dict[str, tuple[int, int, int, int]] = {}
    invalid_usage: set[str] = set()
    counters: Counter[str] = Counter()
    for line in lines:
        if len(line.encode('utf-8', errors='replace')) > MAX_LINE_BYTES:
            counters['invalid_events'] += 1
            continue
        try:
            event = json.loads(line)
        except ValueError:
            counters['invalid_events'] += 1
            continue
        if not isinstance(event, dict):
            counters['invalid_events'] += 1
            continue
        method = event.get('method')
        params = event.get('params')
        if not isinstance(params, dict):
            continue
        if method == 'thread/started':
            thread = params.get('thread')
            if not isinstance(thread, dict):
                continue
            thread_id, parent = thread.get('id'), thread.get('parentThreadId')
            if not isinstance(thread_id, str) or not thread_id:
                counters['invalid_events'] += 1
                continue
            if parent is not None and (not isinstance(parent, str) or not parent):
                counters['invalid_events'] += 1
                continue
            if thread_id not in threads and len(threads) >= MAX_THREADS:
                counters['capacity_exceeded'] += 1
                continue
            role = thread.get('agentRole')
            role = role if isinstance(role, str) and role in KNOWN_ROLES else 'other'
            threads[thread_id] = (role, parent)
        elif method == 'thread/tokenUsage/updated':
            thread_id = params.get('threadId')
            if not isinstance(thread_id, str) or not thread_id:
                counters['invalid_events'] += 1
                continue
            if (
                thread_id not in usage
                and thread_id not in invalid_usage
                and len(usage) + len(invalid_usage) >= MAX_THREADS
            ):
                counters['capacity_exceeded'] += 1
                continue
            token_usage = params.get('tokenUsage')
            total = token_usage.get('total') if isinstance(token_usage, dict) else None
            measured = _counts(total)
            if measured is None:
                invalid_usage.add(thread_id)
                usage.pop(thread_id, None)
                counters['invalid_usage_notifications'] += 1
            elif thread_id not in invalid_usage:
                previous = usage.get(thread_id)
                if previous is not None and any(a < b for a, b in zip(measured, previous)):
                    invalid_usage.add(thread_id)
                    usage.pop(thread_id, None)
                    counters['regressing_usage_notifications'] += 1
                else:
                    usage[thread_id] = measured

    children = [(tid, role) for tid, (role, parent) in threads.items() if parent is not None]
    measured_children = [(tid, role) for tid, role in children if tid in usage]
    totals = [sum(usage[tid][index] for tid, _ in measured_children) for index in range(4)]
    counts_by_role = Counter(role for _, role in children)
    return {
        'source': 'codex-app-server-notifications',
        'scope': 'observed_child_threads_only; not complete provider accounting',
        'observed_threads': len(threads),
        'observed_children': len(children),
        'children_with_valid_usage': len(measured_children),
        'children_without_valid_usage': len(children) - len(measured_children),
        'observed_child_roles': dict(sorted(counts_by_role.items())),
        'observed_child_token_totals': (
            dict(zip(USAGE, totals, strict=True)) if measured_children else None
        ),
        'errors': dict(sorted(counters.items())),
        'effective_child_models_verified': False,
        'effective_child_effort_verified': False,
        'complete_child_usage_verified': False,
        'quota_savings': 'not_measured',
        'privacy': 'Aggregates only; no IDs, paths, transcripts, model labels, or prompts',
    }


def main() -> int:
    print(json.dumps(summarize(sys.stdin), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
