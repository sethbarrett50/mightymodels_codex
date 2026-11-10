"""Fake stdio App Server tests; no Codex inference or child process execution."""

import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
PROBE = SimpleNamespace(**runpy.run_path(str(ROOT / 'scripts/codex_app_server_child_probe.py')))

FAKE = """#!PYTHON
import json
import sys

CASE = 'SCENARIO'

def send(value):
    print(json.dumps(value), flush=True)

def emit():
    send({'method': 'thread/started', 'params': {
        'thread': {'id': 'PRIVATE_PARENT', 'parentThreadId': None}
    }})
    if CASE != 'no_child':
        send({'method': 'turn/item/started', 'params': {'item': {
            'id': 'PRIVATE_CALL', 'type': 'collabAgentToolCall',
            'tool': 'spawnAgent', 'status': 'inProgress'
        }}})
        send({'method': 'turn/item/completed', 'params': {'item': {
            'id': 'PRIVATE_CALL', 'type': 'collabAgentToolCall',
            'tool': 'spawnAgent', 'status': 'completed',
            'receiverThreadIds': ['PRIVATE_CHILD']
        }}})
        send({'method': 'thread/started', 'params': {'thread': {
            'id': 'PRIVATE_CHILD', 'parentThreadId': 'PRIVATE_PARENT',
            'agentRole': 'mm-triage-code-scout'
        }}})
        send({'method': 'turn/item/completed', 'params': {'item': {
            'type': 'subAgentActivity', 'agentThreadId': 'PRIVATE_CHILD',
            'kind': 'started', 'model': 'PRIVATE_MODEL', 'reasoningEffort': 'high'
        }}})
    send({'method': 'turn/completed', 'params': {
        'threadId': 'PRIVATE_PARENT', 'turn': {'id': 'PRIVATE_TURN'}
    }})

for line in sys.stdin:
    message = json.loads(line)
    if message.get('method') == 'initialize':
        send({'id': 1, 'result': {}})
    elif message.get('method') == 'thread/start':
        send({'id': 2, 'result': {'thread': {'id': 'PRIVATE_PARENT'}}})
    elif message.get('method') == 'turn/start':
        if CASE == 'early_completion':
            emit()
        send({'id': 3, 'result': {'turn': {'id': 'PRIVATE_TURN'}}})
        if CASE != 'early_completion':
            emit()
"""


def fixture(tmp_path: Path, scenario: str) -> tuple[Path, str]:
    repo = tmp_path / 'fixture'
    repo.mkdir()
    (repo / '.git').mkdir()
    (repo / 'README.md').write_text('# Synthetic fixture\n')
    fake = tmp_path / 'fake-codex'
    fake.write_text(FAKE.replace('PYTHON', sys.executable).replace('SCENARIO', scenario))
    fake.chmod(0o755)
    return repo, str(fake)


@pytest.mark.unit
@pytest.mark.parametrize('scenario', ['child', 'early_completion'])
def test_child_telemetry_without_private_payloads(tmp_path: Path, scenario: str) -> None:
    repo, fake = fixture(tmp_path, scenario)
    report = PROBE.run(repo, 10, codex=fake)
    assert report['probe_status'] == 'parent_completed'
    assert report['dispatch_classification'] == 'child_observed'
    assert report['observed_spawn_calls'] == 1
    assert report['observed_subagent_creations'] == 1
    assert report['creations_with_resolved_model'] == 1
    assert report['fixture_unchanged_verified'] is True
    assert report['live_host_emission_verified'] is True
    assert 'PRIVATE_' not in json.dumps(report)


@pytest.mark.unit
def test_parent_completion_without_child_is_not_success(tmp_path: Path) -> None:
    repo, fake = fixture(tmp_path, 'no_child')
    report = PROBE.run(repo, 10, codex=fake)
    assert report['probe_status'] == 'parent_completed'
    assert report['observed_children'] == 0
    assert report['live_host_emission_verified'] is False
    assert report['dispatch_classification'] == 'spawn_attempt_not_observed'


@pytest.mark.unit
def test_live_flag_is_mandatory_and_silent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    repo, _fake = fixture(tmp_path, 'child')
    monkeypatch.setattr(sys, 'argv', ['probe', '--repo', str(repo)])
    assert PROBE.main() == 2
    assert 'blocked' in capsys.readouterr().out
