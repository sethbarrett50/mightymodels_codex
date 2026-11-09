"""Compare two sanitized Codex JSONL summaries without claiming measured quota savings.

Inputs must be JSON reports produced by scripts/codex_trace_summary.py.
Only validated numeric counters leave this process. Paths, input metadata,
prompts and models are never echoed.
"""

import argparse
import json
from pathlib import Path

MAX_INPUT_BYTES = 65536


def _safe_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _load_summary(path: Path) -> dict[str, int] | None:
    if path.stat().st_size > MAX_INPUT_BYTES:
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get('source') != 'codex-exec-jsonl':
        return None
    usage, events = data.get('usage'), data.get('events')
    if not isinstance(usage, dict) or not isinstance(events, dict):
        return None
    input_tokens = _safe_count(usage.get('input_tokens'))
    cached_tokens = _safe_count(usage.get('cached_input_tokens'))
    output_tokens = _safe_count(usage.get('output_tokens'))
    reasoning_tokens = _safe_count(usage.get('reasoning_output_tokens'))
    turns = _safe_count(events.get('turn_completed'))
    if (
        input_tokens is None
        or cached_tokens is None
        or output_tokens is None
        or reasoning_tokens is None
        or turns is None
        or turns == 0
    ):
        return None
    if cached_tokens > input_tokens:
        return None
    for name in ('turn_failed', 'errors', 'malformed_events'):
        error_count = _safe_count(events.get(name, 0))
        if error_count is None or error_count > 0:
            return None
    return {'turns': turns, 'input_tokens': input_tokens, 'output_tokens': output_tokens}


def compare(baseline: dict[str, int], candidate: dict[str, int]) -> dict[str, object]:
    """Report observational token counts, not provider quota or cost savings."""
    def per_turn(value: dict[str, int]) -> float:
        return (value['input_tokens'] + value['output_tokens']) / value['turns']

    before, after = per_turn(baseline), per_turn(candidate)
    relative = round((after / before - 1) * 100, 2) if before else None
    return {
        'measurement': 'observed_streamed_tokens_per_completed_turn',
        'baseline': {'turns': baseline['turns'], 'tokens_per_turn': round(before, 2)},
        'candidate': {'turns': candidate['turns'], 'tokens_per_turn': round(after, 2)},
        'relative_change_percent': relative,
        'matched_workload_verified': False,
        'effective_child_models_verified': False,
        'quota_savings_verified': False,
        'limitations': (
            'Only streamed JSONL turn tokens; no child-model identity, provider quota, '
            'hidden work or matched workload is established by this comparison.'
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        baseline, candidate = _load_summary(args.baseline), _load_summary(args.candidate)
    except OSError:
        baseline = candidate = None
    if baseline is None or candidate is None:
        print(json.dumps({'status': 'unverified: invalid or failed sanitized summary input'}))
        return 2
    print(json.dumps(compare(baseline, candidate), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
