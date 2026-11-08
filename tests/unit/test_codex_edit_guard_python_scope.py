"""Guard added Python suppressions without blocking unrelated documentation text."""

from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[2]
inspect = run_path(str(ROOT / 'scripts/codex_edit_guard.py'))['inspect']


def event(patch: str) -> dict:
    return {
        'hook_event_name': 'PreToolUse',
        'tool_name': 'apply_patch',
        'tool_input': {'command': patch},
    }


@pytest.mark.unit
def test_nonpython_noqa_examples_are_not_python_suppressions() -> None:
    patch = '*** Begin Patch\n*** Update File: README.md\n@@\n+# noqa in a code sample\n*** End Patch'
    assert inspect(event(patch)) is None


@pytest.mark.unit
@pytest.mark.parametrize('suffix', ['py', 'pyi'])
@pytest.mark.parametrize('annotation', ['# noqa: F401', '# ruff: noqa', '# type: ignore'])
def test_python_suppressions_remain_blocked(suffix: str, annotation: str) -> None:
    patch = (
        f'*** Begin Patch\n*** Update File: src/demo.{suffix}\n'
        f'@@\n+value = 1  {annotation}\n*** End Patch'
    )
    assert inspect(event(patch)) == 'New lint/type suppression requires independent human review'


@pytest.mark.unit
def test_multifile_patches_check_each_file_independently() -> None:
    patch = (
        '*** Begin Patch\n*** Update File: README.md\n'
        '@@\n+# noqa sample\n*** Update File: src/sample.py\n'
        '@@\n+value = 1  # noqa\n*** End Patch'
    )
    assert inspect(event(patch)) == 'New lint/type suppression requires independent human review'


@pytest.mark.unit
def test_lockfile_and_path_traversal_protections_remain() -> None:
    lock = '*** Begin Patch\n*** Update File: uv.lock\n@@\n+text\n*** End Patch'
    traversal = '*** Begin Patch\n*** Add File: ../escape.md\n+text\n*** End Patch'
    assert 'Direct uv.lock edits are blocked' in inspect(event(lock))
    assert inspect(event(traversal)) == 'Patch path outside the project scope'
