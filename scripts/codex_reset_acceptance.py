"""One-shot, quota-aware live Codex acceptance gate.

--preflight validates static installation without invoking Codex inference.
--live runs exactly one disposable read-only smoke, only after preflight passes.
Neither phase proves hook delivery, child model identity, or host-side admission.
No raw Codex output, prompts, paths, or credentials are retained.
"""

import argparse
import json
from pathlib import Path

from codex_doctor import diagnose
from codex_live_acceptance import MAX_TIMEOUT, MIN_TIMEOUT, run_probe

LIVE_SUCCESS = 'read_only_smoke_completed'
LIMIT_CATEGORY = 'possible_usage_or_rate_limit'


def report(*, home: Path, root: Path, live: bool, timeout: int) -> tuple[dict, int]:
    """Require a healthy static install before consuming any live Codex quota."""
    findings, healthy = diagnose(home, root, root)
    state: dict[str, object] = {
        'probe': 'codex-reset-acceptance-gate',
        'mode': 'live' if live else 'preflight',
        'doctor': {'healthy': healthy, 'findings': findings},
        'host_hook_delivery_verified': False,
        'agent_model_identity_verified': False,
        'host_admission_verified': False,
        'full_lifecycle_verified': False,
    }
    if not healthy:
        state['status'] = 'blocked: static installation checks failed'
        state['next_action'] = 'repair installation and rerun --preflight'
        return state, 1
    if not live:
        state['status'] = 'preflight_passed_live_unverified'
        state['next_action'] = 'when quota resets, run --live once'
        return state, 0
    smoke = run_probe(timeout)
    state['smoke'] = smoke
    if smoke.get('status') == LIVE_SUCCESS:
        state['status'] = 'read_only_smoke_passed_host_acceptance_incomplete'
        state['next_action'] = (
            'inspect docs/CODEX-LIVE-ACCEPTANCE.md for manual host checks; '
            'do not infer hooks or model routing from this smoke'
        )
        return state, 0
    state['status'] = 'live_smoke_unverified_stop'
    state['next_action'] = (
        'stop: quota or rate limit still plausible; do not retry automatically'
        if smoke.get('failure_category') == LIMIT_CATEGORY
        else 'stop: review sanitized smoke status before any further live attempt'
    )
    return state, 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument('--preflight', action='store_true')
    phase.add_argument('--live', action='store_true')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not MIN_TIMEOUT <= args.timeout <= MAX_TIMEOUT:
        parser.error(f'Timeout must be between {MIN_TIMEOUT} and {MAX_TIMEOUT} seconds')
    result, code = report(
        home=args.home.expanduser().resolve(),
        root=args.root.expanduser().resolve(),
        live=args.live,
        timeout=args.timeout,
    )
    print(json.dumps(result, sort_keys=True, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
