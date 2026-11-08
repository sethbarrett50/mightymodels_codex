"""Read-only Codex installation diagnostics without credential access or writes."""

import argparse
import json
import tomllib
from pathlib import Path
from shutil import which

from install_codex_user import AGENT_COUNT, SKILL_COUNT, hook_config, managed_hooks_present

_CONFIG_READ_ERRORS = (OSError, ValueError)


def note(message: str, *, ok: bool) -> str:
    return f'[{"OK" if ok else "FAIL"}] {message}'


def check_mcp(config: dict, root: Path) -> str:
    servers = config.get('mcp_servers')
    server = servers.get('mighty_mcp') if isinstance(servers, dict) else None
    server = server if isinstance(server, dict) else {}
    valid = (
        server.get('command') == 'sh'
        and server.get('args') == [str(root / 'bin/mightymodels-mcp-codex')]
        and server.get('enabled') is not False
    )
    message = (
        'Global MightyModels MCP launcher registered'
        if valid
        else 'Global MightyModels MCP registration missing or unexpected'
    )
    return note(message, ok=valid)


def check_runtime() -> str:
    """Diagnose the launcher dependency without invoking it or exposing paths."""
    available = which('uv') is not None
    return note(
        'uv executable available for MightyModels MCP launcher'
        if available
        else 'uv executable unavailable for MightyModels MCP launcher',
        ok=available,
    )


def check_agents(config: dict, home: Path, root: Path) -> str:
    agents = config.get('agents')
    agents = agents if isinstance(agents, dict) else {}
    codex = home / '.codex'
    valid = sum(
        bool(
            not (codex / 'agents' / f'{name}.toml').exists()
            and not (codex / 'agents' / f'{name}.toml').is_symlink()
            and isinstance(agents.get(name), dict)
            and agents[name].get('config_file') == str(source)
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
        owned = managed_hooks_present(hooks.read_text(encoding='utf-8'), hook_config(root))
    except _CONFIG_READ_ERRORS:
        owned = False
    message = (
        'Installed MightyModels hooks are recognized; runtime trust not verified'
        if owned
        else 'Expected MightyModels hook groups missing or different'
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
    servers = project.get('mcp_servers')
    if servers is None:
        return None  # This project intentionally relies on the global MCP registration.
    if not isinstance(servers, dict):
        return '[WARN] Project-scoped MCP config has unexpected shape'
    if 'mighty_mcp' not in servers:
        return None
    return (
        '[WARN] MightyModels checkout declares project-scoped mighty_mcp; '
        'verify CLI precedence and duplicate hook behavior'
    )


def check_project_mcp_overlap(config_path: Path) -> list[str]:
    """Read only a project MCP declaration; never print its values."""
    if config_path.is_symlink():
        return ['[WARN] Project Codex config is a symlink; scope not inspected']
    if not config_path.is_file():
        return []
    try:
        config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    except _CONFIG_READ_ERRORS:
        return ['[WARN] Active project Codex config malformed or unreadable']
    servers = config.get('mcp_servers')
    if isinstance(servers, dict) and 'mighty_mcp' in servers:
        return [
            (
                '[WARN] Active project and global scopes both declare mighty_mcp; '
                'trust, precedence and duplicate startup unverified'
            )
        ]
    return []


def check_project_hook_overlap(hook_path: Path) -> list[str]:
    """Report potential hook overlap without reading or printing credentials."""
    if hook_path.is_symlink():
        return ['[WARN] Active project hook file is a symlink; not inspected']
    if not hook_path.is_file():
        return []
    try:
        data = json.loads(hook_path.read_text(encoding='utf-8'))
    except _CONFIG_READ_ERRORS:
        return ['[WARN] Active project Codex hook manifest malformed']
    groups = data.get('hooks') if isinstance(data, dict) else None
    if not isinstance(groups, dict):
        return ['[WARN] Active project Codex hook manifest malformed']
    if groups:
        return [
            (
                '[WARN] Active project and global Codex hooks coexist; '
                'event precedence, trust and duplicate delivery unverified'
            )
        ]
    return []


def check_other_repo_overlap(root: Path, cwd: Path) -> list[str]:
    """Flag declarations in the active unrelated Git checkout, not host enforcement."""
    if cwd.is_relative_to(root):
        return []
    project = next(
        (path for path in (cwd, *cwd.parents) if (path / '.git').exists()),
        None,
    )
    if project is None:
        return []
    return [
        *check_project_mcp_overlap(project / '.codex/config.toml'),
        *check_project_hook_overlap(project / '.codex/hooks.json'),
    ]


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
        check_runtime(),
        check_agents(config, home, root),
        check_skills(home, root),
        check_hooks(home, root),
    ]
    warning = check_project_overlap(root, cwd)
    if warning is not None:
        reports.append(warning)
    if cwd.is_relative_to(root):
        # Our own checkout intentionally installs project hooks as well as
        # global lifecycle hooks; report coexistence without claiming delivery.
        reports.extend(check_project_hook_overlap(root / '.codex/hooks.json'))
    reports.extend(check_other_repo_overlap(root, cwd))
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
