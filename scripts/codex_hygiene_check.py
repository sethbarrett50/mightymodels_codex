"""Check newly introduced Python lint/type suppression comments against a Git base.

This is an explicit, read-only fallback for Codex environments without verified
per-edit hook delivery. It never formats files or grants edit approvals.
"""

import argparse
import re
import subprocess
from collections import Counter
from pathlib import Path

SUPPRESSION = re.compile(r'(?i)#\\s*(?:ruff:\\s*)?noqa\\b|#\\s*(?:type|ty):\\s*ignore\\b')


def suppressions(source: str) -> Counter[str]:
    return Counter(
        line.strip()
        for line in source.splitlines()
        if SUPPRESSION.search(line)
    )


def added_suppression_count(before: str, after: str) -> int:
    return sum((suppressions(after) - suppressions(before)).values())


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ['git', '-C', str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def check(base: str, root: Path) -> int:
    verified = git(root, 'rev-parse', '--verify', '--end-of-options', f'{base}^{{commit}}')
    if verified.returncode:
        print('Cannot verify requested base commit; no hygiene check performed.')
        return 2
    changed = subprocess.run(  # noqa: S603
        ['git', '-C', str(root), 'diff', '-z', '--name-only', '--diff-filter=ACMR', base, '--'],
        capture_output=True,
        check=False,
    )
    if changed.returncode:
        print('Could not enumerate tracked changes; no hygiene check performed.')
        return 2

    found = False
    for raw in changed.stdout.split(b'\\0'):
        if not raw:
            continue
        relative = Path(raw.decode('utf-8', errors='surrogateescape'))
        if relative.suffix not in {'.py', '.pyi'}:
            continue
        target = root / relative
        if target.is_symlink() or not target.is_file():
            print(f'Skipped unsafe or missing Python path: {relative}')
            return 2
        previous = git(root, 'show', f'{base}:{relative.as_posix()}')
        if previous.returncode:
            # New files have no version at the requested base.
            previous_source = ''
        else:
            previous_source = previous.stdout
        try:
            current_source = target.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            print(f'Could not read Python source: {relative}')
            return 2
        count = added_suppression_count(previous_source, current_source)
        if count:
            found = True
            print(f'{relative}: {count} new lint/type suppression(s); review required')
    if found:
        print('No automatic approval: review new suppressions before proceeding.')
        return 1
    print('No newly introduced Python lint/type suppressions found in tracked changes.')
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='Known Git commit/ref to compare')
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    return check(args.base, args.root.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
