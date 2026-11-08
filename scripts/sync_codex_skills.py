"""Generate Codex-specific SKILL.md files without changing Claude source skills.

Usage: python scripts/sync_codex_skills.py [--check]

Codex uses the generated copies. Source SKILL.md and companion files stay
unchanged for Claude. No external tools or network access are needed.
"""

import argparse
import re
from pathlib import Path

FRONT = re.compile(r'\A---\n([\s\S]*?)\n---\n')
ALLOWLIST = re.compile(r'(?m)^allowed-tools:\n(?:  - [^\n]*\n)*')
LEGACY_ADAPTER = re.compile(
    r'(?m)^> \*\*Codex runtime adapter \(MightyModels fork\):\*\*[^\n]*\n\n'
)
MCP_PREFIX = 'mcp__plugin_mightymodels_mighty-mcp__'
CODEX_PREFIX = 'mcp__mighty_mcp__'
EXPECTED_SKILLS = 19
BANNER = (
    '> **Native Codex workflow (generated):** This file is generated from the '
    'Claude skill; do not edit it directly. MCP calls must use actual '
    '`mighty_mcp` tools exposed by the current Codex session. '
    'Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage '
    'APIs or inherit model aliases. A required decision in Default mode uses '
    'ordinary chat and stops until a real answer; auto-resolution never grants '
    'permission. `USER_REQUEST_ARGS` denotes the user-provided invocation '
    'text, not a shell variable. Helper paths resolve through the installed '
    '`$HOME/.agents/skills/` links; if these links are missing, stop rather '
    'than guessing a file location.'
)


def translated(source: Path) -> str:
    """Preserve skill semantics while rewriting host-specific transport syntax."""
    raw = source.read_text(encoding='utf-8')
    match = FRONT.match(raw)
    if match is None:
        msg = f'Missing frontmatter: {source}'
        raise ValueError(msg)
    front = ALLOWLIST.sub('', match.group(1) + '\n').rstrip('\n')
    body = LEGACY_ADAPTER.sub('', raw[match.end() :])
    name = source.parent.name
    changes = {
        MCP_PREFIX: CODEX_PREFIX,
        '${CLAUDE_PLUGIN_ROOT}/skills/': '$HOME/.agents/skills/',
        '${CLAUDE_SKILL_DIR}': f'$HOME/.agents/skills/{name}',
        '$ARGUMENTS': 'USER_REQUEST_ARGS',
        '`AskUserQuestion`': '`Codex user decision gate`',
        '`SendMessage`': '`native agent follow-up`',
        '`Agent`': '`spawn_agent`',
        'AskUserQuestion': 'Codex user decision gate',
        ('Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` in this file as\nan absolute path:'): (
            'Codex resolves MightyModels helpers through installed `$HOME/.agents/skills/` links:'
        ),
        (
            'which\nClaude Code substitutes in this file as an absolute path.'
        ): 'which resolves through the installed Codex skill directory.',
        'Models are the fixed aliases `subagent-models` lists, never memory.': (
            "Use the native Codex role's configured model; never pass Claude model aliases."
        ),
        ("its `model` the engineer's fixed alias, `sonnet`, which `subagent-models` repeats."): (
            "using the engineer's configured native Codex role and model; "
            'do not pass Claude aliases.'
        ),
        'Claude Codex user decision gate recorder does not run in Codex': (
            'legacy Claude question recorder does not run in Codex'
        ),
    }
    for previous, replacement in changes.items():
        front = front.replace(previous, replacement)
        body = body.replace(previous, replacement)
    return f'---\n{front}\n---\n\n{BANNER}\n\n{body}'


def generate(root: Path) -> dict[str, str]:
    sources = sorted((root / 'skills').glob('*/SKILL.md'))
    if len(sources) != EXPECTED_SKILLS:
        msg = f'Expected {EXPECTED_SKILLS} source skills, found {len(sources)}'
        raise ValueError(msg)
    result = {}
    for source in sources:
        name = source.parent.name
        key = f'.codex/skills/{name}/SKILL.md'
        result[key] = translated(source)
    return result



def sync_open_ticket_companions(root: Path, *, check: bool) -> list[str]:
    """Keep generated skill companion links pointed at canonical Claude assets."""
    stale = []
    for name in ('assets', 'references', 'scripts'):
        source = root / 'skills/open-ticket' / name
        destination = root / '.codex/skills/open-ticket' / name
        if not source.is_dir():
            msg = f'Missing source skill companion: {source}'
            raise ValueError(msg)
        if destination.is_symlink() and destination.resolve() == source.resolve():
            continue
        if check:
            stale.append(destination.relative_to(root).as_posix())
        elif destination.exists() or destination.is_symlink():
            msg = f'Refusing unmanaged Codex companion: {destination}'
            raise ValueError(msg)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(source, target_is_directory=True)
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    stale = []
    for name, content in generate(root).items():
        path = root / name
        if args.check:
            if not path.is_file() or path.read_text(encoding='utf-8') != content:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    stale.extend(sync_open_ticket_companions(root, check=args.check))
    if stale:
        parser.error('Stale generated Codex skills: ' + ', '.join(stale))
    print(f'Codex skills {"checked" if args.check else "updated"}: 19')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
