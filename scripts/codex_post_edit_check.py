"""Checkout-only, read-only post-edit Python checks for Codex.

Never rewrites files, installs packages, emits source text, or checks another
repository. A configured hook is not proof that the Codex host delivered it.
"""

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

MAX_PATCH_SIZE = 131072
MAX_CHANGED_FILES = 20
CHECK_TIMEOUT = 8
HEADERS = ('*** Update File: ', '*** Add File: ', '*** Move to: ')
ERRORS = (OSError, subprocess.TimeoutExpired, ValueError)


def python_paths(event: object, root: Path) -> tuple[Path, ...]:
    """Extract existing Python files from a bounded successful project patch."""
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PostToolUse':
        return ()
    if event.get('tool_name') != 'apply_patch':
        return ()
    response = event.get('tool_response')
    if isinstance(response, dict) and (
        response.get('isError') is True or response.get('status') in ('failed', 'error')
    ):
        return ()
    supplied = event.get('tool_input')
    cwd = event.get('cwd')
    if not isinstance(supplied, dict) or not isinstance(cwd, str):
        return ()
    directory = Path(cwd).resolve()
    if not directory.is_relative_to(root.resolve()):
        return ()
    patch = supplied.get('command')
    if not isinstance(patch, str) or len(patch) > MAX_PATCH_SIZE:
        return ()
    lines = patch.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        return ()
    files: list[Path] = []
    for line in lines[1:-1]:
        if not line.startswith(HEADERS):
            continue
        filename = line.split(': ', 1)[1].strip()
        part = PurePosixPath(filename)
        if not filename or part.is_absolute() or '..' in part.parts:
            return ()
        if part.suffix not in ('.py', '.pyi'):
            continue
        candidate = directory.joinpath(*part.parts)
        if candidate.is_symlink() or not candidate.is_file():
            continue
        if not candidate.resolve().is_relative_to(root.resolve()):
            return ()
        if candidate not in files:
            files.append(candidate)
        if len(files) > MAX_CHANGED_FILES:
            return ()
    return tuple(files)


def feedback(event: object, root: Path) -> dict | None:
    """Report only checker outcomes; never expose source, paths or stderr."""
    files = python_paths(event, root)
    if not files:
        return None
    binary = root / '.venv/bin/ruff'
    if not binary.is_file():
        message = 'MightyModels post-edit Ruff check not run (local Ruff unavailable); run make check.'
    else:
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
        if not failed:
            return None
        message = (
            'MightyModels post-edit checks: ' + ', '.join(failed)
            + '; run make check to inspect and correct issues.'
        )
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': message,
        }
    }


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        return 0
    result = feedback(event, Path(__file__).resolve().parents[1])
    if result is not None:
        print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
