"""GitHub credential guidance must not advise dumping PAT material."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.parametrize('name', ('AGENTS.md', 'docs/CODEX.md'))
def test_credential_policy(name: str) -> None:
    content = (ROOT / name).read_text(encoding='utf-8')
    assert 'gh auth status -h github.com' in content
    assert 'gh api user --jq .login' in content
    assert 'hosts.yml' in content
    assert 'GH_TOKEN' in content
    assert 'GITHUB_TOKEN' in content
    assert 'Never' in content or 'never' in content
