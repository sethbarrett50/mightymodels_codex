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
import time
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
SPAWN_TOOL_NAMES = frozenset((
    'spawn_agent',
    'Agent',
    'collaborationspawn_agent',
    'collaboration.spawn_agent',
))
HOOK_TIMEOUT = 8
MAX_RESUME_CONTEXT = 600
MAX_MCP_RESULT_LENGTH = 8192
QUESTION_PROBE_MARKER_MODE = 0o600
HOOK_ERRORS = (OSError, subprocess.TimeoutExpired, ValueError)
INPUT_ERRORS = (ValueError, UnicodeError)


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


def translate(event: object) -> tuple[dict | None, str | None]:  # noqa: C901, PLR0911, PLR0912
    """Return translated legacy hook input, or a denial reason.

    A non-MightyModels dispatch returns (None, None). Missing role information is
    denied to avoid silently bypassing admission on a changed Codex wire format.
    """
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PreToolUse':
        return None, 'Unexpected or malformed Codex PreToolUse event'
    if event.get('tool_name') not in SPAWN_TOOL_NAMES:
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
    if target.startswith('mightymodels:') and target not in ROLES.values():
        return None, 'Unknown MightyModels agent role'
    if target == 'mightymodels:triage:wingman':
        return None, 'Codex wingman is disabled: Fable tier is not configured'
    if not target.startswith('mightymodels:'):
        if is_mighty_caller:
            return None, 'MightyModels worker may not delegate to a non-MightyModels role'
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


def run_admission(event: object, *, project_root: Path, environ: dict) -> dict | None:  # noqa: PLR0911
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
    except HOOK_ERRORS:
        return denial('MightyModels admission unavailable; dispatch denied')
    if result.returncode:
        return denial(
            f'MightyModels admission check failed; dispatch denied (exit {result.returncode})'
        )
    if not result.stdout.strip():
        return None
    try:
        decision = json.loads(result.stdout)
    except ValueError:
        return denial('MightyModels admission returned malformed JSON')
    if not isinstance(decision, dict):
        return denial('Admission handler did not return a JSON object')
    return decision


def translate_plan_answers(event: dict) -> dict | None:  # noqa: C901, PLR0911, PLR0912, PLR0914, PLR0915
    """Convert only explicit, nonsecret Plan-mode answers for the legacy recorder.

    Default-mode prompts may auto-resolve; never treat those as authorization.
    Unknown or partial Codex response shapes are not persisted.
    """
    if event.get('permission_mode') != 'plan':
        return None
    session_id = event.get('session_id')
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    request = event.get('tool_input')
    response = event.get('tool_response')
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            return None
    if not isinstance(request, dict) or not isinstance(response, dict):
        return None
    questions = request.get('questions')
    returned = response.get('answers')
    if not isinstance(questions, list) or not isinstance(returned, dict):
        return None
    # Even an explicit JSON null marks a host timeout field as present.
    # Match the legacy recorder's fail-closed presence check.
    if 'afkTimeoutMs' in response:
        return None

    answers: dict[str, str] = {}
    question_ids: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            return None
        identifier = question.get('id')
        label = question.get('question')
        if not isinstance(identifier, str) or not identifier or identifier in question_ids:
            return None
        question_ids.add(identifier)
        if question.get('is_secret') is True:
            continue
        if not isinstance(label, str) or not label.strip() or label in answers:
            return None
        selected = returned.get(identifier)
        if not isinstance(selected, dict) or not isinstance(selected.get('answers'), list):
            return None
        texts = selected['answers']
        if not all(isinstance(text, str) for text in texts):
            return None
        actual = [value.strip() for value in texts if value.strip()]
        if not actual:
            return None
        answers[label] = '\n'.join(actual)
    if not answers:
        return None
    # The recorder needs only the session pointer and approved answers.
    # Never pass original tool_input/options or skipped secret responses onward.
    cwd = event.get('cwd')
    if not isinstance(cwd, str) or not cwd.strip():
        return None
    return {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'AskUserQuestion',
        'cwd': cwd,
        'session_id': session_id,
        'tool_response': {'answers': answers},
    }


def failed_mcp_result(response: object) -> bool:
    """Reject explicit failures or uninspectable responses without logging them."""
    if response is None:
        return False  # Older host versions may omit the result entirely.
    if isinstance(response, str):
        if len(response) > MAX_MCP_RESULT_LENGTH:
            return True
        try:
            response = json.loads(response)
        except ValueError:
            return True
    if not isinstance(response, dict):
        return True
    return response.get('isError') is True or response.get('status') in ('error', 'failed')


def translate_pointer_event(event: dict) -> dict | None:
    """Pass only target keys to the session-pointer handler, never tool results."""
    session_id = event.get('session_id')
    cwd = event.get('cwd')
    name = event.get('tool_name')
    supplied = event.get('tool_input')
    if (
        failed_mcp_result(event.get('tool_response'))
        or not isinstance(session_id, str)
        or not session_id.strip()
    ):
        return None
    if not isinstance(cwd, str) or not cwd.strip():
        return None
    if not isinstance(name, str) or not name.startswith('mcp__mighty_mcp__'):
        return None
    if not isinstance(supplied, dict):
        return None
    target = {
        key: value
        for key in ('slug', 'ticket', 'investigation_id')
        if isinstance((value := supplied.get(key)), str) and value.strip()
    }
    if not target:
        return None
    return {
        'hook_event_name': 'PostToolUse',
        'tool_name': name,
        'session_id': session_id,
        'cwd': cwd,
        'tool_input': target,
    }


