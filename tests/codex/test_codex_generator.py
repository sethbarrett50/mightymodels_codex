"""Check Codex roles cannot silently drift from Claude agent sources."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.unit
def test_native_agent_files_match_sources() -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, 'scripts/sync_codex_agents.py', '--check'],
        cwd=root,
        check=True,
    )
