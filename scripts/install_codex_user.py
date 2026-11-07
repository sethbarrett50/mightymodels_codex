"""Install or remove MightyModels integrations for the current Codex user.

Never use sudo: files are managed only inside the invoking user's home.
Existing unrelated skill, agent, hook and MCP settings are preserved.
"""

import argparse
import json
import os
import shlex
import tomllib
from collections.abc import Iterator  # noqa: TC003 - required by Python 3.13 at runtime
from contextlib import contextmanager, suppress
from pathlib import Path
from stat import S_IMODE

START = '# >>> mightymodels-codex managed >>>'
END = '# <<< mightymodels-codex managed <<<'
SKILL_COUNT = 19
AGENT_COUNT = 11
_INSTALL_ERRORS = (OSError, ValueError, TypeError)
_ROLLBACK_ERRORS = (OSError, ValueError)


def managed_text(text: str, replacement: str) -> str:
    """Replace the managed stanza without altering unrelated content."""
    if text.count(START) != text.count(END) or text.count(START) > 1:
        msg = 'Malformed MightyModels managed markers'
        raise ValueError(msg)
    if START in text:
        left, remainder = text.split(START, 1)
        _, right = remainder.split(END, 1)
        text = left.rstrip('\n') + '\n' + right.lstrip('\n')
    return text.rstrip('\n') + (
        '\n\n' + START + '\n' + replacement.rstrip('\n') + '\n' + END + '\n'
        if replacement
        else '\n'
    )


def safe_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.mightymodels-tmp')
    if tmp.exists() or tmp.is_symlink():
        msg = f'Refusing existing temporary file: {tmp}'
        raise FileExistsError(msg)
    tmp.write_text(content, encoding='utf-8')
    Path(tmp).chmod(0o600)
    tmp.replace(path)


Snapshot = tuple[Path, str, bytes | Path | None, int]


def capture_snapshot(path: Path) -> Snapshot:
    if path.is_symlink():
        return path, 'link', path.readlink(), 0
    if path.is_file():
        return path, 'file', path.read_bytes(), S_IMODE(path.stat().st_mode)
    if path.exists():
        msg = f'Refusing to snapshot non-file destination: {path}'
        raise FileExistsError(msg)
    return path, 'absent', None, 0


def restore_snapshot(snapshot: Snapshot) -> None:
    path, kind, saved, mode = snapshot
    if path.is_symlink() or path.is_file():
        path.unlink()
    if kind == 'link' and isinstance(saved, Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(saved)
    elif kind == 'file' and isinstance(saved, bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(saved)
        path.chmod(mode)


def remove_empty_created_directories(directories: set[Path]) -> None:
    for directory in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        with suppress(OSError):
            directory.rmdir()


@contextmanager
def restore_on_failure(paths: list[Path]) -> Iterator[None]:
    """Undo file/link mutations on ordinary failures; not a crash-safe journal."""
    snapshots = [capture_snapshot(path) for path in paths]
    missing_dirs: set[Path] = set()
    for path in paths:
        parent = path.parent
        while not parent.exists():
            missing_dirs.add(parent)
            parent = parent.parent
    try:
        yield
    except _ROLLBACK_ERRORS:
        for snapshot in reversed(snapshots):
            restore_snapshot(snapshot)
        remove_empty_created_directories(missing_dirs)
        raise


def reconcile_link(destination: Path, source: Path, *, remove: bool) -> None:
    if destination.is_symlink():
        if destination.resolve(strict=False) != source.resolve():
            msg = f'Refusing unrelated symlink: {destination}'
            raise FileExistsError(msg)
        destination.unlink()
    elif destination.exists():
        msg = f'Refusing existing unmanaged path: {destination}'
        raise FileExistsError(msg)
    if not remove:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source, target_is_directory=True)


def hook_config(root: Path) -> str:
    data = json.loads((root / 'hooks/codex-global-template.json').read_text(encoding='utf-8'))
    command = 'python3 ' + shlex.quote(str(root / 'hooks/codex_bridge.py'))
    for groups in data['hooks'].values():
        for group in groups:
            for hook in group['hooks']:
                hook['command'] = command
    return json.dumps(data, indent=2) + '\n'


def hooks_are_owned(held: str, expected: str) -> bool:
    """Allow previous MightyModels hook subsets, but never unrelated hooks."""
    try:
        original = json.loads(held)
        current = json.loads(expected)
    except ValueError:
        return False
    if (
        not isinstance(original, dict)
        or set(original) != set(current)
        or original.get('description') != current['description']
    ):
        return False
    observed = original.get('hooks')
    supported = current['hooks']
    return (
        isinstance(observed, dict)
        and bool(observed)
        and all(
            key in supported
            and isinstance(value, list)
            and bool(value)
            and value == supported[key][: len(value)]
            for key, value in observed.items()
        )
    )


def managed_hooks_present(held: str, expected: str) -> bool:
    """Verify every owned event group is installed, even alongside foreign hooks."""
    try:
        original = json.loads(held)
        required = json.loads(expected)
    except ValueError:
        return False
    if not isinstance(original, dict) or not isinstance(original.get('hooks'), dict):
        return False
    observed = original['hooks']
    return all(
        isinstance(observed.get(event), list)
        and all(observed[event].count(group) == 1 for group in groups)
        for event, groups in required['hooks'].items()
    )


def validate_hook_groups(groups: list, expected: list) -> None:
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get('hooks'), list):
            msg = 'Invalid global hook group structure'
            raise TypeError(msg)
        for hook in group['hooks']:
            if not isinstance(hook, dict):
                msg = 'Invalid global hook command structure'
                raise TypeError(msg)
            command = hook.get('command')
            if isinstance(command, str) and 'codex_bridge.py' in command and group not in expected:
                msg = 'Existing MightyModels bridge hook differs from expected definition'
                raise ValueError(msg)


