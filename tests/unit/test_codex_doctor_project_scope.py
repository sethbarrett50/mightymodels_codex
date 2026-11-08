"""Check the installer doctor handles optional project MCP scope safely."""

import sys
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    DOCTOR = run_path(str(ROOT / 'scripts/codex_doctor.py'))
check_project_overlap = DOCTOR['check_project_overlap']


@pytest.mark.unit
def test_project_config_without_mcp_servers_is_expected(tmp_path: Path) -> None:
    checkout = tmp_path / 'mightymodels'
    project = checkout / '.codex'
    project.mkdir(parents=True)
    (project / 'config.toml').write_text(
        '[agents]\nenabled = true\nmax_concurrent_threads_per_session = 6\n'
    )
    assert check_project_overlap(checkout, checkout) is None


@pytest.mark.unit
def test_project_mcp_duplicates_still_warn(tmp_path: Path) -> None:
    checkout = tmp_path / 'mightymodels'
    project = checkout / '.codex'
    project.mkdir(parents=True)
    (project / 'config.toml').write_text('[mcp_servers.mighty_mcp]\ncommand = "sh"\n')
    assert 'declares project-scoped mighty_mcp' in check_project_overlap(checkout, checkout)


@pytest.mark.unit
def test_project_mcp_wrong_type_still_warns(tmp_path: Path) -> None:
    checkout = tmp_path / 'mightymodels'
    project = checkout / '.codex'
    project.mkdir(parents=True)
    (project / 'config.toml').write_text('mcp_servers = "bad shape"\n')
    assert check_project_overlap(checkout, checkout) == (
        '[WARN] Project-scoped MCP config has unexpected shape'
    )


@pytest.mark.unit
def test_project_mcp_non_mighty_server_does_not_warn(tmp_path: Path) -> None:
    checkout = tmp_path / 'mightymodels'
    project = checkout / '.codex'
    project.mkdir(parents=True)
    (project / 'config.toml').write_text('[mcp_servers.other]\ncommand = "safe"\n')
    assert check_project_overlap(checkout, checkout) is None
