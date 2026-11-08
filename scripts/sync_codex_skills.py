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


def native_dispatch_steps(body: str) -> str:
    """Replace Claude-only dispatch steps with Codex role and model semantics."""
    model_step = (
        "2. **Resolve the native role and model.** Read the active ticket's "
        "`subagent-models` block, then consult the generated role's TOML under "
        '`$HOME/.codex/agents/mm-<group>-<worker>.toml`. Use the exact registered '
        'role name and its configured model and reasoning effort; do not pass a Claude '
        'alias (haiku, sonnet, opus or fable) as a `spawn_agent` model argument. '
        'The original ticket aliases and native model pins are not proof of effective '
        'runtime identity. Wingman/Fable is disabled; ask the user rather than '
        'substituting another model. Record any requested routing change as an '
        'explicit decision before dispatch.'
    )
    dispatch_step = (
        '5. **Dispatch with native Codex tools.** Use `spawn_agent` with '
        '`agent_type` set to the full registered `mm-<group>-<worker>` role '
        '(for example `mm-workers-engineer` or `mm-triage-code-scout`), '
        "not Claude's `mightymodels:FOLDER:WORKER` identifier or "
        '`subagent_type`. Supply the completed packet as the message. '
        'Do not supply a Claude model alias as an override. For follow-ups, use '
        'the native send-input operation with the returned agent ID when the '
        'host exposes it; otherwise report that continuation is unavailable. '
        'Never claim native permission checks fired merely because the agent '
        'was registered or spawned.'
    )
    replacements = (
        (r'(?ms)^2\. \*\*Resolve the model\.\*\*.*?(?=^3\. \*\*)', model_step + '\n\n'),
        (r'(?ms)^5\. \*\*Dispatch\*\*.*?(?=^6\. \*\*)', dispatch_step + '\n\n'),
    )
    for pattern, replacement in replacements:
        body, count = re.subn(pattern, replacement, body)
        if count != 1:
            msg = 'Expected exactly one Claude dispatch step to translate'
            raise ValueError(msg)
    return body


def native_open_ticket_decisions(body: str) -> str:
    """Make user decisions explicit chat gates, not fictitious host dialogs."""
    steps = (
        (
            (
                'One `Codex user decision gate` dialog containing only the '
                'questions the conversation has not already\nanswered. Each\nquestion '
                'carries two to four options, and the user can always type an '
                'answer of their own.'
            ),
            (
                'In Codex Default mode, ask only unanswered interview questions in '
                'ordinary chat and end the\nturn until the user explicitly responds. '
                'Offer two to four choices per question and accept\nfree-text '
                'answers; no timeout, empty response or auto-resolution counts as a '
                'decision.'
            ),
        ),
        (
            (
                'An answer starting `needs input` means no one could be asked '
                'through the tool: put each question\nit names to the user in one '
                '`Codex user decision gate` dialog, then call again with those '
                'arguments'
            ),
            (
                'An answer starting `needs input` means the MCP tool could not '
                'collect required inputs.\nAsk each named question in ordinary chat '
                'and end the turn until the user explicitly\nanswers; then call '
                '`ticket_write` again using those actual answers'
            ),
        ),
        (
            'Ask once, through `Codex user decision gate`:',
            ('Ask once in ordinary chat, then end the turn until the user explicitly chooses:'),
        ),
    )
    for old, new in steps:
        if body.count(old) != 1:
            msg = 'Expected exactly one open-ticket decision instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body


def native_baton_pass_frontmatter(front: str) -> str:
    """Summarize blocking Codex chat choices without inventing a dialog UI."""
    old = (
        'asks in one\n  Codex user decision gate call what the next session should '
        'focus on and what to do with uncommitted\n  work, then writes'
    )
    new = (
        'asks in ordinary chat what the next session should focus on and what to '
        'do with uncommitted\n  work, awaits explicit user answers, then writes'
    )
    if front.count(old) != 1:
        msg = 'Expected exactly one baton-pass frontmatter decision clause'
        raise ValueError(msg)
    return front.replace(old, new)