def lifecycle_command(event: dict) -> str | None:
    """Return a supported lifecycle command, filtering unrelated MCP results."""
    name = event.get('hook_event_name')
    if name == 'PostToolUse':
        tool = event.get('tool_name')
        if tool == 'request_user_input':
            return 'ask-recorder'
        return (
            'session-pointer'
            if isinstance(tool, str) and tool.startswith('mcp__mighty_mcp__')
            else None
        )
    if name == 'SessionStart':
        return 'session-resume' if event.get('source') in ('resume', 'compact') else 'session-prune'
    return {
        'PreCompact': 'pre-compact',
        'SubagentStop': 'subagent-record',
    }.get(name)


def resume_hook_output(command: str, result: subprocess.CompletedProcess[str]) -> dict | None:
    """Expose only the bounded successful resume hint as SessionStart context."""
    if command != 'session-resume' or result.returncode:
        return None
    hint = result.stdout.strip()
    if not hint or len(hint) > MAX_RESUME_CONTEXT:
        return None
    return {
        'hookSpecificOutput': {
            'hookEventName': 'SessionStart',
            'additionalContext': hint,
        }
    }


def run_lifecycle(event: object, *, project_root: Path, environ: dict) -> dict | None:  # noqa: C901, PLR0912, PLR0915
    """Forward compatible nonblocking events to the existing MightyModels hooks."""
    if not isinstance(event, dict):
        return None
    name = event.get('hook_event_name')
    command = lifecycle_command(event)
    if command is None:
        return None
    payload = dict(event)
    if command == 'ask-recorder':
        translated = translate_plan_answers(event)
        if translated is None:
            return {
                'systemMessage': (
                    'MightyModels did not persist this Codex question response; '
                    'required decisions need explicit user confirmation and MCP state.'
                )
            }
        payload = translated
    elif command == 'session-pointer':
        translated = translate_pointer_event(event)
        if translated is None:
            return None
        payload = translated
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
    result = None
    try:
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
    except HOOK_ERRORS:
        warning = f'MightyModels {command} unavailable'
    else:
        if result.returncode:
            warning = f'MightyModels {command} failed (exit {result.returncode})'
        # Legacy persistence handlers can report unreadable state on stderr
        # despite exit 0. Never echo private handler diagnostics.
        elif (
            command
            in (
                'session-pointer',
                'ask-recorder',
                'subagent-record',
                'pre-compact',
                'session-prune',
                'session-resume',
            )
            and result.stderr.strip()
        ):
            warning = f'MightyModels {command} reported a persistence warning'
    if name == 'SubagentStop':
        return {'continue': True, **({'systemMessage': warning} if warning else {})}
    restored = (
        resume_hook_output(command, result) if warning is None and result is not None else None
    )
    return restored or ({'systemMessage': warning} if warning else None)


def question_probe_enabled(home: Path, environ: dict[str, str]) -> bool:
    """Require an explicit shell flag or a private, locally owned regular file."""
    if environ.get('MIGHTYMODELS_CODEX_QUESTION_PROBE') == '1':
        return True
    marker = home / '.local/state/mightymodels/codex-question-probe.enabled'
    try:
        status = marker.stat(follow_symlinks=False)
    except OSError:
        return False
    return (
        marker.is_file()
        and not marker.is_symlink()
        and (status.st_mode & 0o777) == QUESTION_PROBE_MARKER_MODE
        and status.st_uid == os.getuid()
    )


def question_probe_receipt(event: object, environ: dict[str, str]) -> None:
    """Opt-in receipt of hook delivery and response *shape*, never answer contents."""
    home = Path(environ.get('HOME') or str(Path.home()))
    if not question_probe_enabled(home, environ):
        return
    state_dir = home / '.local/state/mightymodels'
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PostToolUse':
        return
    if event.get('tool_name') != 'request_user_input':
        return
    receipt = state_dir / 'codex-question-probe.log'
    response = event.get('tool_response')
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except ValueError:
            response = None
    answers = response.get('answers') if isinstance(response, dict) else None
    mode = event.get('permission_mode')
    allowed_modes = ('default', 'plan', 'acceptEdits', 'dontAsk', 'bypassPermissions')
    mode = mode if mode in allowed_modes else 'unknown'
    request = event.get('tool_input')
    question_present = isinstance(request, dict) and isinstance(request.get('questions'), list)
    fields = (
        'event=PostToolUse',
        'tool=request_user_input',
        f'mode={mode}',
        f'input_questions={question_present}',
        f'response_object={isinstance(response, dict)}',
        f'answers_object={isinstance(answers, dict)}',
        f'timeout_field={isinstance(response, dict) and "afkTimeoutMs" in response}',
    )
    receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if receipt.is_symlink():
        return
    with receipt.open('a', encoding='utf-8') as stream:
        stream.write(' '.join(fields) + '\n')
    receipt.chmod(0o600)


