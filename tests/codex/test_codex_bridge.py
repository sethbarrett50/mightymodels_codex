"""Regression tests for the Codex-to-MightyModels dispatch gate."""
import json
import subprocess
from unittest.mock import patch

import pytest

from hooks import codex_bridge as module


def event(target="mm-workers-engineer", caller=None):
    result = {
        "hook_event_name": "PreToolUse",
        "tool_name": "spawn_agent",
        "tool_input": {"agent_type": target, "message": "test"},
        "cwd": "/tmp/repo",
        "session_id": "test-session",
    }
    if caller is not None:
        result["agent_type"] = caller
    return result


@pytest.mark.unit
def test_worker_and_caller_name_translation():
    payload, error = module.translate(
        event("mm-triage-code-scout", "mm-workers-engineer")
    )
    assert error is None
    assert payload["tool_input"]["subagent_type"] == "mightymodels:triage:code-scout"
    assert payload["agent_type"] == "mightymodels:workers:engineer"
    assert payload["tool_name"] == "Agent"


@pytest.mark.unit
def test_plain_codex_role_not_policed():
    payload, error = module.translate(event("explorer"))
    assert payload is None
    assert error is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    [
        {},
        [],
        {"hook_event_name": "PreToolUse", "tool_name": "spawn_agent"},
        {"hook_event_name": "PostToolUse", "tool_name": "spawn_agent"},
    ],
)
def test_malformed_events_fail_closed(value):
    payload, error = module.translate(value)
    assert payload is None
    assert error


@pytest.mark.unit
def test_legacy_denial_preserved(tmp_path):
    denial = module.denial("ticket not started")
    fake = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=json.dumps(denial), stderr=""
    )
    with patch.object(module.subprocess, "run", return_value=fake) as runner:
        got = module.run_admission(
            event(), project_root=tmp_path, environ={"HOME": str(tmp_path)}
        )
    assert got == denial
    payload = json.loads(runner.call_args.kwargs["input"])
    assert payload["tool_input"]["subagent_type"] == "mightymodels:workers:engineer"
    assert runner.call_args.kwargs["timeout"] == 8


@pytest.mark.unit
def test_hook_failure_denies(tmp_path):
    fake = subprocess.CompletedProcess(
        args=[], returncode=2, stdout="", stderr="bad state"
    )
    with patch.object(module.subprocess, "run", return_value=fake):
        got = module.run_admission(
            event(), project_root=tmp_path, environ={"HOME": str(tmp_path)}
        )
    assert got["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.unit
def test_hook_timeout_denies(tmp_path):
    with patch.object(
        module.subprocess,
        "run",
        side_effect=subprocess.TimeoutExpired("uv", 8),
    ):
        got = module.run_admission(
            event(), project_root=tmp_path, environ={"HOME": str(tmp_path)}
        )
    assert got["hookSpecificOutput"]["permissionDecision"] == "deny"

@pytest.mark.unit
def test_scout_stop_uses_legacy_hook(tmp_path):
    recorded = {}
    def fake_run(*args, **kwargs):
        recorded.update(kwargs)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch.object(module.subprocess, "run", side_effect=fake_run):
        outcome = module.run_lifecycle(
            {
                "hook_event_name": "SubagentStop",
                "agent_type": "mm-triage-code-scout",
                "agent_id": "scout-id",
                "last_assistant_message": "<report>OK</report>",
                "cwd": str(tmp_path),
            },
            project_root=tmp_path,
            environ={"HOME": str(tmp_path)},
        )
    payload = json.loads(recorded["input"])
    assert payload["agent_type"] == "mightymodels:triage:code-scout"
    assert recorded["input"]
    assert outcome == {"continue": True}


@pytest.mark.unit
def test_compaction_uses_legacy_snapshot_hook(tmp_path):
    with patch.object(module.subprocess, "run") as runner:
        runner.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        result = module.run_lifecycle(
            {"hook_event_name": "PreCompact", "cwd": str(tmp_path)},
            project_root=tmp_path,
            environ={"HOME": str(tmp_path)},
        )
    assert result is None
    assert "pre-compact" in runner.call_args.args[0]
