"""Regression tests for the Codex-to-MightyModels dispatch gate."""

import json
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

module = SimpleNamespace(
    **runpy.run_path(str(Path(__file__).resolve().parents[2] / 'hooks' / 'codex_bridge.py'))
)


def event(target: str = 'mm-workers-engineer', caller: str | None = None) -> dict[str, Any]:
    result = {
        'hook_event_name': 'PreToolUse',
        'tool_name': 'spawn_agent',
        'tool_input': {'agent_type': target, 'message': 'test'},
        'cwd': str(Path.cwd()),
        'session_id': 'test-session',
    }
    if caller is not None:
        result['agent_type'] = caller
    return result


@pytest.mark.unit
def test_worker_and_caller_name_translation() -> None:
    payload, error = module.translate(event('mm-triage-code-scout', 'mm-workers-engineer'))
    assert error is None
    assert payload['tool_input']['subagent_type'] == 'mightymodels:triage:code-scout'
    assert payload['agent_type'] == 'mightymodels:workers:engineer'
    assert payload['tool_name'] == 'Agent'


@pytest.mark.unit
def test_plain_codex_role_not_policed() -> None:
    payload, error = module.translate(event('explorer'))
    assert payload is None
    assert error is None


@pytest.mark.unit
@pytest.mark.parametrize(
    'value',
    [
        {},
        [],
        {'hook_event_name': 'PreToolUse', 'tool_name': 'spawn_agent', 'tool_input': None},
        {'hook_event_name': 'PostToolUse', 'tool_name': 'spawn_agent'},
    ],
)
def test_malformed_events_fail_closed(value: object) -> None:
    payload, error = module.translate(value)
    assert payload is None
    assert error


@pytest.mark.unit
def test_legacy_denial_preserved(tmp_path: Path) -> None:
    denial = module.denial('ticket not started')
    fake = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(denial), stderr='')
    with patch.object(module.subprocess, 'run', return_value=fake) as runner:
        got = module.run_admission(event(), project_root=tmp_path, environ={'HOME': str(tmp_path)})
    assert got == denial
    payload = json.loads(runner.call_args.kwargs['input'])
    assert payload['tool_input']['subagent_type'] == 'mightymodels:workers:engineer'
    assert runner.call_args.kwargs['timeout'] == 8


@pytest.mark.unit
def test_hook_failure_denies(tmp_path: Path) -> None:
    fake = subprocess.CompletedProcess(args=[], returncode=2, stdout='', stderr='bad state')
    with patch.object(module.subprocess, 'run', return_value=fake):
        got = module.run_admission(event(), project_root=tmp_path, environ={'HOME': str(tmp_path)})
    assert got['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.unit
def test_hook_timeout_denies(tmp_path: Path) -> None:
    with patch.object(
        module.subprocess,
        'run',
        side_effect=subprocess.TimeoutExpired('uv', 8),
    ):
        got = module.run_admission(event(), project_root=tmp_path, environ={'HOME': str(tmp_path)})
    assert got['hookSpecificOutput']['permissionDecision'] == 'deny'


@pytest.mark.unit
def test_scout_stop_uses_legacy_hook(tmp_path: Path) -> None:
    recorded = {}

    def fake_run(*_args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded.update(kwargs)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout='', stderr='')

    with patch.object(module.subprocess, 'run', side_effect=fake_run) as runner:
        outcome = module.run_lifecycle(
            {
                'hook_event_name': 'SubagentStop',
                'agent_type': 'mm-triage-code-scout',
                'agent_id': 'scout-id',
                'last_assistant_message': '<report>OK</report>',
                'cwd': str(tmp_path),
            },
            project_root=tmp_path,
            environ={'HOME': str(tmp_path)},
        )
    payload = json.loads(recorded['input'])
    assert payload['agent_type'] == 'mightymodels:triage:code-scout'
    assert recorded['input']
    assert 'subagent-record' in runner.call_args.args[0]
    assert outcome == {'continue': True}


@pytest.mark.unit
def test_compaction_uses_legacy_snapshot_hook(tmp_path: Path) -> None:
    with patch.object(module.subprocess, 'run') as runner:
        runner.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='', stderr=''
        )
        result = module.run_lifecycle(
            {'hook_event_name': 'PreCompact', 'cwd': str(tmp_path)},
            project_root=tmp_path,
            environ={'HOME': str(tmp_path)},
        )
    assert result is None
    assert 'pre-compact' in runner.call_args.args[0]


@pytest.mark.unit
def test_native_default_agent_allowed() -> None:
    base = event()
    base['tool_input'] = {'message': 'Summarize the repository'}
    payload, error = module.translate(base)
    assert payload is None
    assert error is None


@pytest.mark.unit
def test_mighty_worker_cannot_delegate_to_native_role() -> None:
    payload, error = module.translate(event('explorer', 'mm-workers-engineer'))
    assert payload is None
    assert 'may not delegate' in error


@pytest.mark.unit
def test_mighty_worker_requires_explicit_role() -> None:
    base = event(caller='mm-workers-engineer')
    base['tool_input'] = {'message': 'Do anything'}
    payload, error = module.translate(base)
    assert payload is None
    assert 'explicit approved role' in error


@pytest.mark.unit
def test_fable_wingman_dispatch_is_denied() -> None:
    payload, error = module.translate(event('mm-triage-wingman'))
    assert payload is None
    assert error is not None
    assert 'disabled' in error


@pytest.mark.unit
def test_unknown_mightymodels_role_fails_closed() -> None:
    payload, error = module.translate(event('mightymodels:workers:invented'))
    assert payload is None
    assert 'Unknown MightyModels agent' in error


@pytest.mark.unit
def test_opt_in_probe_records_dispatch_without_prompt_or_path(tmp_path: Path) -> None:
    probe_event = event('mm-workers-engineer')
    probe_event['tool_input']['message'] = 'TOP_SECRET_DO_NOT_LOG'
    module.audit_probe(
        probe_event,
        {'HOME': str(tmp_path), 'MIGHTYMODELS_CODEX_DISPATCH_PROBE': '1'},
    )
    log = tmp_path / '.local/state/mightymodels/codex-dispatch-probe.log'
    assert log.is_file()
    assert 'pre_tool_use_spawn_agent_seen' in log.read_text()
    assert 'TOP_SECRET_DO_NOT_LOG' not in log.read_text()
    assert log.stat().st_mode & 0o777 == 0o600


@pytest.mark.unit
def test_probe_disabled_by_default(tmp_path: Path) -> None:
    module.audit_probe(event(), {'HOME': str(tmp_path)})
    assert not (tmp_path / '.local/state/mightymodels').exists()
