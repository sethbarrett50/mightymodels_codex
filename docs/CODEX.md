# MightyModels Codex port — status and installation

The port provides native Codex definitions for **11 enabled agents** (from 12 Claude source roles; Fable/wingman is disabled), **19 skills**, and a
local **35-tool MCP server**. Claude support is retained. It is **experimental**:
static tests and one live read-only subagent test do not establish complete
dispatch authorization or end-to-end workflow equivalence.

## Observed live results — Debian 13, Codex CLI 0.167.0 (November 2026)

**Historical observations, not current end-to-end acceptance.** Static checks and CLI discovery do not demonstrate host-enforced dispatch denial, read-only scout isolation, actual spawned-agent model identity, decision persistence, or complete lifecycle behavior. Track these separately under issues [#9](https://github.com/sethbarrett50/mightymodels_codex/issues/9), [#8](https://github.com/sethbarrett50/mightymodels_codex/issues/8), [#14](https://github.com/sethbarrett50/mightymodels_codex/issues/14) and [#16](https://github.com/sethbarrett50/mightymodels_codex/issues/16).

The separate, unprivileged `codex` user on Debian 13 successfully:

- Installed uv 0.13.7 with Python 3.14 and cloned this repository.
- Passed the generator check in an earlier state (12 Claude sources; currently 11 enabled Codex roles and 19 skills).
- Discovered 12 roles and 19 skills in an earlier session **before Fable/wingman was disabled**; the current 11-role registry has not been host-verified.
- Connected to `mighty_mcp`; 35 tools were listed. A real
  `investigation_list({})` request reached the server, but state reads returned
  "no repository is recorded" because no write unit of work had registered it.
- Ran the native `mm-triage-code-scout` agent to inspect MCP registration code;
  the agent finished and reported the nine registrars.
- Created `~/.local/share/mightymodels/state.db` and an MCP log.
- **Did not establish** that `PreToolUse` blocked unauthorized dispatch or that
  `SubagentStop` persisted the scout report. No implementation workflow ran.

The scout's `/root/...` agent identifier is a coordinator hierarchy identifier;
the OS account was verified as UID 1002 (`codex`), not Linux root.

## Source, enabled and reported roles

The source tree includes 12 original Claude roles. The native Codex generator emits 11 enabled roles and deliberately omits Fable/wingman. `.codex/compatibility-report.json` counts the **12 source roles**, including the disabled one: its `count` is not the enabled-install count. All 19 skills have Codex-specific generated equivalents. Run `python3 scripts/sync_codex_agents.py --check` and `python3 scripts/sync_codex_skills.py --check` for generation drift; these checks are not live host acceptance.

## User-scoped installation across repositories

Run this as the unprivileged Linux user that will launch Codex. Do not use sudo
or place GitHub PATs inside the MightyModels checkout.

```sh
cd ~/code/mightymodels_codex
uv sync --locked --no-dev
python3 scripts/install_codex_user.py
codex mcp list
```

The installer symlinks the 11 enabled native roles into `~/.codex/agents/` and 19
skills into `~/.agents/skills/`, adds a clearly marked `mighty_mcp` section
to `~/.codex/config.toml`, installs absolute-path hooks at
`~/.codex/hooks.json`, and adds a managed instruction stanza in
`~/.codex/AGENTS.md`. It refuses to overwrite unrelated files and does not
modify sandbox, approval, model, or network settings. It can be rerun.

```sh
python3 scripts/install_codex_user.py --uninstall
```

Uninstall removes only owned links and managed stanzas. It preserves Codex
authentication, unrelated configuration, all user repositories, PAT files, and
the MightyModels state database. Keep this checkout at its installed location;
reinstall after moving it. Restart Codex after installing or uninstalling.

**Caution:** Codex may require explicit trust for newly installed hooks; hooks
being present on disk is not evidence they executed. An unrelated preexisting
`~/.codex/hooks.json` causes the installer to stop rather than overwrite it.
Merge hook definitions manually in that case.

### Per-repository workflow

```sh
cd ~/kc/YOUR_REPO
codex mcp list
codex
```

In the interactive session, ask Codex to list the *registered* `mighty_mcp`
ticket/task tools and delegate a **read-only** scout. Compare with the actual
tools and agent event trace, not just configuration files.

The MCP launcher now keeps the target repository working directory while
loading the MightyModels Python package from this checkout. Repository state is
distinct from the plugin source tree. If the host starts MCP from a different
directory, confirm its reported repository identity before writing state.

## Source checkout mode

From the repository root, install Python >=3.14 and uv, run
`uv sync --locked --no-dev`, then start `codex`. The checkout includes its
own `.codex/config.toml`, local agent definitions and skill links. Do not
run a second duplicate MCP server unintentionally when user-level installation
is active; prefer the user-scoped setup when working across repos.

## Adaptation and safety limitations

- Original Claude definitions live in `agents/**/*.md`. Generated TOML files
  set names, instructions and reasoning effort, but do **not** enforce Claude
  model aliases, `maxTurns`, tool restrictions or automatic skill preloads.
- Codex native delegation replaces Claude's Agent / SendMessage tool names.
  Resolve MCP calls to exposed `mighty_mcp` tools. Never guess tool names.
- Read-only instructions are **not a filesystem sandbox**. Parent permissions
  apply to children.
- The hook adapter converts Codex spawn events into the original admission hook,
  but disabled, untrusted or differently-shaped hooks may bypass the guardrail.
  Verify actual blocked dispatches before write-capable use.
- SubagentStop and PreCompact adapters are implemented; SessionStart and
  PostToolUse state-pointer handling remains unmigrated.

## Remaining live acceptance tests

1. In an unrelated scratch repo, confirm all global agents, skills and MCP
   tools appear, and a read-only scout completes.
2. Verify a missing/invalid started task causes a **real host-level denial** of
   `mm-workers-engineer` delegation. Do not substitute a prompt-only refusal.
3. Verify a valid scoped engineer task, owned-file check, independent
   fact-checker, persisted verdict and three-failed-fix ceiling.
4. Verify scout write prevention using actual sandbox permissions.
5. Verify SubagentStop evidence, compaction, resume, session state and user
   approvals, then test installed-plugin mode separately.
6. Validate GitHub/Jira writes through properly scoped approved tooling.

The project is not production-ready until these acceptance checks pass.

## Native interactive user questions (Codex Default mode)

On the unprivileged `codex` Linux account, add this user-scoped feature flag to
`~/.codex/config.toml` (preserve existing TOML sections and settings):

```toml
[features]
default_mode_request_user_input = true
```

Restart Codex, then check with `codex features list`. This setting is
intentionally **not** written by the MightyModels installer; user-specific
Codex preferences and permissions remain separate from the repository.

For **optional** feedback, use the actual native `request_user_input` tool
when listed in the active session. It provides choices and free-text input; do
not claim a popup was shown unless the tool was actually called.

For **required MightyModels decisions** (including investigation framing and
end-of-round gates), Default-mode Codex popups can auto-resolve. Ask the user
in ordinary conversation and end the turn without progressing the gate.
In Plan mode, the native question can be blocking when available, but a real
answer is still required. Never treat an empty reply, timeout, failure, or
interruption as consent. Persist pending decisions through existing MCP state
mechanisms where supported and verify resumption behavior before relying on it.

`autoResolutionMs` is deprecated in current Codex; `isBlocking` is decided
by the host/collaboration mode and isn't a general model-controlled timeout
switch. No documented `AGENTS.md` directive can force a Default-mode popup
to remain indefinitely. The safest fallback is a regular chat question.

### Global instructions under `~/.codex/AGENTS.md`

The installer manages a stanza in the user's global instructions that points
to this repository's `AGENTS.md`. Keep that managed stanza intact. An older
user-authored instruction such as “never specify `autoResolutionMs`” is
harmless but **does not disable the popup timeout**. Replace any promise that
questions will always remain visually pending with the accurate fallback:
required decisions use a normal chat question and pause the workflow until
an explicit answer. Do not append a duplicate managed stanza.

The `default_mode_request_user_input` feature flag enables the optional
Default-mode question tool but does not make its prompts blocking.
The original Claude `AskUserQuestion`
recorder hook is **not migrated**; do not assume Codex answers were
automatically recorded. Persist only the user's actual decision/evidence with
the available investigation tools and preserve the skill's ledger invariants.

## Troubleshooting named scout dispatches

A custom role may be listed in an agent TOML file but rejected at runtime with
`agent type is currently not available`. This is a **Codex agent registration
error**, not the normal MCP repository-registration response or an authorization
denial. The global installer now registers each of the 11 enabled roles explicitly in
user `~/.codex/config.toml` via `[agents."mm-..."]` with an absolute
`config_file` path. The source TOML and its instructions remain in
`~/.codex/agents/` and the MightyModels checkout.

After pulling the updated checkout, run `python3 scripts/install_codex_user.py`,
close all old Codex sessions and launch a **fresh** Codex session in the target
repository. Validate a read-only `mm-triage-code-scout` dispatch before resuming
a persisted investigation. The installer checks for unrelated custom role
definitions and refuses to overwrite them. If a freshly started Codex session
still returns this error, collect the actual `spawn_agent` result and
`codex --version` and treat it as an outstanding host compatibility issue.
Do not substitute a generic agent while claiming a named MightyModels scout
ran, and do not relax admission hooks to workaround registry errors.

## Cost-aware native agent routing (issue #6)

| Original Claude tier | Configured Codex tier | Validation |
| --- | --- | --- |
| Haiku | `gpt-6-luna`, medium | Generated; effective model unverified |
| Sonnet | `gpt-6.1-sol`, medium | Generated; effective model unverified |
| Opus | `gpt-6.1-sol`, high | Generated; effective model unverified |
| Fable/wingman | None (disabled) | Escalate decisions to the user |

This documents configured roles, not actual model dispatch or quota savings (issue #16).

Codex roles are generated from the original Claude role tiers. Haiku maps to
`gpt-6-luna` at medium effort (six focused retrieval/mechanical workers).
Sonnet maps to `gpt-6.1-sol` medium (engineer and Terry).
Opus maps to `gpt-6.1-sol` high (architect, merge-vader and uncle-bob).
The Fable-tier wingman is **not generated or installed for Codex** and is
blocked by the dispatch adapter. Its Claude source remains untouched; no
Astra or other premium replacement is selected.

These explicit per-agent model settings prevent ordinary inheritance of the
coordinator's selected model. Model availability depends on the user's Codex
account and CLI: confirm `/model` and test a named Luna scout plus a Sol
worker before declaring live routing validated. An unavailable model must not
silently fall back to the expensive parent. Higher reasoning consumes more
tokens; don't claim a fixed usage reduction without a representative benchmark.
Re-run `python3 scripts/install_codex_user.py` after upgrading and restart
Codex to refresh its agent definitions. The global installer now enables 11
Codex roles and still exposes all 19 skills, some of which may refer to the
unavailable wingman; those paths must block rather than dispatch it.

OpenAI references:
https://learn.chatgpt.com/docs/agent-configuration/subagents
https://learn.chatgpt.com/docs/models?surface=cli

## Codex live dispatch authorization probe — issue #9

**Safety status: NOT host-verified.** A direct invocation of
`hooks/codex_bridge.py` proves only that its Python logic runs, not that
the Codex host invokes it before native `spawn_agent`. An upstream Codex
report describes `spawn_agent` bypassing `PreToolUse`, allowing an agent
to start without consulting a deny hook:
https://github.com/openai/codex/issues/49736

A scoped opt-in audit marker helps distinguish an installed hook from a
**live host hook invocation**. It contains only a constant event label and
timestamp, never a prompt, argument, role name, token or repository content.
It is OFF by default, and written under the Codex user's private
`~/.local/state/mightymodels/codex-dispatch-probe.log`.

In an unprivileged `codex` shell:

```sh
export MIGHTYMODELS_CODEX_DISPATCH_PROBE=1
rm -f ~/.local/state/mightymodels/codex-dispatch-probe.log
cd ~/kc/kc-backend-core  # or a disposable test repo
codex
```

In that **new** session, ask for a single read-only
`mm-triage-code-scout` to list the repository's top-level filenames.
Exit, then check:

```sh
if test -s ~/.local/state/mightymodels/codex-dispatch-probe.log; then
    echo 'PreToolUse reached the bridge; verify actual denial separately'
else
    echo 'UNVERIFIED/UNSAFE: no native spawn_agent PreToolUse event was observed'
fi
unset MIGHTYMODELS_CODEX_DISPATCH_PROBE
```

**Do not test with a destructive command or an unauthorized live write.**
The next acceptance test should be a benign attempted engineer dispatch
without a started task, requiring a real host-level denial before declaring
the gate reliable. Even a marker plus a deny on one CLI version cannot
guarantee protection when hooks are untrusted, disabled or bypassed, and
Codex custom subagents inherit the parent's sandbox. A scout instructed
'read-only' is NOT a separate sandbox; run read-only investigations with a
read-only parent permission mode where possible, and do not rely on an
advisory restriction as security enforcement. This is a bounded diagnostic,
not a workaround that relaxes the gate.

## Codex session lifecycle restoration — issue #8

Codex `SessionStart` now invokes a pruning-only handler, avoiding Claude's
`CLAUDE_ENV_FILE` requirement. Codex `PostToolUse` responses from
`mcp__mighty_mcp__*` invoke the existing session-pointer handler to connect
the session with the most recently used ticket or investigation. Neither hook
prints credentials or logs raw MCP payloads. These records support later
compaction and handoff, and preserve Claude's existing `session-start`
export functionality in its own runtime.

**Important limitations:** hook trust, event presence and the actual
Codex session identifier need real-host verification. No Claude
`AskUserQuestion` recorder equivalent has been assumed: Codex's
`request_user_input` may time out, and unanswered decisions must never
be converted to persisted approvals. The session-pointer handler can
only record tools whose inputs identify the target; a bare
`investigation_start` response is not automatically linked until a
subsequent named investigation tool call. The remaining user-decision
recording work is tracked under #8 and #11.

## Use existing GitHub CLI credentials without exposing secrets (issue #12)

When the `codex` Unix user needs to read Kart-Chaser or other repositories,
first check its existing GitHub CLI session:

```sh
gh auth status -h github.com
gh api user --jq .login
gh repo view OWNER/REPO --json nameWithOwner
```

GitHub CLI commonly keeps its configuration at
`${XDG_CONFIG_HOME:-$HOME/.config}/gh`. This location may include
`hosts.yml`, whose contents can contain PATs. **Treat it as sensitive.**
Use `gh`'s credential management; never read, print, grep, paste, upload,
persist or log raw token material. Never access a different Linux account's
configuration with sudo or copy a user's GitHub token to another account.

To check whether a token environment variable is present without printing it:

```sh
python3 - <<'PY'
import os
for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
    print(key, 'set' if os.environ.get(key) else 'unset')
PY
```

A scoped GitHub command may still need additional approval, authentication
or repository authorization. A failed read does not mean there is no PAT;
a successful read does not authorize unrelated writes. Preserve GitHub
scopes and sandbox/approval boundaries. For missing credentials, ask the
user to use `gh auth login` or the approved credential connector; never
request a token be pasted into the conversation.

### Updating an existing global Codex hook installation

After lifecycle hook changes (issue #8), an older MightyModels-owned
`~/.codex/hooks.json` may contain only the previous PreToolUse,
PreCompact and SubagentStop events. The installer now accepts an existing
manifest only when every defined event matches exactly the current
MightyModels-owned definition. It can then replace that owned subset with the
new version (which adds SessionStart and PostToolUse). It **still refuses** a
symlink, a changed hook or an unrelated event; never remove another tool's
hooks to force installation. This is an intentionally narrow upgrade
compatibility measure. Full coexistence with unrelated hooks, crash-safe
multi-file rollback and duplicate-configuration diagnostics remain under
issue #15. Restart Codex and re-review changed hook trust hashes.

## Generated Codex-only skill files — issue #14 (first migration slice)

The original 19 `skills/*/SKILL.md` remain Claude-compatible and untouched.
Run `python3 scripts/sync_codex_skills.py` after changes to those sources,
then `python3 scripts/sync_codex_skills.py --check` (also enforced by Codex CI).

Codex reads separately generated `.codex/skills/<skill>/SKILL.md` files.
The generator strips Claude-only `allowed-tools` frontmatter, normalizes
MCP tool identifiers, translates legacy helper-file locations into paths
under `$HOME/.agents/skills`, and clarifies native user decisions and
subagent delegation. Original companion directories (`references`,
`scripts`, `assets`, and `evals`) remain available by symlink without
copying or changing them. The user-scoped installer migrates its previously
owned `~/.agents/skills/<name>` symlinks to these generated skill
directories. Project-scope links in `.agents/skills` also point there.

The generator also rewrites legacy Claude `CLAUDE_PLUGIN_ROOT` prose and
Claude-only model-alias instructions in the affected workflows so the Codex
copies reference installed skill links and native role model configuration.
The original Claude skill sources are unchanged.

This is an **initial transport-level translation**; it does NOT make the
Codex host enforce Claude `allowed-tools`, `maxTurns`, or automatic
skill preloads. Required decisions remain fail-closed. Certain multi-agent
Claude-specific workflows and live runtime compatibility still require
testing before claiming full parity with Claude; issue #14 stays open.

## Read-only Codex install doctor — issue #15 (diagnostic slice)

After updating or moving the MightyModels checkout, run as the unprivileged
`codex` account:

```sh
cd ~/code/mightymodels_codex
python3 scripts/install_codex_user.py
python3 scripts/codex_doctor.py
```

The doctor checks ownership and targets of the global MCP registration,
11 native agent role entries, 19 generated Codex skill symlinks, and the
managed global hook manifest. The checkout does not register a duplicate
MCP server or global lifecycle/dispatch hook events. Its project-specific
`.codex/hooks.json` is limited to `apply_patch` edit hygiene; the user-level
installer owns MCP and lifecycle hooks. The global hook source is at
`hooks/codex-global-template.json`. Plugin-mode hooks at
`hooks/codex-hooks.json` are still distinct from global mode; do not enable
both installations without verifying host precedence and duplicate delivery.
A nonzero exit indicates a missing or unexpected installed component.

The doctor makes **no writes**, does not run agent dispatches, and never reads
`~/.config/gh`, token files or credential values. It does not establish that
hooks actually fired or were trusted, or that scouts were sandboxed.
Remaining crash/power-loss transactionality, third-party hook coexistence,
plugin-vs-global precedence, and live host enforcement stay open under #15/#9.

## Read-only JSONL telemetry for live acceptance — issue #16

Codex's noninteractive `codex exec --json` streams JSONL events with
turn completions, item start events and numeric token usage. To check a
single bounded **read-only** run without saving raw prompts or tool output:

```sh
cd ~/kc/YOUR_DISPOSABLE_REPO
codex --version
codex exec --json --sandbox read-only \
  "Read only: summarize the top-level files and do not edit anything." \
  | python3 ~/code/mightymodels_codex/scripts/codex_trace_summary.py
```

The script parses the stream in memory and prints only counters for started
item types, completed/failed turns and numeric input/cached/output tokens.
It never prints prompts, command arguments, messages, thread IDs or raw
responses. Do not save the **raw** JSONL stream in bug reports, PRs or CI
artifacts. Disable telemetry by omitting the pipe/script entirely.

The report deliberately says `effective_model_identity: unverified` and
`quota_savings: not_measured`: model pins and token counts do not prove
actual child-agent identity, provider quota consumption or cost reduction.
Run matched baseline and MightyModels tasks on a real host and separately
verify agent routing, trust and state transitions before claiming #16 passed.
The summarizer cannot reconstruct hidden child turns or model metadata if
the event stream does not expose them.

## Project hygiene without unverified Claude hooks — issue #17

The original Claude project settings use Write/Edit suppression prompts,
post-edit Ruff formatting, Read diagnostics, and approval rules for sensitive
toolchain files. These Claude matchers are **not** asserted to execute in native
Codex. The global MightyModels hook bridge is for lifecycle/dispatch, not
automatic formatting in arbitrary target repositories.

For development **inside this MightyModels checkout**, the project-only
`.codex/hooks.json` now registers a narrow `PreToolUse` handler for
`apply_patch` / `Edit` / `Write`. Its read-only Python guard refuses newly
added `noqa`, `type: ignore` and `ty: ignore` annotations in the patch and
direct `uv.lock` patch changes. Unknown edit payloads are denied rather than
silently assumed safe. It does not change user/global dispatch or MCP hooks.

**This is not complete host enforcement.** Hook execution requires Codex to load
and trust this project's hooks, and some edits (including shell-driven writes)
may bypass `apply_patch` interception. No `ask` response is emitted: Codex
does not currently support PreToolUse `permissionDecision: "ask"`. A refusal
requires a separate user-approved workflow, not an automatic consent prompt.
The hook never runs a formatter or changes files itself.

Continue using the explicit repository-scoped quality workflow:

```sh
python3 scripts/codex_hygiene_check.py --base origin/main
make format
make check
```

The hygiene command is read-only, compares tracked Python changes against an
existing Git base, and returns 1 when new `noqa`, `type: ignore`, or
`ty: ignore` annotations need review. Exit 2 means the check could not
complete and must **not** be treated as a pass. It does not examine untracked
files, validate every type-suppression form, or replace review. It reports
counts, not potentially sensitive source lines. `make format` intentionally
changes files; run it only where edits are approved. `make check` runs the
repo's lint/tests. Review configuration-file edits explicitly, and regenerate `uv.lock`
through the dependency tooling rather than editing it directly. A static
hook test is not proof that the live host enforced a denial.

For other repositories, use **their own** format, lint, test and approval
procedures. Never run MightyModels' Ruff/ty settings against unrelated code
as an automatic global hook. No live Codex per-read/per-edit hook delivery or
protected-file approval behavior is claimed by this fallback.
