"""Reject malformed apply_patch shapes before project suppression checks."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
inspect = run_path(str(ROOT / 'scripts/codex_edit_guard.py'))['inspect']


def event(patch: str) -> dict[str, object]:
    return {
        'hook_event_name': 'PreToolUse',
        'tool_name': 'apply_patch',
        'tool_input': {'command': patch},
    }


@pytest.mark.unit
@pytest.mark.parametrize(
    'patch',
    [
        '*** Begin Patch\n*** End Patch',
        '*** Begin Patch\n@@\n+new = True\n*** End Patch',
    ],
)
def test_patch_must_identify_at_least_one_file(patch: str) -> None:
    assert inspect(event(patch)) is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    'patch',
    [
        '*** Begin Patch\n*** Update File: src/demo.py\n@@\n+value = 1',
        '*** Begin Patch\n*** Update File: src/demo.py\n@@\n+value = 1\n*** End Patch\n+extra',
        '*** Begin Patch\n*** Add File: src/demo.py\n+value = 1\n*** End Patch\n@@',
    ],
)
def test_patch_must_have_exact_boundaries(patch: str) -> None:
    assert inspect(event(patch)) == 'Malformed project patch boundaries'


@pytest.mark.unit
def test_patch_cannot_have_edits_before_first_file_header() -> None:
    patch = (
        '*** Begin Patch\n+value = 1\n*** Update File: src/demo.py\n@@\n+print(1)\n*** End Patch'
    )
    assert inspect(event(patch)) == 'Edit patch has changes without a file header'


@pytest.mark.unit
def test_empty_path_cannot_bypass_patch_inspection() -> None:
    patch = '*** Begin Patch\n*** Update File: \n@@\n+value = 1\n*** End Patch'
    assert inspect(event(patch)) == 'Edit patch has an empty file path'


@pytest.mark.unit
def test_valid_multi_file_patch_still_permitted_without_suppressions() -> None:
    patch = (
        '*** Begin Patch\n*** Update File: README.md\n@@\n+Some words\n'
        '*** Update File: src/demo.py\n@@\n+value = 2\n*** End Patch'
    )
    assert inspect(event(patch)) is None
