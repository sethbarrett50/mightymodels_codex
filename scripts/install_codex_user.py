"""Install or remove MightyModels integrations for the current Codex user.

Never use sudo: files are managed only inside the invoking user's home.
Existing unrelated skill, agent, hook and MCP settings are preserved.
"""

import argparse
import json
import os
import shlex
import tomllib
from pathlib import Path

START = '# >>> mightymodels-codex managed >>>'
END = '# <<< mightymodels-codex managed <<<'
SKILL_COUNT = 19
AGENT_COUNT = 12


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
    data = json.loads((root / '.codex/hooks.json').read_text(encoding='utf-8'))
    command = 'python3 ' + shlex.quote(str(root / 'hooks/codex_bridge.py'))
    for groups in data['hooks'].values():
        for group in groups:
            for hook in group['hooks']:
                hook['command'] = command
    return json.dumps(data, indent=2) + '\n'


def update_hooks(path: Path, root: Path, *, remove: bool) -> None:
    """Do not overwrite an unrelated hooks file; identify ours by exact content."""
    expected = hook_config(root)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.read_text(encoding='utf-8') != expected:
            msg = f'Refusing unmanaged hooks configuration: {path}'
            raise FileExistsError(msg)
        path.unlink()
    if not remove:
        safe_write(path, expected)


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
    skills = sorted((root / 'skills').glob('*/SKILL.md'))
    if len(agents) != AGENT_COUNT or len(skills) != SKILL_COUNT:
        parser.error('Incomplete source checkout (expected 12 agents and 19 skills)')
    codex = home / '.codex'
    # Validate all potential collisions BEFORE changing anything.
    destinations = [(codex / 'agents' / x.name, x) for x in agents]
    destinations += [(home / '.agents/skills' / x.parent.name, x.parent) for x in skills]
    for dest, src in destinations:
        if dest.is_symlink():
            if dest.resolve(strict=False) != src.resolve():
                parser.error(f'Unmanaged symlink exists: {dest}')
        elif dest.exists():
            parser.error(f'Unmanaged path exists: {dest}')
    hooks = codex / 'hooks.json'
    expected_hooks = hook_config(root)
    if hooks.exists() and (
        hooks.is_symlink() or hooks.read_text(encoding='utf-8') != expected_hooks
    ):
        parser.error(f'Unmanaged hooks configuration exists: {hooks}; merge manually')
    try:  # noqa: PLW0717
        # Validate global config before modifying installed links.
        global_conf = codex / 'config.toml'
        old = global_conf.read_text(encoding='utf-8') if global_conf.exists() else ''
        parsed = tomllib.loads(old)
        if START not in old and 'mighty_mcp' in parsed.get('mcp_servers', {}):
            parser.error('Unmanaged global mighty_mcp exists; merge manually')
        for dest, src in destinations:
            reconcile_link(dest, src, remove=args.uninstall)
        update_config(global_conf, root, remove=args.uninstall)
        update_hooks(hooks, root, remove=args.uninstall)
        update_instructions(codex / 'AGENTS.md', root, remove=args.uninstall)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(
        ('Removed' if args.uninstall else 'Installed')
        + ' MightyModels user-level agents, skills, MCP, instructions and hooks.'
    )
    print('Restart Codex; review/trust hooks before relying on admission controls.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
