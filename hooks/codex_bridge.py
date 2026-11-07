"""Translate Codex PreToolUse agent-dispatch events into MightyModels admission hooks.

Codex hook failures are not intrinsically fail-closed. This adapter returns an explicit
denial when a MightyModels dispatch cannot be validated. Hook execution can still be
disabled or bypassed by the host; this is a guardrail, not a security sandbox.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROLES = {
    f'mm-{kind}-{name}': f'mightymodels:{kind}:{name}'
    for kind, names in {
        'review': ('fact-checker', 'merge-vader', 'qualitylens', 'uncle-bob'),
        'triage': ('code-scout', 'terry-toolchain', 'web-scout', 'wingman'),
        'workers': ('architect', 'engineer', 'gitty-up', 'intern'),
    }.items()
    for name in names
}
HOOK_TIMEOUT = 8


def denial(reason: str) -> dict:
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }


def role(value: object) -> object:
    return ROLES.get(value, value) if isinstance(value, str) else value


def translate(event: object) -> tuple[dict | None, str | None]:  # noqa: C901, PLR0911
    """Return translated legacy hook input, or a denial reason.

    A non-MightyModels dispatch returns (None, None). Missing role information is
    denied to avoid silently bypassing admission on a changed Codex wire format.
    """
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PreToolUse':
        return None, 'Unexpected or malformed Codex PreToolUse event'
    if event.get('tool_name') not in ('spawn_agent', 'Agent'):
        return None, 'Unexpected hook tool name for agent dispatch'
    raw = event.get('tool_input')
    if not isinstance(raw, dict):
        return None, 'Codex agent dispatch has no argument object'
    target = next(
        (raw.get(k) for k in ('agent_type', 'subagent_type', 'profile') if raw.get(k)),
        None,
    )
    parent = role(event.get('agent_type'))
    is_mighty_caller = isinstance(parent, str) and parent.startswith('mightymodels:')
    if not isinstance(target, str):
        if is_mighty_caller:
            return None, 'MightyModels worker cannot delegate without an explicit approved role'
        return None, None  # Native Codex default-agent dispatch
    target = role(target)
    if not target.startswith('mightymodels:'):
        if is_mighty_caller:
            return None, f'MightyModels worker may not delegate to {target}'
        return None, None
    payload = {
        'hook_event_name': 'PreToolUse',
        'session_id': event.get('session_id'),
        'cwd': event.get('cwd'),
        'tool_name': 'Agent',
        'tool_input': {'subagent_type': target},
    }
    if isinstance(parent, str):
        payload['agent_type'] = parent
    return payload, None


def run_admission(event: object, *, project_root: Path, environ: dict) -> dict | None:
    translated, error = translate(event)
    if error:
        return denial(error)
    if translated is None:
        return None

    env = dict(environ)
    home = Path(env.get('HOME') or str(Path.home()))
    data_dir = (
        env.get('CLAUDE_PLUGIN_DATA')
        or env.get('PLUGIN_DATA')
        or env.get('MIGHTYMODELS_DATA_DIR')
        or str(Path(env.get('XDG_DATA_HOME') or (home / '.local/share')) / 'mightymodels')
    )
    env['CLAUDE_PLUGIN_DATA'] = data_dir
    env['UV_PROJECT'] = str(project_root)
    env['UV_PROJECT_ENVIRONMENT'] = str(project_root / '.venv')

    try:
        # State initialization is not an authorization decision.
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(  # noqa: S603
            [
                shutil.which('uv') or '/nonexistent/uv',
                'run',
                '--locked',
                '--no-dev',
                '--package',
                'mightymodels-hooks',
                'mightymodels-hooks',
                'dispatch-hook',
            ],
            input=json.dumps(translated),
            cwd=str(project_root),
            env=env,
            text=True,
            capture_output=True,
            timeout=HOOK_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return denial(f'MightyModels admission unavailable; dispatch denied: {exc}')
    if result.returncode:
        return denial(
                'MightyModels admission check failed; dispatch denied '
                f'(exit {result.returncode}; {result.stderr[-500:]})'
            )
    if not result.stdout.strip():
        return None
    try:
        decision = json.loads(result.stdout)
    except ValueError as exc:
        return denial(f'MightyModels admission returned malformed JSON: {exc}')
    if not isinstance(decision, dict):
        return denial('Admission handler did not return a JSON object')
    return decision


def run_lifecycle(event: object, *, project_root: Path, environ: dict) -> dict | None:
    """Forward compatible nonblocking events to the existing MightyModels hooks."""
    if not isinstance(event, dict):
        return None
    name = event.get('hook_event_name')
    command = {'PreCompact': 'pre-compact', 'SubagentStop': 'subagent-record'}.get(name)
    if command is None:
        return None
    payload = dict(event)
    if name == 'SubagentStop':
        payload['agent_type'] = role(payload.get('agent_type'))
    env = dict(environ)
    home = Path(env.get('HOME') or str(Path.home()))
    data_dir = (
        env.get('CLAUDE_PLUGIN_DATA')
        or env.get('PLUGIN_DATA')
        or env.get('MIGHTYMODELS_DATA_DIR')
        or str(Path(env.get('XDG_DATA_HOME') or (home / '.local/share')) / 'mightymodels')
    )
    env['CLAUDE_PLUGIN_DATA'] = data_dir
    env['UV_PROJECT'] = str(project_root)
    env['UV_PROJECT_ENVIRONMENT'] = str(project_root / '.venv')
    warning = None
    try:
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [
                'uv',
                'run',
                '--locked',
                '--no-dev',
                '--package',
                'mightymodels-hooks',
                'mightymodels-hooks',
                command,
            ],
            input=json.dumps(payload),
            cwd=str(project_root),
            env=env,
            text=True,
            capture_output=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        warning = f'MightyModels {command} unavailable: {exc}'
    else:
        if result.returncode:
            warning = f'MightyModels {command} failed ({result.returncode}): {result.stderr[-300:]}'
    if name == 'SubagentStop':
        return {'continue': True, **({'systemMessage': warning} if warning else {})}
    return {'systemMessage': warning} if warning else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError) as exc:
        print(json.dumps(denial(f'Invalid Codex hook event: {exc}')))
        return 0
    root = Path(__file__).resolve().parent.parent
    if isinstance(event, dict) and event.get('hook_event_name') in ('PreCompact', 'SubagentStop'):
        result = run_lifecycle(event, project_root=root, environ=dict(os.environ))
    else:
        result = run_admission(event, project_root=root, environ=dict(os.environ))
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
