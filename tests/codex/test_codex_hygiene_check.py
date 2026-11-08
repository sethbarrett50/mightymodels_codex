"""Codex suppression check runs without edits in a disposable Git repository."""

import subprocess
from pathlib import Path
from runpy import run_path
from shutil import which

import pytest

GIT_BINARY = which('git') or '/usr/bin/git'

_checker = run_path(str(Path(__file__).resolve().parents[2] / 'scripts/codex_hygiene_check.py'))
added_suppression_count = _checker['added_suppression_count']
check = _checker['check']
audit_file = _checker['audit_file']


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
            GIT_BINARY,
            '-C',
            str(tmp_path),
            '-c',
            'user.name=Test',
            '-c',
            'user.email=test@example.invalid',
            'commit',
            '-qm',
            'baseline',
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


@pytest.mark.unit
def test_untracked_python_file_with_suppression_is_detected(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'new_file.py').write_text('value = 1  # noqa: F841\n')
    assert check('HEAD', repo) == 1


@pytest.mark.unit
def test_untracked_python_file_without_suppression_is_allowed(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'new_file.py').write_text('value = 1\n')
    assert check('HEAD', repo) == 0


@pytest.mark.unit
def test_ignored_python_file_is_not_checked(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / '.gitignore').write_text('ignored.py\n')
    (repo / 'ignored.py').write_text('value = 1  # type: ignore\n')
    assert check('HEAD', repo) == 0


@pytest.mark.unit
def test_untracked_symlink_python_file_fails_closed(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'new_file.py').symlink_to(repo / 'missing.py')
    assert check('HEAD', repo) == 2


@pytest.mark.unit
def test_unreadable_existing_baseline_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'file.py').write_text('x = 1  # noqa: F401\n')
    original = audit_file.__globals__['git']

    def broken_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        if args[0] == 'show':
            return subprocess.CompletedProcess(args, 128, '', 'simulated read failure')
        return original(root, *args)

    monkeypatch.setitem(audit_file.__globals__, 'git', broken_git)
    assert audit_file('HEAD', repo, Path('file.py')) == -1


@pytest.mark.unit
def test_missing_baseline_is_allowed_for_new_file(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    (repo / 'new_file.py').write_text('x = 1  # noqa: F401\n')
    assert audit_file('HEAD', repo, Path('new_file.py')) == 1
