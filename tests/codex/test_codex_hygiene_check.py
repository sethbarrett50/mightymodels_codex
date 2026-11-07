"""Codex suppression check runs without edits in a disposable Git repository."""

import subprocess
from pathlib import Path
from runpy import run_path
from shutil import which

import pytest

GIT_BINARY = which('git')
assert GIT_BINARY is not None

_checker = run_path(str(Path(__file__).resolve().parents[2] / 'scripts/codex_hygiene_check.py'))
added_suppression_count = _checker['added_suppression_count']
check = _checker['check']


@pytest.mark.unit
def test_detects_only_new_suppressions() -> None:
    before = 'x = 1  # noqa: F401\n'
    assert added_suppression_count(before, before) == 0
    assert added_suppression_count(before, before + 'y = 2  # type: ignore\n') == 1
    assert added_suppression_count('', '# ruff: noqa\n# ty: ignore\n') == 2
    assert added_suppression_count('', '# normal comment\n') == 0


def setup_repo(tmp_path: Path) -> Path:
    subprocess.run(  # noqa: S603
        [GIT_BINARY, 'init', '-q', str(tmp_path)], check=True, capture_output=True
    )
    (tmp_path / 'file.py').write_text('x = 1\n')
    subprocess.run(  # noqa: S603
        [GIT_BINARY, '-C', str(tmp_path), 'add', 'file.py'],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603
        [
            'git', '-C', str(tmp_path),
            '-c', 'user.name=Test',
            '-c', 'user.email=test@example.invalid',
            'commit', '-qm', 'baseline',
        ],
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.mark.unit
def test_disposable_repository_detects_new_suppression(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    assert check('HEAD', repo) == 0
    (repo / 'file.py').write_text('x = 1  # noqa: F401\n')
    assert check('HEAD', repo) == 1


@pytest.mark.unit
def test_invalid_base_fails_closed(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    assert check('nonexistent-base', repo) == 2


@pytest.mark.unit
def test_does_not_follow_symlinks(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'file.py').unlink()
    (repo / 'file.py').symlink_to(repo / 'outside.py')
    assert check('HEAD', repo) == 2
