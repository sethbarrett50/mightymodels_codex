"""Project Codex edit guard checks do not depend on a trusted live hook host."""

import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARD = SimpleNamespace(**runpy.run_path(str(ROOT / 'scripts/codex_edit_guard.py')))


def event(patch: str) -> dict[str, object]:
    return {
        'hook_event_name': 'PreToolUse',
        'tool_name': 'apply_patch',
        'tool_input': {'command': patch},
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'added',
    [
        '+import os  # noqa: F401',
        '+value: int = 1  # type: ignore[assignment]',
        '+value = 1  # ty: ignore',
    ],
)
def test_new_suppressions_are_denied_before_patch(added: str) -> None:
    patch = f'*** Begin Patch\n*** Update File: src/app.py\n@@\n{added}\n*** End Patch'
    assert 'suppression' in GUARD.inspect(event(patch))


@pytest.mark.unit
def test_existing_suppression_in_context_is_not_a_new_suppression() -> None:
    patch = (
        '*** Begin Patch\n*** Update File: src/app.py\n@@\n'
        ' already = True  # noqa: F401\n+value = 1\n*** End Patch'
    )
    assert GUARD.inspect(event(patch)) is None


@pytest.mark.unit
@pytest.mark.parametrize('header', ['*** Update File: uv.lock', '*** Move to: sub/uv.lock'])
def test_direct_lockfile_patching_is_denied(header: str) -> None:
    patch = f'*** Begin Patch\n{header}\n@@\n+value = 1\n*** End Patch'
    assert 'uv.lock' in GUARD.inspect(event(patch))


@pytest.mark.unit
def test_path_traversal_is_denied() -> None:
    patch = '*** Begin Patch\n*** Update File: ../outside.py\n@@\n+thing = True\n*** End Patch'
    assert 'scope' in GUARD.inspect(event(patch))


@pytest.mark.unit
def test_normal_code_edit_is_not_denied() -> None:
    patch = '*** Begin Patch\n*** Update File: src/app.py\n@@\n+thing = True\n*** End Patch'
    assert GUARD.inspect(event(patch)) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    'payload',
    [
        {},
        {'hook_event_name': 'PreToolUse', 'tool_name': 'apply_patch'},
        {
            'hook_event_name': 'PreToolUse',
            'tool_name': 'apply_patch',
            'tool_input': {'command': 'echo nope'},
        },
    ],
)
def test_unknown_edit_schema_denied_without_echoing_payload(payload: object) -> None:
    assert GUARD.inspect(payload)


@pytest.mark.unit
def test_denial_uses_codex_pretooluse_shape_without_patch_content() -> None:
    got = GUARD.deny('New lint/type suppression requires independent human review')
    assert got['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert got['hookSpecificOutput']['hookEventName'] == 'PreToolUse'
    assert 'source' not in str(got)
