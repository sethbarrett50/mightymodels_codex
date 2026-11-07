"""Structural smoke tests for Codex plugin and project packaging."""
import json
from pathlib import Path
import subprocess
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_all_codex_roles_are_discoverable():
    originals = list((ROOT / "agents").rglob("*.md"))
    converted = list((ROOT / ".codex" / "agents").glob("*.toml"))
    assert len(originals) == len(converted) == 12
    for path in converted:
        role = tomllib.loads(path.read_text(encoding="utf-8"))
        for required in ("name", "description", "developer_instructions"):
            assert isinstance(role.get(required), str) and role[required]
        assert role["name"] == path.stem
        assert "astra" not in str(role.get("model", "")).lower()


@pytest.mark.unit
def test_plugin_and_mcp_metadata():
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))
    assert manifest["extensions"]["com.openai"]["hooks"] == "./hooks/codex-hooks.json"
    server = mcp["mcpServers"]["mighty-mcp"]
    assert server["type"] == "stdio"
    assert server["command"] == "./bin/mightymodels-mcp-codex"
    assert (ROOT / server["command"]).is_file()
    assert (ROOT / server["command"]).stat().st_mode & 0o111


@pytest.mark.unit
def test_project_scoped_skills():
    source = sorted((ROOT / "skills").glob("*/SKILL.md"))
    assert len(source) == 19
    for item in source:
        skill = ROOT / ".agents" / "skills" / item.parent.name
        assert skill.is_symlink()
        assert skill.resolve() == item.parent.resolve()


@pytest.mark.unit
def test_hook_configurations_parse():
    for path in ("hooks/codex-hooks.json", ".codex/hooks.json"):
        data = json.loads((ROOT / path).read_text(encoding="utf-8"))
        group = data["hooks"]["PreToolUse"][0]
        assert "Agent" in group["matcher"]
        assert group["hooks"][0]["type"] == "command"
    tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))


@pytest.mark.unit
def test_shell_launcher_syntax():
    subprocess.run(
        ["sh", "-n", "bin/mightymodels-mcp-codex"],
        check=True,
        cwd=ROOT,
    )
