"""Test read-only doctor diagnostics for other Codex project scopes."""

import sys
from pathlib import Path
from runpy import run_path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
with patch.object(sys, 'path', [str(ROOT / 'scripts'), *sys.path]):
    DOCTOR = run_path(str(ROOT / 'scripts/codex_doctor.py'))
check_other_repo_overlap = DOCTOR['check_other_repo_overlap']


@pytest.mark.unit
def test_doctor_reports_other_project_scope_overlaps(tmp_path: Path) -> None:
    root = tmp_path / 'mightymodels'
    root.mkdir()
    project = tmp_path / 'external'
    (project / '.git').mkdir(parents=True)
    codex = project / '.codex'
    codex.mkdir()
    (codex / 'config.toml').write_text('[mcp_servers.mighty_mcp]\ncommand = "sh"\n')
    (codex / 'hooks.json').write_text('{"hooks":{"PreToolUse":[]}}')
    nested = project / 'src'
    nested.mkdir()
    reports = check_other_repo_overlap(root, nested)
    assert len(reports) == 2
    assert 'both declare mighty_mcp' in reports[0]
    assert 'hooks coexist' in reports[1]
    assert all('unverified' in report for report in reports)


@pytest.mark.unit
def test_doctor_does_not_claim_overlap_without_declaration(tmp_path: Path) -> None:
    root = tmp_path / 'mightymodels'
    root.mkdir()
    project = tmp_path / 'external'
    (project / '.git').mkdir(parents=True)
    (project / '.codex').mkdir()
    (project / '.codex/config.toml').write_text('[mcp_servers.other]\ncommand = "sh"\n')
    assert check_other_repo_overlap(root, project) == []
    assert check_other_repo_overlap(root, tmp_path) == []


@pytest.mark.unit
def test_doctor_flags_malformed_project_files_without_exposing_secrets(tmp_path: Path) -> None:
    root = tmp_path / 'mightymodels'
    root.mkdir()
    project = tmp_path / 'external'
    (project / '.git').mkdir(parents=True)
    codex = project / '.codex'
    codex.mkdir()
    (codex / 'config.toml').write_text('PRIVATE_TOKEN = "abc"\n[broken')
    (codex / 'hooks.json').write_text('{"secret":"abc",')
    reports = check_other_repo_overlap(root, project)
    assert len(reports) == 2
    assert all('abc' not in report for report in reports)
    assert 'malformed' in reports[0]
    assert 'malformed' in reports[1]
