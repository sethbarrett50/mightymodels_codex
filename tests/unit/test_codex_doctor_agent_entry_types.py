"""Doctor reports malformed role entries instead of raising on a TOML value."""

import sys
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    DOCTOR = run_path(str(ROOT / 'scripts/codex_doctor.py'))
check_agents = DOCTOR['check_agents']


@pytest.mark.unit
@pytest.mark.parametrize('malformed', ['invalid', [], False, 123, None])
def test_doctor_rejects_malformed_individual_role_entry(
    tmp_path: Path, malformed: object
) -> None:
    source = ROOT / '.codex/agents/mm-workers-engineer.toml'
    installed = tmp_path / '.codex/agents/mm-workers-engineer.toml'
    installed.parent.mkdir(parents=True)
    installed.symlink_to(source)
    status = check_agents({'agents': {'mm-workers-engineer': malformed}}, tmp_path, ROOT)
    assert status.startswith('[FAIL]')
    assert '0/11' in status


@pytest.mark.unit
def test_doctor_recognizes_valid_role_without_exposing_config_values(tmp_path: Path) -> None:
    source = ROOT / '.codex/agents/mm-workers-engineer.toml'
    installed = tmp_path / '.codex/agents/mm-workers-engineer.toml'
    installed.parent.mkdir(parents=True)
    installed.symlink_to(source)
    status = check_agents(
        {'agents': {'mm-workers-engineer': {'config_file': str(source)}}},
        tmp_path,
        ROOT,
    )
    assert '1/11' in status
    assert str(source) not in status
