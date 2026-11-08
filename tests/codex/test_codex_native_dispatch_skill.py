"""Generated Codex dispatch instructions must not direct Claude-only API calls."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = run_path(str(ROOT / 'scripts/sync_codex_skills.py'))
translated = SYNC['translated']
native_dispatch_steps = SYNC['native_dispatch_steps']


@pytest.mark.unit
def test_prompting_subagents_uses_native_roles_without_claude_model_aliases() -> None:
    path = ROOT / 'skills/prompting-subagents/SKILL.md'
    generated = translated(path)
    assert '2. **Resolve the native role and model.**' in generated
    assert '5. **Dispatch with native Codex tools.**' in generated
    assert '`agent_type` set to the full registered' in generated
    assert '`mm-workers-engineer`' in generated
    assert '`mm-triage-code-scout`' in generated
    assert 'Pass the alias (haiku, sonnet, opus or fable)' not in generated
    assert '`subagent_type` the plugin-qualified' not in generated
    assert 'SendMessage` instead of a fresh dispatch' not in generated
    assert generated == (ROOT / '.codex/skills/prompting-subagents/SKILL.md').read_text(
        encoding='utf-8'
    )


@pytest.mark.unit
def test_dispatch_translation_fails_on_missing_original_steps() -> None:
    with pytest.raises(ValueError, match='exactly one Claude dispatch step'):
        native_dispatch_steps('## Incomplete instructions\\n')


@pytest.mark.unit
def test_dispatch_translation_rejects_duplicated_claude_steps() -> None:
    source = (ROOT / 'skills/prompting-subagents/SKILL.md').read_text(encoding='utf-8')
    body = source.split('---\\n', 2)[-1]
    repeated = body + '\\n' + body
    with pytest.raises(ValueError, match='exactly one Claude dispatch step'):
        native_dispatch_steps(repeated)
