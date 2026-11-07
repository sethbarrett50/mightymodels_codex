"""Read-only diagnostics for a user-scoped MightyModels Codex installation.

Usage: python3 scripts/codex_doctor.py [--home PATH] [--root PATH]
Does not spawn Codex, read credential stores, reveal tokens or change files.
"""

import argparse
import sys
import tomllib
from pathlib import Path

from install_codex_user import AGENT_COUNT, SKILL_COUNT, hook_config, hooks_are_owned


def diagnose(home: Path, root: Path, cwd: Path) -> tuple[list[str], bool]:
    """Return non-secret status messages and whether critical checks passed."""
    reports = []
    failed = False

    def note(level: str, message: str) -> None:
        nonlocal failed
        reports.append(f'[{level}] {message}')
        failed |= level == 'FAIL'

    if not (root / 'bin/mightymodels-mcp-codex').is_file():
        note('FAIL', 'MightyModels MCP launcher missing from checkout')
        return reports, False

    codex = home / '.codex'
    config_path = codex / 'config.toml'
    try:
        config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        note('FAIL', 'Global Codex config missing or malformed')
        return reports, False

    server = config.get('mcp_servers', {}).get('mighty_mcp', {})
    if server.get('command') == 'sh' and server.get('args') == [
        str(root / 'bin/mightymodels-mcp-codex')
    ]:
        note('OK', 'Global MightyModels MCP launcher registered')
    else:
        note('FAIL', 'Global MightyModels MCP registration missing or unexpected')

    agents = config.get('agents', {})
    valid_agents = sum(
        bool(
            (codex / 'agents' / f'{name}.toml').is_symlink()
            and (codex / 'agents' / f'{name}.toml').resolve(strict=False) == source.resolve()
            and agents.get(name, {}).get('config_file') == str(source)
        )
        for source in (root / '.codex/agents').glob('mm-*.toml')
        for name in (source.stem,)
    )
    note(
        'OK' if valid_agents == AGENT_COUNT else 'FAIL',
        f'Installed owned native agent registrations: {valid_agents}/{AGENT_COUNT}',
    )

    valid_skills = sum(
        bool(
            (home / '.agents/skills' / source.parent.name).is_symlink()
            and (home / '.agents/skills' / source.parent.name).resolve(strict=False)
            == source.parent.resolve()
        )
        for source in (root / '.codex/skills').glob('*/SKILL.md')
    )
    note(
        'OK' if valid_skills == SKILL_COUNT else 'FAIL',
        f'Installed owned Codex skill links: {valid_skills}/{SKILL_COUNT}',
    )

    hooks = codex / 'hooks.json'
    if hooks.is_file() and not hooks.is_symlink():
        if hooks_are_owned(hooks.read_text(encoding='utf-8'), hook_config(root)):
            note('OK', 'Installed MightyModels hooks are owned; runtime trust not verified')
        else:
            note('FAIL', 'Existing global hooks differ from managed MightyModels definitions')
    else:
        note('FAIL', 'Global MightyModels hooks missing or a symlink')

    project_conf = root / '.codex/config.toml'
    if cwd.is_relative_to(root) and project_conf.is_file():
        try:
            project = tomllib.loads(project_conf.read_text(encoding='utf-8'))
        except ValueError:
            note('WARN', 'Project-scoped Codex config is malformed')
        else:
            if 'mighty_mcp' in project.get('mcp_servers', {}):
                note(
                    'WARN',
                    'MightyModels checkout also declares project-scoped mighty_mcp; '
                    'verify CLI precedence and duplicate hook behavior',
                )

    note('WARN', 'Live hook delivery, scout sandbox isolation and model identity are unverified')
    return reports, not failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    home = args.home.expanduser().resolve()
    root = args.root.expanduser().resolve()
    messages, valid = diagnose(home, root, Path.cwd().resolve())
    for message in messages:
        print(message)
    return 0 if valid else 1


if __name__ == '__main__':
    sys.exit(main())