def native_baton_pass_decisions(body: str) -> str:
    """Do not claim unobserved Codex recorder delivery during handoff."""
    changes = (
        (
            (
                'One `Codex user decision gate` call, two questions, options drawn '
                'from the state rather than generic:'
            ),
            (
                'Ask the user in ordinary chat for the next-session focus and, only '
                'if the tree is dirty,\nfor the uncommitted-work action. Offer '
                'options supported by the current state and\nend the turn until the '
                'user explicitly answers each required question; do not assume\na '
                'popup timeout or empty response is consent.'
            ),
        ),
        (
            (
                'Write no decision entry by hand. The recorder hook on `Codex user '
                'decision gate` already stored every\nanswer the user gave in a '
                'dialog, including the two just given, but only if the session '
                'was\npointed at a ledger or ticket when it was given; the snapshot '
                'carries those to the next session.\nIn a session with no ticket and '
                'no pointer it stored nothing, so those decisions go in\nBATON.md. A '
                'choice\nthe user made only in chat has no writer: if it matters to '
                'the next session, put it to them\nthrough `Codex user decision '
                'gate` now, so the recorder takes it. One only in the baton is one '
                'more line\nto drift.'
            ),
            (
                'Do not assume a Codex user-input recorder hook executed. Preserve '
                "only the user's actual\nconfirmed focus and uncommitted-work choice "
                'in BATON.md, not a predicted or default answer.\nIf an active '
                'ticket exists, also update its durable context through available '
                'MightyModels\nstate tools before the final snapshot, and verify the '
                'state write succeeded. If the state\nwriter is unavailable or '
                'fails, say so explicitly and do not claim a persisted handoff.\nDo '
                'not store credentials or raw private responses in the baton. A '
                'missing user answer is\nstill pending and must not be converted '
                'into approval.'
            ),
        ),
    )
    for old, new in changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one baton-pass decision instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body


def native_game_plan_decisions(body: str) -> str:
    """Use actual Codex chat rather than a nonexistent question dialog."""
    changes = (
        (
            (
                'One `Codex user decision gate` dialog, risks batched up to four a call, '
                'each offering the same'
            ),
            'Ask in ordinary chat, at most four risks per turn, each offering the same',
        ),
        (
            'One `Codex user decision gate` dialog with one question, the',
            'Ask one blocking question in ordinary chat and wait for a real answer, the',
        ),
        (
            'ask through\n`Codex user decision gate`: approve, revise, or abandon.',
            'ask in ordinary chat and stop for an explicit choice: approve, revise, or abandon.',
        ),
    )
    for old, new in changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one game-plan user decision instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body


def native_review_routing(front: str, body: str) -> tuple[str, str]:
    """Remove Claude reviewer model and preload claims from Codex output."""
    front_old = (
        'One\n  Codex user decision gate gate sets depth (quick runs its reviewers on '
        'sonnet, standard and deep on opus), persona\n  emphasis, and scope;'
    )
    front_new = (
        'An ordinary-chat decision sets review depth (quick, standard, deep), persona\n'
        '  emphasis, and scope without changing native reviewer model pins;'
    )
    front_gate = 'presented by id through Codex user decision gate'
    native_gate = 'presented by id for explicit ordinary-chat decisions'
    body_changes = (
        (
            ('quick is one persona on sonnet, standard and deep run their reviewers on opus.'),
            (
                'quick runs one persona, while standard and deep change review '
                'coverage; all native Codex reviewers use their registered Sol '
                'model settings (Claude aliases in profiles.md are not Codex pins).'
            ),
        ),
        (
            (
                'Each persona preloads its doctrine as a skill of its own\n'
                '(`becoming-merge-vader`, `becoming-uncle-bob`) and is passed '
                'no doctrine path.'
            ),
            (
                'Each persona must explicitly read its installed doctrine skill\n'
                '(`becoming-merge-vader` or `becoming-uncle-bob`) through '
                '`$HOME/.agents/skills/` before reviewing; native Codex dispatch '
                'does not guarantee automatic preloads.'
            ),
        ),
    )
    if front.count(front_old) != 1:
        msg = 'Expected exactly one review routing frontmatter clause'
        raise ValueError(msg)
    front = front.replace(front_old, front_new)
    if front.count(front_gate) != 1:
        msg = 'Expected exactly one review findings decision clause'
        raise ValueError(msg)
    front = front.replace(front_gate, native_gate)
    for old, new in body_changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one review routing body clause'
            raise ValueError(msg)
        body = body.replace(old, new)
    return front, body


