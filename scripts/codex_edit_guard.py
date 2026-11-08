"""Project-only Codex apply_patch guard; never modifies files or logs patch content.

This is an advisory local hook, not a sandbox or a guarantee that every edit
path is intercepted. It intentionally fails closed on unknown patch schemas.
"""

import json
import re
import sys
from pathlib import PurePosixPath

_SUPPRESSION = re.compile(
    r'#\s*(?:ruff\s*:\s*)?noqa\b|#\s*(?:type|ty)\s*:\s*ignore\b',
    re.IGNORECASE,
)
_BAD_INPUT = (ValueError, UnicodeError)
_PATCH_HEADERS = (
    '*** Update File: ',
    '*** Add File: ',
    '*** Delete File: ',
    '*** Move to: ',
)


def deny(reason: str) -> dict:
    return {
        'hookSpecificOutput': {
            'hookEventName': 'PreToolUse',
            'permissionDecision': 'deny',
            'permissionDecisionReason': reason,
        }
    }


def inspect(event: object) -> str | None:  # noqa: C901, PLR0911, PLR0912
    """Return a sanitized reason only when an edit should not proceed."""
    if not isinstance(event, dict) or event.get('hook_event_name') != 'PreToolUse':
        return 'Unrecognized project edit hook event'
    if event.get('tool_name') not in ('apply_patch', 'Edit', 'Write'):
        return 'Unrecognized tool for project edit guard'
    arguments = event.get('tool_input')
    if not isinstance(arguments, dict):
        return 'Edit arguments unavailable for project review'
    patch = arguments.get('command')
    if not isinstance(patch, str) or not patch.lstrip().startswith('*** Begin Patch'):
        return 'Edit patch unavailable for project review'
    lines = patch.splitlines()
    if not lines or lines[0] != '*** Begin Patch' or lines[-1] != '*** End Patch':
        return 'Malformed project patch boundaries'
    python_file = False
    file_header_seen = False
    for line in lines[1:-1]:
        if line.startswith(_PATCH_HEADERS):
            path = line.split(': ', 1)[1].strip()
            if not path:
                return 'Edit patch has an empty file path'
            parts = PurePosixPath(path)
            if parts.is_absolute() or '..' in parts.parts:
                return 'Patch path outside the project scope'
            if parts.name == 'uv.lock':
                return 'Direct uv.lock edits are blocked; use the dependency lock workflow'
            file_header_seen = True
            python_file = parts.suffix in ('.py', '.pyi')
        added_line = line.startswith('+') and not line.startswith('+++')
        if added_line and not file_header_seen:
            return 'Edit patch has changes without a file header'
        if python_file and added_line and _SUPPRESSION.search(line[1:]):
            return 'New lint/type suppression requires independent human review'
    return None if file_header_seen else 'Edit patch has no recognized file header'


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except _BAD_INPUT:
        print(json.dumps(deny('Invalid project edit hook payload')))
        return 0
    reason = inspect(event)
    if reason is not None:
        print(json.dumps(deny(reason)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
