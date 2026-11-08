"""Checkout-only, read-only post-edit Python checks for Codex.

Never rewrites checkout files, installs packages, emits source text, or checks
another repository. An explicit opt-in external canary can prove host delivery;
normal operation writes no probe file.
"""

import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_PATCH_SIZE = 131072
MAX_CHANGED_FILES = 20
CHECK_TIMEOUT = 8
HEADERS = ('*** Update File: ', '*** Add File: ', '*** Move to: ')
ERRORS = (OSError, subprocess.TimeoutExpired, ValueError)


def _event_patch(event: object, root: Path) -> tuple[Path, str] | None:
    """Require a local, bounded, successful Codex apply_patch result."""
    if (
        not isinstance(event, dict)
        or event.get('hook_event_name') != 'PostToolUse'
        or event.get('tool_name') != 'apply_patch'
    ):
        return None
    response = event.get('tool_response')
    if isinstance(response, dict) and (
        response.get('isError') is True or response.get('status') in ('failed', 'error')
    ):
        return None
    supplied = event.get('tool_input')
    cwd = event.get('cwd')
    if not isinstance(supplied, dict) or not isinstance(cwd, str):
        return None
    directory = Path(cwd).resolve()
    patch = supplied.get('command')
    if not directory.is_relative_to(root.resolve()):
        return None
    if not isinstance(patch, str) or len(patch) > MAX_PATCH_SIZE:
        return None
    return directory, patch


def _candidate(line: str, directory: Path, root: Path) -> Path | bool | None:
    """False marks an unsafe path, None marks an unrelated or missing file."""
    if not line.startswith(HEADERS):
        return None
    filename = line.split(': ', 1)[1].strip()
    relative = PurePosixPath(filename)
    if not filename or '..' in relative.parts:
        return False
    if relative.suffix not in ('.py', '.pyi'):
        return None
    candidate = Path(filename) if relative.is_absolute() else directory.joinpath(*relative.parts)
    if candidate.is_symlink() or not candidate.is_file():
        return None
    if not candidate.resolve().is_relative_to(root.resolve()):
        return False
    return candidate


def python_paths(event: object, root: Path) -> tuple[Path, ...]:
    """Select bounded existing Python paths without reading file contents."""
    context = _event_patch(event, root)
    if context is None:
        return ()
    directory, patch = context
    lines = patch.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        return ()
    files: list[Path] = []
    for line in lines[1:-1]:
        candidate = _candidate(line, directory, root)
        if candidate is False:
            return ()
        if isinstance(candidate, Path) and candidate not in files:
            files.append(candidate)
        if len(files) > MAX_CHANGED_FILES:
            return ()
    return tuple(files)


def _ruff_failures(binary: Path, files: tuple[Path, ...], root: Path) -> list[str]:
    failed: list[str] = []
    for label, args in (
        ('format', ('format', '--check')),
        ('lint', ('check', '--no-fix')),
    ):
        try:
            result = subprocess.run(  # noqa: S603
                [str(binary), *args, '--', *(str(path) for path in files)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=CHECK_TIMEOUT,
                check=False,
            )
        except ERRORS:
            failed.append(f'{label} unavailable')
        else:
            if result.returncode:
                failed.append(f'{label} did not pass')
    return failed


def _ty_failures(binary: Path, files: tuple[Path, ...], root: Path) -> list[str]:
    """Run the checkout's installed ty binary without modifying files."""
    try:
        result = subprocess.run(  # noqa: S603
            [str(binary), 'check', *(str(path) for path in files)],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=CHECK_TIMEOUT,
            check=False,
        )
    except ERRORS:
        return ['type check unavailable']
    return ['type check did not pass'] if result.returncode else []


def _missing_checkout_context(event: object) -> bool:
    if not isinstance(event, dict):
        return False
    if event.get('hook_event_name') != 'PostToolUse' or event.get('tool_name') != 'apply_patch':
        return False
    cwd = event.get('cwd')
    return not isinstance(cwd, str) or not cwd.strip()


def feedback(event: object, root: Path) -> dict | None:
    """Report only checker outcomes; never expose source, paths or stderr."""
    if _missing_checkout_context(event):
        return {
            'hookSpecificOutput': {
                'hookEventName': 'PostToolUse',
                'additionalContext': (
                    'MightyModels post-edit checks not run: '
                    'host hook event omitted its checkout directory.'
                ),
            }
        }
    files = python_paths(event, root)
    if not files:
        return None
    ruff = root / '.venv/bin/ruff'
    ty = root / '.venv/bin/ty'
    failed: list[str] = []
    if ruff.is_file():
        failed.extend(_ruff_failures(ruff, files, root))
    else:
        failed.append('Ruff not run (local Ruff unavailable)')
    if ty.is_file():
        failed.extend(_ty_failures(ty, files, root))
    else:
        failed.append('ty not run (local ty unavailable)')
    if not failed:
        return None
    message = (
        'MightyModels post-edit checks: '
        + ', '.join(failed)
        + '; run make check to inspect and correct issues.'
    )
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': message,
        }
    }


def probe_delivery(event: object, root: Path, environ: dict[str, str]) -> None:
    """Opt-in external canary: no arguments, paths or source contents retained."""
    if not isinstance(event, dict):
        return
    if event.get('hook_event_name') != 'PostToolUse' or event.get('tool_name') != 'apply_patch':
        return
    supplied = environ.get('MIGHTYMODELS_CODEX_POST_EDIT_PROBE_FILE')
    if not supplied:
        return
    target = Path(supplied)
    if not target.is_absolute() or target.resolve(strict=False).is_relative_to(root.resolve()):
        return
    try:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except OSError:
        return
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write('PostToolUse apply_patch observed\n')


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0
    root = Path(__file__).resolve().parents[1]
    probe_delivery(event, root, dict(os.environ))
    result = feedback(event, root)
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
