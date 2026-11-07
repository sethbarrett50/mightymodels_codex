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


@pytest.mark.unit
def test_mcp_post_tool_result_records_session_pointer(tmp_path: Path) -> None:
    post_event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'mcp__mighty_mcp__ticket_show',
        'tool_input': {'slug': 'example'},
        'session_id': 'codex-session-1',
        'cwd': str(tmp_path),
    }
    with patch.object(module.subprocess, 'run') as runner:
        runner.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='', stderr=''
        )
        result = module.run_lifecycle(
            post_event, project_root=tmp_path, environ={'HOME': str(tmp_path)}
        )
    assert result is None
    assert 'session-pointer' in runner.call_args.args[0]
    sent = json.loads(runner.call_args.kwargs['input'])
    assert sent['tool_name'] == 'mcp__mighty_mcp__ticket_show'
    assert sent['session_id'] == 'codex-session-1'


@pytest.mark.unit
def test_non_mighty_mcp_post_tool_result_is_ignored(tmp_path: Path) -> None:
    with patch.object(module.subprocess, 'run') as runner:
        outcome = module.run_lifecycle(
            {'hook_event_name': 'PostToolUse', 'tool_name': 'Bash'},
            project_root=tmp_path,
            environ={'HOME': str(tmp_path)},
        )
    assert outcome is None
    runner.assert_not_called()


@pytest.mark.unit
def test_session_start_runs_prune_only(tmp_path: Path) -> None:
    with patch.object(module.subprocess, 'run') as runner:
        runner.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='', stderr=''
        )
        outcome = module.run_lifecycle(
            {'hook_event_name': 'SessionStart', 'cwd': str(tmp_path)},
            project_root=tmp_path,
            environ={'HOME': str(tmp_path)},
        )
    assert outcome is None
    assert 'session-prune' in runner.call_args.args[0]


@pytest.mark.unit
def test_explicit_plan_answers_translate_to_legacy_decisions() -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'plan',
        'session_id': 'session-001',
        'tool_input': {
            'questions': [
                {'id': 'design', 'question': 'Which design?'},
                {'id': 'secrets', 'question': 'Password?', 'is_secret': True},
            ]
        },
        'tool_response': {
            'answers': {
                'design': {'answers': ['Option A', 'detail B']},
                'secrets': {'answers': ['TOP_SECRET_DO_NOT_STORE']},
            }
        },
    }
    payload = module.translate_plan_answers(event)
    assert payload is not None
    assert payload['tool_name'] == 'AskUserQuestion'
    assert payload['tool_response'] == {'answers': {'Which design?': 'Option A\ndetail B'}}
    assert 'TOP_SECRET_DO_NOT_STORE' not in json.dumps(payload)


@pytest.mark.unit
@pytest.mark.parametrize('mode', ['default', 'unknown', None])
def test_default_or_unknown_user_input_never_persists_approval(mode: str | None) -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': mode,
        'session_id': 'session-001',
        'tool_input': {'questions': [{'id': 'q', 'question': 'May I proceed?'}]},
        'tool_response': {'answers': {'q': {'answers': ['Yes']}}},
    }
    assert module.translate_plan_answers(event) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    'response',
    [
        {'answers': {}},
        {'answers': {'q': {'answers': []}}},
        {'answers': {'q': {'answers': [None]}}},
        {'answers': {'q': {'answers': ['yes']}}, 'afkTimeoutMs': 1000},
        {'answers': {'q': {'answer': 'yes'}}},
        'not-json',
    ],
)
def test_empty_timeout_or_unrecognized_answers_are_not_recorded(response: object) -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'plan',
        'session_id': 'session-001',
        'tool_input': {'questions': [{'id': 'q', 'question': 'Continue?'}]},
        'tool_response': response,
    }
    assert module.translate_plan_answers(event) is None


@pytest.mark.unit
def test_plan_decision_forwards_to_legacy_recorder(tmp_path: Path) -> None:
    plan_event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'plan',
        'session_id': 'session-001',
        'cwd': str(tmp_path),
        'tool_input': {'questions': [{'id': 'q', 'question': 'Continue?'}]},
        'tool_response': {'answers': {'q': {'answers': ['Proceed']}}},
    }
    with patch.object(module.subprocess, 'run') as runner:
        runner.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='', stderr=''
        )
        outcome = module.run_lifecycle(
            plan_event, project_root=tmp_path, environ={'HOME': str(tmp_path)}
        )
    assert outcome is None
    assert 'ask-recorder' in runner.call_args.args[0]
    payload = json.loads(runner.call_args.kwargs['input'])
    assert payload['tool_response'] == {'answers': {'Continue?': 'Proceed'}}


@pytest.mark.unit
def test_unconfirmed_default_answer_emits_warning_without_state_write(tmp_path: Path) -> None:
    event = {
        'hook_event_name': 'PostToolUse',
        'tool_name': 'request_user_input',
        'permission_mode': 'default',
        'session_id': 'session-001',
        'tool_input': {'questions': [{'id': 'q', 'question': 'Continue?'}]},
        'tool_response': {'answers': {'q': {'answers': ['Yes']}}},
    }
    with patch.object(module.subprocess, 'run') as runner:
        outcome = module.run_lifecycle(
            event, project_root=tmp_path, environ={'HOME': str(tmp_path)}
        )
    runner.assert_not_called()
    assert 'did not persist' in outcome['systemMessage']
