"""Opt-in lifecycle receipts prove host callback delivery without state leakage."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
probe = run_path(str(ROOT / 'hooks/codex_bridge.py'))['lifecycle_probe_receipt']


@pytest.mark.unit
def test_unenabled_lifecycle_probe_writes_nothing(tmp_path: Path) -> None:
    probe({'hook_event_name': 'SessionStart', 'source': 'resume'}, {'HOME': str(tmp_path)})
    assert not (tmp_path / '.local/state/mightymodels/codex-lifecycle-probe.log').exists()


@pytest.mark.unit
def test_lifecycle_receipts_are_sanitized_and_line_delimited(tmp_path: Path) -> None:
    state = tmp_path / '.local/state/mightymodels'
    state.mkdir(parents=True)
    (state / 'codex-lifecycle-probe.enabled').touch(mode=0o600)
    env = {'HOME': str(tmp_path)}
    probe(
        {
            'hook_event_name': 'SessionStart',
            'source': 'resume',
            'session_id': 'SECRET_SESSION',
            'cwd': 'SECRET_PATH',
        },
        env,
    )
    probe({'hook_event_name': 'PreCompact', 'session_id': 'SECRET_SESSION'}, env)
    log = state / 'codex-lifecycle-probe.log'
    assert log.read_text() == 'event=SessionStart source=resume\nevent=PreCompact source=unknown\n'
    assert log.stat().st_mode & 0o777 == 0o600


@pytest.mark.unit
@pytest.mark.parametrize('mode', [0o644, 0o666])
def test_unsafe_marker_is_ignored(tmp_path: Path, mode: int) -> None:
    state = tmp_path / '.local/state/mightymodels'
    state.mkdir(parents=True)
    marker = state / 'codex-lifecycle-probe.enabled'
    marker.touch()
    marker.chmod(mode)
    probe({'hook_event_name': 'SessionStart'}, {'HOME': str(tmp_path)})
    assert not (state / 'codex-lifecycle-probe.log').exists()


@pytest.mark.unit
def test_lifecycle_unknown_source_is_not_logged(tmp_path: Path) -> None:
    state = tmp_path / '.local/state/mightymodels'
    state.mkdir(parents=True)
    (state / 'codex-lifecycle-probe.enabled').touch(mode=0o600)
    probe(
        {'hook_event_name': 'SessionStart', 'source': 'SECRET_SOURCE'},
        {'HOME': str(tmp_path)},
    )
    assert (state / 'codex-lifecycle-probe.log').read_text() == (
        'event=SessionStart source=unknown\n'
    )