def reconcile_event_groups(groups: list, wanted: list, *, remove: bool, event: str) -> bool:  # noqa: PLR0913
    """Apply exact owned group additions/removals without touching foreign entries."""
    validate_hook_groups(groups, wanted)
    changed = False
    for group in wanted:
        count = groups.count(group)
        if count > 1:
            msg = f'Duplicate managed MightyModels hook group for {event}'
            raise ValueError(msg)
        if remove and count:
            groups.remove(group)
            changed = True
        elif not remove and not count:
            groups.append(group)
            changed = True
    return changed


def merge_hook_text(existing: str | None, expected: str, *, remove: bool) -> str | None:  # noqa: C901, PLR0912
    """Reconcile exact owned groups, preserving unrelated hook definitions."""
    if existing is None or hooks_are_owned(existing, expected):
        return None if remove else expected
    try:
        held = json.loads(existing)
        required = json.loads(expected)
    except ValueError as exc:
        msg = 'Malformed global hooks JSON'
        raise ValueError(msg) from exc
    if not isinstance(held, dict) or not isinstance(held.get('hooks'), dict):
        msg = 'Global hooks must contain a hooks object'
        raise TypeError(msg)

    changed = False
    for event, wanted in required['hooks'].items():
        groups = held['hooks'].get(event, [])
        if not isinstance(groups, list):
            msg = f'Global hook groups for {event} must be a list'
            raise TypeError(msg)
        event_changed = reconcile_event_groups(groups, wanted, remove=remove, event=event)
        changed = changed or event_changed
        if groups:
            held['hooks'][event] = groups
        elif event in held['hooks'] and event_changed:
            del held['hooks'][event]
    if not changed:
        return existing
    if (
        remove
        and not held['hooks']
        and set(held) == set(required)
        and held.get('description') == required['description']
    ):
        return None
    return json.dumps(held, indent=2) + '\n'


def update_hooks(path: Path, root: Path, *, remove: bool) -> None:
    """Merge owned groups without clobbering unrelated Codex user hooks."""
    existing = path.read_text(encoding='utf-8') if path.exists() else None
    content = merge_hook_text(existing, hook_config(root), remove=remove)
    if content is None:
        if path.exists():
            path.unlink()
    elif content != existing:
        safe_write(path, content)


def update_config(path: Path, root: Path, *, remove: bool) -> None:
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    # Parse before editing and again afterwards to avoid corrupting Codex config.
    parsed = tomllib.loads(original)
    if START not in original and 'mighty_mcp' in parsed.get('mcp_servers', {}):
        msg = 'Existing mighty_mcp is not managed by this installer'
        raise ValueError(msg)
    if START not in original:
        reserved = [name for name in parsed.get('agents', {}) if name.startswith('mm-')]
        if reserved:
            msg = f'Existing unowned MightyModels agent role declarations: {reserved}'
            raise ValueError(msg)
    quoted = json.dumps(str(root / 'bin/mightymodels-mcp-codex'))
    role_entries = []
    for role_file in sorted((root / '.codex/agents').glob('mm-*.toml')):
        name = role_file.stem
        role_description = tomllib.loads(role_file.read_text(encoding='utf-8'))['description']
        role_entries.append(
            f'[agents.{json.dumps(name)}]\n'
            f'description = {json.dumps(role_description)}\n'
            f'config_file = {json.dumps(str(role_file))}'
        )
    block = (
        ''
        if remove
        else (
            f'[mcp_servers.mighty_mcp]\ncommand = "sh"\nargs = [{quoted}]\n'
            'startup_timeout_sec = 30\n\n' + '\n\n'.join(role_entries)
        )
    )
    content = managed_text(original, block)
    tomllib.loads(content)
    if content != original:
        safe_write(path, content)


