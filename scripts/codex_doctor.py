"""Read-only Codex installation diagnostics without credential access or writes."""

import argparse
import tomllib
from pathlib import Path

from install_codex_user import AGENT_COUNT, SKILL_COUNT, hook_config, hooks_are_owned

_CONFIG_READ_ERRORS = (OSError, ValueError)


def note(message: str, *, ok: bool) -> str:
    return f'[{"OK" if ok else "FAIL"}] {message}'


def check_mcp(config: dict, root: Path) -> str:
    server = config.get('mcp_servers', {}).get('mighty_mcp', {})
    valid = server.get('command') == 'sh' and server.get('args') == [
        str(root / 'bin/mightymodels-mcp-codex')
    ]
    message = (
        'Global MightyModels MCP launcher registered'
        if valid
        else 'Global MightyModels MCP registration missing or unexpected'
    )
    return note(message, ok=valid)


def check_agents(config: dict, home: Path, root: Path) -> str:
    agents = config.get('agents', {})
    codex = home / '.codex'
    valid = sum(
        bool(
            (codex / 'agents' / f'{name}.toml').is_symlink()
            and (codex / 'agents' / f'{name}.toml').resolve(strict=False) == source.resolve()
            and agents.get(name, {}).get('config_file') == str(source)
        )
        for source in (root / '.codex/agents').glob('mm-*.toml')
        for name in (source.stem,)
    )
    message = f'Installed owned native agent registrations: {valid}/{AGENT_COUNT}'
    return note(message, ok=valid == AGENT_COUNT)


def check_skills(home: Path, root: Path) -> str:
    valid = sum(
        bool(
            (home / '.agents/skills' / source.parent.name).is_symlink()
            and (home / '.agents/skills' / source.parent.name).resolve(strict=False)
            == source.parent.resolve()
        )
        for source in (root / '.codex/skills').glob('*/SKILL.md')
    )
    message = f'Installed owned Codex skill links: {valid}/{SKILL_COUNT}'
    return note(message, ok=valid == SKILL_COUNT)


def check_hooks(home: Path, root: Path) -> str:
    hooks = home / '.codex/hooks.json'
    if not hooks.is_file() or hooks.is_symlink():
        return note('Global MightyModels hooks missing or a symlink', ok=False)
    try:
        owned = hooks_are_owned(hooks.read_text(encoding='utf-8'), hook_config(root))
    except _CONFIG_READ_ERRORS:
        owned = False
    message = (
        'Installed MightyModels hooks are owned; runtime trust not verified'
        if owned
        else 'Existing global hooks differ from managed MightyModels definitions'
    )
    return note(message, ok=owned)


def check_project_overlap(root: Path, cwd: Path) -> str | None:
    config = root / '.codex/config.toml'
    if not cwd.is_relative_to(root) or not config.is_file():
        return None
    try:
        project = tomllib.loads(config.read_text(encoding='utf-8'))
    except _CONFIG_READ_ERRORS:
        return '[WARN] Project-scoped Codex config missing or malformed'
    if 'mighty_mcp' not in project.get('mcp_servers', {}):
        return None
    return (
        '[WARN] MightyModels checkout also declares project-scoped mighty_mcp; '
        'verify CLI precedence and duplicate hook behavior'
    )


def diagnose(home: Path, root: Path, cwd: Path) -> tuple[list[str], bool]:
    """Return nonsecret status messages and whether required checks passed."""
    if not (root / 'bin/mightymodels-mcp-codex').is_file():
        return ['[FAIL] MightyModels MCP launcher missing from checkout'], False
    try:
        config = tomllib.loads((home / '.codex/config.toml').read_text(encoding='utf-8'))
    except _CONFIG_READ_ERRORS:
        return ['[FAIL] Global Codex config missing or malformed'], False

    reports = [
        check_mcp(config, root),
        check_agents(config, home, root),
        check_skills(home, root),
        check_hooks(home, root),
    ]
    warning = check_project_overlap(root, cwd)
    if warning is not None:
        reports.append(warning)
    reports.append('[WARN] Live hook delivery, scout isolation and model identity unverified')
    return reports, all(not item.startswith('[FAIL]') for item in reports)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    messages, valid = diagnose(
        args.home.expanduser().resolve(),
        args.root.expanduser().resolve(),
        Path.cwd().resolve(),
    )
    for message in messages:
        print(message)
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