def lifecycle_probe_receipt(event: object, environ: dict[str, str]) -> None:
    """Record bounded host lifecycle delivery metadata, never payload contents."""
    if not isinstance(event, dict):
        return
    name = event.get('hook_event_name')
    if name not in ('SessionStart', 'PreCompact'):
        return
    home = Path(environ.get('HOME') or str(Path.home()))
    state_dir = home / '.local/state/mightymodels'
    marker = state_dir / 'codex-lifecycle-probe.enabled'
    try:
        status = marker.stat(follow_symlinks=False)
    except OSError:
        return
    if not marker.is_file() or marker.is_symlink():
        return
    if (status.st_mode & 0o777) != QUESTION_PROBE_MARKER_MODE or status.st_uid != os.getuid():
        return
    source = event.get('source')
    source_name = source if source in ('startup', 'resume', 'compact') else 'unknown'
    receipt = state_dir / 'codex-lifecycle-probe.log'
    if receipt.is_symlink():
        return
    receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with receipt.open('a', encoding='utf-8') as stream:
        stream.write(f'event={name} source={source_name}\n')
    receipt.chmod(0o600)


def lifecycle_resume_probe_outcome(event: object, result: object, environ: dict[str, str]) -> None:
    """Opt-in receipt of a returned pointer hint, never the target or its contents."""
    if not isinstance(event, dict) or event.get('hook_event_name') != 'SessionStart':
        return
    if event.get('source') not in ('resume', 'compact'):
        return
    home = Path(environ.get('HOME') or str(Path.home()))
    state_dir = home / '.local/state/mightymodels'
    marker = state_dir / 'codex-lifecycle-probe.enabled'
    try:
        status = marker.stat(follow_symlinks=False)
    except OSError:
        return
    if not marker.is_file() or marker.is_symlink():
        return
    if (status.st_mode & 0o777) != QUESTION_PROBE_MARKER_MODE or status.st_uid != os.getuid():
        return
    output = result.get('hookSpecificOutput') if isinstance(result, dict) else None
    hint = output.get('additionalContext') if isinstance(output, dict) else None
    if isinstance(hint, str) and hint.strip():
        state = 'present'
    elif isinstance(result, dict) and result.get('systemMessage'):
        state = 'warning'
    else:
        state = 'absent'
    receipt = state_dir / 'codex-lifecycle-probe.log'
    if receipt.is_symlink():
        return
    receipt.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with receipt.open('a', encoding='utf-8') as stream:
        stream.write(f'event=SessionResumePointer hint={state}\n')
    receipt.chmod(0o600)


def audit_probe(event: object, environ: dict[str, str]) -> None:
    """Record that the host reached this hook, without persisting tool arguments."""
    if environ.get('MIGHTYMODELS_CODEX_DISPATCH_PROBE') != '1':
        return
    if not isinstance(event, dict):
        return
    if event.get('hook_event_name') != 'PreToolUse':
        return
    if event.get('tool_name') not in SPAWN_TOOL_NAMES:
        return
    home = Path(environ.get('HOME') or str(Path.home()))
    log = home / '.local/state/mightymodels/codex-dispatch-probe.log'
    log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as stream:
        stream.write(f'pre_tool_use_spawn_agent_seen {time.time_ns()}\n')
    log.chmod(0o600)


def audit_probe_decision(event: object, environ: dict[str, str], result: object) -> None:
    """Log the adapter's sanitized decision, not proof of a Codex-host block."""
    if environ.get('MIGHTYMODELS_CODEX_DISPATCH_PROBE') != '1':
        return
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PreToolUse':
        return
    if event.get('tool_name') not in SPAWN_TOOL_NAMES:
        return
    hook_output = result.get('hookSpecificOutput') if isinstance(result, dict) else None
    denied = isinstance(hook_output, dict) and hook_output.get('permissionDecision') == 'deny'
    status = 'adapter_denied' if denied else 'adapter_no_denial'
    home = Path(environ.get('HOME') or str(Path.home()))
    log = home / '.local/state/mightymodels/codex-dispatch-probe.log'
    log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with log.open('a', encoding='utf-8') as stream:
        stream.write(f'{status} {time.time_ns()}\n')
    log.chmod(0o600)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except INPUT_ERRORS:
        print(json.dumps(denial('Invalid Codex hook event')))
        return 0
    root = Path(__file__).resolve().parent.parent
    audit_probe(event, dict(os.environ))
    question_probe_receipt(event, dict(os.environ))
    lifecycle_probe_receipt(event, dict(os.environ))
    if isinstance(event, dict) and event.get('hook_event_name') in (
        'PreCompact',
        'SubagentStop',
        'SessionStart',
        'PostToolUse',
    ):
        result = run_lifecycle(event, project_root=root, environ=dict(os.environ))
    else:
        result = run_admission(event, project_root=root, environ=dict(os.environ))
    lifecycle_resume_probe_outcome(event, result, dict(os.environ))
    audit_probe_decision(event, dict(os.environ), result)
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