def update_instructions(path: Path, root: Path, *, remove: bool) -> None:
    original = path.read_text(encoding='utf-8') if path.exists() else ''
    block = (
        ''
        if remove
        else (
            'MightyModels user-scoped installation: read '
            f'{root / "AGENTS.md"} before running MightyModels skills or agents.\n'
            'Do not infer authorization from prompts alone; deny unverified dispatches.\n'
            'Use the mighty_mcp server to persist ticket and task state.'
        )
    )
    content = managed_text(original, block)
    if content != original:
        safe_write(path, content)


def main() -> int:  # noqa: C901, PLR0912, PLR0914, PLR0915
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uninstall', action='store_true')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    home = args.home.expanduser().resolve()
    if os.geteuid() == 0:
        parser.error('Run as the intended unprivileged Codex user, not root')
    agents = sorted((root / '.codex/agents').glob('mm-*.toml'))
    skills = sorted((root / '.codex/skills').glob('*/SKILL.md'))
    if len(agents) != AGENT_COUNT or len(skills) != SKILL_COUNT:
        parser.error('Incomplete source checkout (expected 11 enabled agents and 19 skills)')
    codex = home / '.codex'
    # Validate all potential collisions BEFORE changing anything.
    destinations = [(codex / 'agents' / x.name, x) for x in agents]
    destinations += [(home / '.agents/skills' / x.parent.name, x.parent) for x in skills]
    old_skill_links = {
        home / '.agents/skills' / skill.parent.name: root / 'skills' / skill.parent.name
        for skill in skills
    }
    for dest, src in destinations:
        if dest.is_symlink():
            previous = old_skill_links.get(dest)
            accepted = {src.resolve()}
            if previous is not None:
                accepted.add(previous.resolve())
            if dest.resolve(strict=False) not in accepted:
                parser.error(f'Unmanaged symlink exists: {dest}')
        elif dest.exists():
            parser.error(f'Unmanaged path exists: {dest}')
    # Remove an obsolete wingman symlink left by installations before model routing.
    retired = codex / 'agents/mm-triage-wingman.toml'
    retired_source = root / '.codex/agents/mm-triage-wingman.toml'
    if retired.is_symlink():
        if retired.resolve(strict=False) != retired_source.resolve(strict=False):
            parser.error(f'Unmanaged retired agent symlink: {retired}')
    elif retired.exists():
        parser.error(f'Unmanaged retired agent path: {retired}')
    hooks = codex / 'hooks.json'
    expected_hooks = hook_config(root)
    if hooks.is_symlink():
        parser.error(f'Unmanaged hooks symlink exists: {hooks}')
    try:  # noqa: PLW0717, PLR1702
        # Check user hooks can be merged before touching any links.
        merge_hook_text(
            hooks.read_text(encoding='utf-8') if hooks.exists() else None,
            expected_hooks,
            remove=args.uninstall,
        )
        # Validate global config before modifying installed links.
        global_conf = codex / 'config.toml'
        if global_conf.is_symlink():
            parser.error(f'Refusing global config symlink: {global_conf}')
        old = global_conf.read_text(encoding='utf-8') if global_conf.exists() else ''
        parsed = tomllib.loads(old)
        if START not in old and 'mighty_mcp' in parsed.get('mcp_servers', {}):
            parser.error('Unmanaged global mighty_mcp exists; merge manually')
        if START not in old:
            reserved = [name for name in parsed.get('agents', {}) if name.startswith('mm-')]
            if reserved:
                parser.error(f'Existing unowned MightyModels agent role declarations: {reserved}')
        # Preflight managed markers and stale temporary files before touching links.
        # The individual updaters validate these too, but only after link mutations.
        managed_text(old, '')
        instructions = codex / 'AGENTS.md'
        if instructions.is_symlink():
            parser.error(f'Refusing symlink to global instructions: {instructions}')
        managed_text(instructions.read_text(encoding='utf-8') if instructions.exists() else '', '')
        for target in (global_conf, hooks, instructions):
            tmp = target.with_name(target.name + '.mightymodels-tmp')
            if tmp.exists() or tmp.is_symlink():
                parser.error(f'Refusing existing temporary file: {tmp}')
        affected = [dest for dest, _ in destinations]
        affected.extend((retired, global_conf, hooks, instructions))
        with restore_on_failure(affected):
            for dest, src in destinations:
                previous = old_skill_links.get(dest)
                if (
                    previous is not None
                    and dest.is_symlink()
                    and dest.resolve(strict=False) == previous.resolve()
                ):
                    dest.unlink()
                reconcile_link(dest, src, remove=args.uninstall)
            reconcile_link(retired, retired_source, remove=True)
            update_config(global_conf, root, remove=args.uninstall)
            update_hooks(hooks, root, remove=args.uninstall)
            update_instructions(instructions, root, remove=args.uninstall)
    except _INSTALL_ERRORS as exc:
        parser.error(str(exc))
    print(
        ('Removed' if args.uninstall else 'Installed')
        + ' MightyModels user-level agents, skills, MCP, instructions and hooks.'
    )
    print('Restart Codex; review/trust hooks before relying on admission controls.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
