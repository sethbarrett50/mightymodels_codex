"""Check Codex roles cannot silently drift from Claude agent sources."""
import subprocess
from pathlib import Path

import pytest


@pytest.mark.unit
def test_native_agent_files_match_sources():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["python3", "scripts/sync_codex_agents.py", "--check"],
        cwd=root,
        check=True,
    )
