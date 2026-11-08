"""Synchronize native Codex agent roles with upstream MightyModels Markdown agents.

Usage: python scripts/sync_codex_agents.py [--check]
This parser deliberately handles only fields needed from the current repository;
it refuses unfamiliar frontmatter shapes rather than guessing YAML semantics.
"""

import argparse
import json
import re
import tomllib
from pathlib import Path

SOURCE = re.compile(r'\A---\r?\n([\s\S]*?)\r?\n---\r?\n')
EXPECTED_AGENTS = 12

# Codex equivalents of the original Claude economy tiers. Fable is intentionally disabled.
MODEL_TIERS = {
    'haiku': ('gpt-6-luna', 'medium'),
    'sonnet': ('gpt-6.1-sol', 'medium'),
    'opus': ('gpt-6.1-sol', 'high'),
}

DESCRIPTION = re.compile(r'^description:\s*>-\s*\n((?:[ \t]+[^\n]*\n?)*)', re.MULTILINE)


def field(frontmatter: str, key: str) -> str | None:
    match = re.search(rf'^{re.escape(key)}:\s*(.*)$', frontmatter, re.MULTILINE)
    return match.group(1).strip() if match is not None else None


# Translate tool-specific source instructions only in generated Codex agent copies.
# Order compound aliases before single names to avoid double replacement.
ROLE_TRANSLATIONS = (
    ('`Read`, `Grep`, `Glob`', '`exec_command` (file reads, `rg`, `rg --files`)'),
    ('`Read`, `Grep`', '`exec_command` (file reads and `rg`)'),
    ('`Grep`, `Glob`', '`exec_command` (`rg` and `rg --files`)'),
    ('`Edit`, `Write`', '`apply_patch`'),
    ('`Read`', '`exec_command` (read-only file inspection)'),
    ('`Grep`', '`exec_command` with `rg`'),
    ('`Glob`', '`exec_command` with `rg --files`'),
    ('`Edit`', '`apply_patch`'),
    ('`Write`', '`apply_patch`'),
    ('`Bash`', '`exec_command`'),
    ('`Agent`', '`spawn_agent`'),
    ('`code-scout`', '`mm-triage-code-scout`'),
    ('`web-scout`', '`mm-triage-web-scout`'),
    ('`qualitylens`', '`mm-review-qualitylens`'),
    (
        'preloaded `prompting-subagents` skill',
        'installed `$prompting-subagents` skill (read its SKILL.md explicitly)',
    ),
    (
        'preloaded `becoming-merge-vader` skill',
        'installed `$becoming-merge-vader` skill (read its SKILL.md explicitly)',
    ),
    (
        'preloaded `becoming-uncle-bob` skill',
        'installed `$becoming-uncle-bob` skill (read its SKILL.md explicitly)',
    ),
    (
        (
            'Its text is in your context from the start, under a line that reads '
            '"Base directory for this skill:" and gives the skill\'s absolute path;'
        ),
        'Read the skill from $HOME/.agents/skills/ before continuing;',
    ),
)


def native_web_scout_tools(body: str) -> str:
    """Replace unsupported Claude web-tool names without inventing Codex APIs."""
    if body.count('WebSearch') < 2 or body.count('WebFetch') < 2:
        msg = 'Missing expected upstream web-scout tool references'
        raise ValueError(msg)
    body = body.replace('WebSearch', 'host-provided web search')
    body = body.replace('WebFetch', 'host-provided web fetch')
    guidance = (
        'Codex web-tool availability is session- and agent-dependent. Inspect '
        'the tools actually exposed to this agent before searching or fetching; '
        'never treat the capability labels below as literal tool names. If '
        'search or fetch is unavailable, return UNKNOWN-BLOCKED and specify '
        'which capability is missing. Do not use a shell or alternate agent '
        'to bypass the original read-only public-documentation scope.\\n\\n'
    )
    return guidance + body