def native_review_circus_decisions(body: str) -> str:
    """Translate unsupported reviewer overrides and user dialogs for Codex."""
    changes = (
        (
            (
                'An answer starting `needs input` means no one could be asked '
                'through the tool: put each question\nit names to the user in one '
                '`Codex user decision gate` dialog, then call again with those '
                'arguments. A refusal\nnaming a missing argument means: ask the '
                'user for it, then call again.'
            ),
            (
                'When `review_start` returns `needs input` or a missing-argument '
                'refusal,\nask for each required choice in ordinary chat and end '
                'the turn until the user\nexplicitly answers. Then call again with '
                'only those actual answers; do not\nassume that a nonexistent '
                'popup or a timeout supplied them.'
            ),
        ),
        (
            (
                'A run may spend one override on its heavier-weighted reviewer '
                '(the first persona, merge-vader, on equal weights), moving it to '
                'fable. Ask for it only when the user wants the strongest '
                'reviewer, with `review_override`:\n\n```json\n{"run_id": '
                '"20261005-103000"}\n```\n\nThe answer names the reviewer and says '
                "to dispatch it with effort high. A ticket's reviewer keys change "
                'no review.'
            ),
            (
                'Codex disables the Fable review override. Never call '
                '`review_override`\nor claim it changed the model. Both registered '
                'reviewer roles use their\nnative Sol model settings; review depth '
                'changes review scope, not model.\nIf the user requests an '
                'unavailable reviewer upgrade, disclose that\nlimitation and ask '
                'how to proceed instead of silently substituting a model.'
            ),
        ),
        (
            (
                'The answer says which findings are still undecided. An answer '
                'starting `needs input` means no one\ncould be asked through the '
                'tool: put the question it names to the user in one `Codex user '
                'decision gate`\ndialog, then call again with `decisions` (several '
                'findings may go in one call):'
            ),
            (
                'The answer identifies findings still undecided. For `needs '
                'input`,\nask the user about those finding IDs in ordinary chat '
                'and stop for their\nexplicit choices. Call again with `decisions` '
                'containing only confirmed\nanswers (multiple findings may be '
                'included together):'
            ),
        ),
    )
    for old, new in changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one review-circus decision instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body


def native_assembly_roles(body: str) -> str:
    """Generate registered Codex role and explicit escalation instructions."""
    changes = (
        (
            (
                "The engineer's model is `sonnet`, as ticket.yml repeats; "
                'bump it one tier for a genuinely gnarly task, with the '
                'reason logged in the stanza.'
            ),
            (
                'Use the registered `mm-workers-engineer` native role model '
                "and reasoning effort. The ticket's Claude alias is historical; "
                'it must not override the Codex model. Request an explicit '
                'user decision before changing native routing, and do not '
                'claim the configured model proves effective runtime identity.'
            ),
        ),
        (
            (
                'Then dispatch `mightymodels:workers:engineer` through the '
                "`spawn_agent` tool, using the engineer's configured native Codex "
                'role and model; do not pass Claude aliases.'
            ),
            (
                'Then use `spawn_agent` with `agent_type=mm-workers-engineer` and '
                'the engineer packet, using its native role model without a Claude '
                'alias override.'
            ),
        ),
        (
            (
                'and dispatched as `mightymodels:workers:intern` on `haiku`, with '
                "prompting-subagents' intern template."
            ),
            (
                'and dispatched with native `spawn_agent` role `mm-workers-intern`, '
                'using its native model and prompting-subagents intern template.'
            ),
        ),
        (
            (
                'Dispatch `mightymodels:review:fact-checker` on `haiku`, with '
                "prompting-subagents' fact-checker template:"
            ),
            (
                'Dispatch native `spawn_agent` role `mm-review-fact-checker` using '
                'its configured model and the prompting-subagents fact-checker '
                'template:'
            ),
        ),
        (
            (
                'Off → one `Codex user decision gate` dialog giving the task, its '
                'status and the reasons verbatim, with two answers:'
            ),
            (
                'Off → ask the user in ordinary chat, then stop until explicitly '
                'answered. Give the task, status, reasons verbatim, and these two '
                'choices:'
            ),
        ),
    )
    for old, new in changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one assembly dispatch or decision instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body


def native_landing_decisions(body: str) -> str:
    """Wait for a real review-or-handoff choice after green CI."""
    before = (
        'ask once through `Codex user decision gate` '
        '(up to four questions a call, two to four options each):'
    )
    after = (
        'ask in ordinary chat whether to review now or hand off, then end '
        'the turn until the user explicitly chooses. Neither a timeout '
        'nor an automatic response is consent:'
    )
    if body.count(before) != 1:
        msg = 'Expected exactly one landing decision instruction'
        raise ValueError(msg)
    body = body.replace(before, after)
    alias_step = (
        'Dispatch workers through prompting-subagents. Models are the fixed '
        'aliases `subagent-models`\nlists, never memory.'
    )
    native_step = (
        'Dispatch through prompting-subagents using the registered native Codex '
        'roles and each role TOML model/effort settings. The ticket\n'
        '`subagent-models` aliases are Claude-only historical values, not '
        'dispatch arguments or proof of the effective host model.'
    )
    if body.count(alias_step) != 1:
        msg = 'Expected exactly one landing model routing instruction'
        raise ValueError(msg)
    return body.replace(alias_step, native_step)


