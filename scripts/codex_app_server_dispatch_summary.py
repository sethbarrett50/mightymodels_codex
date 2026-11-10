"""Offline App Server spawn-observation classifier; no host calls or raw output.

Only synthetic streams have been validated. Missing notifications are unknown,
not proof that the parent did not invoke native spawn_agent.
"""

import json
import sys
from typing import TextIO

from codex_app_server_usage_summary import MAX_THREADS, Observer, _parse

STATUSES = frozenset({'inProgress', 'completed', 'failed', 'interrupted'})


class DispatchObserver:
    """Correlate a bounded set of observed spawn items without exposing IDs."""

    def __init__(self) -> None:
        self.usage = Observer()
        self.calls: dict[str, tuple[str, bool]] = {}
        self.ignored = 0

    def record_item(self, method: str, params: dict) -> None:
        item = params.get('item')
        if not isinstance(item, dict):
            return
        if item.get('type') != 'collabAgentToolCall' or item.get('tool') != 'spawnAgent':
            return
        identity = item.get('id')
        if not isinstance(identity, str) or not identity:
            self.ignored += 1
            return
        if identity not in self.calls and len(self.calls) >= MAX_THREADS:
            self.ignored += 1
            return
        status = item.get('status')
        if not isinstance(status, str) or status not in STATUSES:
            status = 'unknown'
        receivers = item.get('receiverThreadIds')
        has_receiver = (
            isinstance(receivers, list)
            and bool(receivers)
            and all(isinstance(value, str) and value for value in receivers)
        )
        if method == 'item/completed':
            self.calls[identity] = (status, has_receiver)
        elif identity not in self.calls:
            self.calls[identity] = ('inProgress', has_receiver)

    def consume(self, event: dict) -> None:
        method = event.get('method')
        params = event.get('params')
        if not isinstance(params, dict):
            return
        if method == 'thread/started':
            self.usage.record_thread(params)
        elif method == 'thread/tokenUsage/updated':
            self.usage.record_usage(params)
        elif method in ('item/started', 'item/completed'):
            self.record_item(method, params)

    def report(self) -> dict[str, object]:
        report = self.usage.report()
        observed_children = report['observed_children']
        statuses = [status for status, _ in self.calls.values()]
        if observed_children:
            classification = 'child_observed'
        elif not self.calls:
            classification = 'spawn_attempt_not_observed'
        elif any(status == 'failed' for status in statuses):
            classification = 'spawn_failed_or_denied'
        elif any(status == 'completed' and receiver for status, receiver in self.calls.values()):
            classification = 'spawn_returned_child_id_but_thread_unobserved'
        else:
            classification = 'spawn_outcome_unknown'
        report.update({
            'dispatch_classification': classification,
            'observed_spawn_calls': len(self.calls),
            'observed_spawn_statuses': {
                status: statuses.count(status) for status in sorted(set(statuses))
            },
            'ignored_spawn_items': self.ignored,
            'dispatch_observability': (
                'partial: missing App Server events cannot prove no dispatch attempt; '
                'failed does not prove a security denial'
            ),
        })
        return report


def summarize(lines: TextIO) -> dict[str, object]:
    observer = DispatchObserver()
    for line in lines:
        event = _parse(line)
        if event is None:
            observer.usage.counters['invalid_events'] += 1
        else:
            observer.consume(event)
    return observer.report()


def main() -> int:
    print(json.dumps(summarize(sys.stdin), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
