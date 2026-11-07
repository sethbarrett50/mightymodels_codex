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
            'Consult docs/CODEX.md. Do not execute write-capable workflows until '
            'their MCP and safety controls are validated.\n\n'
        )

        def encoded(value: str) -> str:
            return json.dumps(value, ensure_ascii=False)

        lines = [f'name = {encoded(role)}', f'description = {encoded(description)}']
        lines.append(f'model = {encoded(model)}')
        lines.append(f'model_reasoning_effort = {encoded(routed_effort)}')
        lines.append(f'developer_instructions = {encoded(notes + raw[match.end() :])}')
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