def native_landing_frontmatter(front: str) -> str:
    """Describe the same blocking user choice in the generated skill summary."""
    old = (
        'On green, ask through Codex user decision gate whether to review now '
        '(review-circus) or hand off (baton-pass).'
    )
    new = (
        'On green, ask in ordinary chat whether to review now (review-circus) '
        'or hand off (baton-pass), then wait for an explicit answer.'
    )
    if front.count(old) != 1:
        msg = 'Expected exactly one landing frontmatter decision instruction'
        raise ValueError(msg)
    return front.replace(old, new)


def native_task_split_frontmatter(front: str) -> str:
    """Avoid describing an unavailable dialog in Codex skill metadata."""
    old = 'Ends in one Codex user decision gate dialog showing every piece'
    new = 'Ends by asking in ordinary chat and awaiting explicit approval for every piece'
    if front.count(old) != 1:
        msg = 'Expected exactly one task split frontmatter dialog'
        raise ValueError(msg)
    return front.replace(old, new)


def native_task_split_decisions(body: str) -> str:
    """Ask for split approval in ordinary chat and preserve actual choices."""
    changes = (
        (
            'Until the dialog in step 4 is answered this skill',
            'Until the user explicitly answers the blocking question in step 4 this skill',
        ),
        (
            (
                'A dialog that timed out, was\ndismissed or came back empty is not '
                'an answer: open it again. Do not decide for the user, do not\nask '
                'in prose instead, and do not start on a piece while you wait.'
            ),
            (
                'A timeout, cancellation, dismissal or empty reply is not an answer: '
                'ask again in\nordinary chat. Do not decide for the user or start '
                'a piece while awaiting approval.'
            ),
        ),
        (
            'then open one\n`Codex user decision gate` dialog about them.',
            (
                'then ask in ordinary chat whether to split, keep, or revise. '
                'End the turn until the user explicitly responds.'
            ),
        ),
        (
            'The dialog has one question with these options:',
            'Ask one blocking question with these options:',
        ),
        (
            "through the dialog's free text.",
            'using an explicit free-text response in chat.',
        ),
        (
            'as the dialog listed.',
            'as the user explicitly approved.',
        ),
    )
    for old, new in changes:
        if body.count(old) != 1:
            msg = 'Expected exactly one task split approval instruction'
            raise ValueError(msg)
        body = body.replace(old, new)
    return body



SOURCE_COMPANION_SKILLS = frozenset(('prompting-subagents', 'baton-pass'))


def native_companion_guidance(name: str) -> str:
    """Resolve Claude-source reference files from the installed Codex skill link."""
    if name not in SOURCE_COMPANION_SKILLS:
        return ''
    return (
        '> **Codex companion paths:** This generated SKILL.md lives under '
        '`.codex/skills/` but the original `references/`, `scripts/`, and '
        '`assets/` may live only under the source `skills/` tree. '
        'For a relative companion path in this skill, resolve the MightyModels '
        'source checkout with '
        '`git -C "$(realpath "$HOME/.agents/skills/' + name + '")" rev-parse --show-toplevel`, '
        'then read `skills/' + name + '/<relative companion path>` from that root. '
        'Do not look for those files in the unrelated target repository, and '
        'never proceed by inventing a missing template.\n\n'
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
    front = native_baton_pass_frontmatter(front) if name == 'baton-pass' else front
    front = native_landing_frontmatter(front) if name == 'stick-the-landing' else front
    front = native_task_split_frontmatter(front) if name == 'break-it-down' else front
    transformers = {
        'prompting-subagents': native_dispatch_steps,
        'open-ticket': native_open_ticket_decisions,
        'baton-pass': native_baton_pass_decisions,
        'game-plan': native_game_plan_decisions,
        'review-circus': native_review_circus_decisions,
        'agents-assemble': native_assembly_roles,
        'stick-the-landing': native_landing_decisions,
        'break-it-down': native_task_split_decisions,
    }
    if name == 'review-circus':
        front, body = native_review_routing(front, body)
    transformer = transformers.get(name)
    if transformer is not None:
        body = transformer(body)
    return f'---\n{front}\n---\n\n{BANNER}\n\n{native_companion_guidance(name)}{body}'


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