def native_body(source: str, *, role: str | None = None) -> str:
    """Translate supported Claude tool references; never infer host enforcement."""
    for original, native in ROLE_TRANSLATIONS:
        source = source.replace(original, native)
    if role == 'mm-triage-web-scout':
        source = native_web_scout_tools(source)
    return source


def generate(root: Path) -> dict[str, str]:  # noqa: PLR0914, PLR0915
    result = {}
    report = []
    sources = sorted((root / 'agents').glob('*/*.md'))
    if len(sources) != EXPECTED_AGENTS:
        msg = f'Expected 12 MightyModels agents; got {len(sources)}'
        raise ValueError(msg)
    for source in sources:
        raw = source.read_text(encoding='utf-8')
        match = SOURCE.match(raw)
        if match is None:
            msg = f'Unrecognized frontmatter: {source}'
            raise ValueError(msg)
        front = match.group(1)
        relative = source.relative_to(root).as_posix()
        name = field(front, 'name')
        description_match = DESCRIPTION.search(front)
        if name is None or description_match is None:
            msg = f'Missing name or folded description: {source}'
            raise ValueError(msg)
        description = ' '.join(description_match.group(1).split())
        effort = field(front, 'effort')
        source_model = field(front, 'model')
        role = f'mm-{source.parent.name}-{name}'
        if source_model == 'fable':
            report.append({
                'source': relative,
                'role': role,
                'source_model': source_model,
                'source_effort': effort,
                'codex_status': 'disabled: no Fable substitution',
                'unmapped': [],
            })
            continue
        if source_model not in MODEL_TIERS:
            msg = f'Unsupported source model {source_model!r}: {source}'
            raise ValueError(msg)
        model, routed_effort = MODEL_TIERS[source_model]
        notes = (
            f'Ported from {relative}.\n'
            'IMPORTANT: Claude-specific tool allowlists, skill preloads, '
            'and agent dispatch identifiers are NOT automatically enforced by Codex. '
            'Load required skills explicitly from $HOME/.agents/skills and use native '
            'Codex role names (mm-triage-code-scout, mm-triage-web-scout, '
            'mm-review-qualitylens). Consult docs/CODEX.md. '
            'Do not execute write-capable workflows until '
            'their MCP and safety controls are validated.\n\n'
        )

        def encoded(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)

        lines = [f'name = {encoded(role)}', f'description = {encoded(description)}']
        lines.append(f'model = {encoded(model)}')
        lines.append(f'model_reasoning_effort = {encoded(routed_effort)}')
        lines.append(f'developer_instructions = {encoded(notes + native_body(raw[match.end() :], role=role))}')
        target = (root / '.codex/agents' / f'{role}.toml').relative_to(root).as_posix()
        result[target] = '\n'.join(lines) + '\n'
        unmapped = [
            key
            for key in (
                'tools',
                'skills',
                'maxTurns',
                'permissionMode',
                'disallowedTools',
                'mcpServers',
                'hooks',
                'memory',
            )
            if re.search(rf'^{key}:', front, re.MULTILINE)
        ]
        report.append({
            'source': relative,
            'role': role,
            'source_model': source_model,
            'source_effort': effort,
            'codex_model': model,
            'codex_effort': routed_effort,
            'unmapped': unmapped,
        })
    result['.codex/compatibility-report.json'] = (
        json.dumps(
            {
                'status': 'experimental: generation only, not runtime-verified',
                'count': len(report),
                'agents': report,
            },
            indent=2,
            ensure_ascii=False,
        )
        + '\n'
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    files = generate(root)
    stale = []
    for name, content in files.items():
        path = root / name
        if path.suffix == '.toml':
            tomllib.loads(content)
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                stale.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
    if stale:
        parser.error('Stale generated roles: ' + ', '.join(stale))
    print(f'Codex roles {"checked" if args.check else "updated"}: {len(files) - 1}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
