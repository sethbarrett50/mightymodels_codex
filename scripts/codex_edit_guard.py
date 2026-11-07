"""Project-only Codex apply_patch guard; never modifies files or logs patch content.

This is an advisory local hook, not a sandbox or a guarantee that every edit
path is intercepted. It intentionally fails closed on unknown patch schemas.
"""

import json
import re
import sys
from pathlib import PurePosixPath

_SUPPRESSION = re.compile(r'#\\s*(?:noqa\\b|(?:type|ty)\\s*:\\s*ignore\\b)', re.IGNORECASE)
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


def inspect(event: object) -> str | None:
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
    for line in patch.splitlines():
        if line.startswith(_PATCH_HEADERS):
            path = line.split(': ', 1)[1].strip()
            parts = PurePosixPath(path)
            if parts.is_absolute() or '..' in parts.parts:
                return 'Patch path outside the project scope'
            if parts.name == 'uv.lock':
                return 'Direct uv.lock edits are blocked; use the dependency lock workflow'
        if line.startswith('+') and not line.startswith('+++') and _SUPPRESSION.search(line[1:]):
            return 'New lint/type suppression requires independent human review'
    return None


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        print(json.dumps(deny('Invalid project edit hook payload')))
        return 0
    reason = inspect(event)
    if reason is not None:
        print(json.dumps(deny(reason)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
