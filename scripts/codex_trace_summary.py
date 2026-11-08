"""Summarize Codex exec JSONL into nonsecret counts without retaining transcripts.

Usage: codex exec --json --sandbox read-only "..." |
       python3 scripts/codex_trace_summary.py
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import TextIO

USAGE_FIELDS = (
    'input_tokens',
    'cached_input_tokens',
    'output_tokens',
    'reasoning_output_tokens',
)
ITEM_TYPES = {
    'command_execution': 'command_executions',
    'mcp_tool_call': 'mcp_calls',
    'file_change': 'file_changes',
    'web_search': 'web_searches',
    'plan_update': 'plan_updates',
}
MAX_LINE_LENGTH = 1_000_000


def _positive_count(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _parse_event(line: str) -> dict | None:
    if len(line.encode('utf-8', errors='replace')) > MAX_LINE_LENGTH:
        return None
    try:
        parsed = json.loads(line)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _count_usage(usage: object, counts: Counter[str], tokens: Counter[str]) -> None:
    if not isinstance(usage, dict):
        counts['turns_without_usage'] += 1
        return
    for name in USAGE_FIELDS:
        tokens[name] += _positive_count(usage.get(name))


def _count_event(event: dict, counts: Counter[str], tokens: Counter[str]) -> None:
    kind = event.get('type')
    if kind in ('turn.started', 'turn.completed', 'turn.failed'):
        counts[kind.replace('.', '_')] += 1
    elif kind == 'item.started':
        counts['items_started'] += 1
        item = event.get('item')
        item_type = item.get('type') if isinstance(item, dict) else None
        mapped = (
            ITEM_TYPES.get(item_type, 'other_items')
            if isinstance(item_type, str)
            else 'other_items'
        )
        counts[mapped] += 1
    elif kind == 'item.completed':
        item = event.get('item')
        if isinstance(item, dict):
            item_type = item.get('type')
            if item_type == 'command_execution':
                counts['commands_completed'] += 1
                exit_code = item.get('exit_code')
                if isinstance(exit_code, int) and not isinstance(exit_code, bool) and exit_code != 0:
                    counts['commands_exited_nonzero'] += 1
            elif item_type == 'mcp_tool_call':
                counts['mcp_calls_completed'] += 1
                if item.get('status') == 'failed':
                    counts['mcp_calls_failed'] += 1
    elif kind == 'error':
        counts['errors'] += 1
    elif kind not in ('thread.started', 'item.updated'):
        counts['unknown_events'] += 1
    if kind == 'turn.completed':
        _count_usage(event.get('usage'), counts, tokens)


def summarize(lines: TextIO) -> dict[str, object]:
    """Consume only event kinds, operation classes and numeric usage fields."""
    counts: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    for line in lines:
        event = _parse_event(line)
        if event is None:
            counts['malformed_events'] += 1
        else:
            _count_event(event, counts, tokens)
    return {
        'source': 'codex-exec-jsonl',
        'effective_model_identity': 'unverified',
        'quota_savings': 'not_measured',
        'events': dict(sorted(counts.items())),
        'usage': {name: tokens[name] for name in USAGE_FIELDS},
        'privacy': 'Only event classes and numeric counters; raw prompts never retained',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', default='-', help='JSONL path or - for stdin')
    args = parser.parse_args()
    if args.input == '-':
        report = summarize(sys.stdin)
    else:
        with Path(args.input).open(encoding='utf-8') as stream:
            report = summarize(stream)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
