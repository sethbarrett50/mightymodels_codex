# MightyModels Codex port — status and installation

The port provides native Codex definitions for **12 agents**, **19 skills**, and a
local **35-tool MCP server**. Claude support is retained. It is **experimental**:
static tests and one live read-only subagent test do not establish complete
dispatch authorization or end-to-end workflow equivalence.

## Observed live results — Debian 13, Codex CLI 0.167.0 (November 2026)

The separate, unprivileged `codex` user on Debian 13 successfully:

- Installed uv 0.13.7 with Python 3.14 and cloned this repository.
- Passed `scripts/sync_codex_agents.py --check` (12 TOML roles, 19 skills).
- Discovered all 12 roles and all 19 skills in an interactive Codex session.
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

## User-scoped installation across repositories

Run this as the unprivileged Linux user that will launch Codex. Do not use sudo
or place GitHub PATs inside the MightyModels checkout.

```sh
cd ~/code/mightymodels_codex
uv sync --locked --no-dev
python3 scripts/install_codex_user.py
codex mcp list
```

The installer symlinks the 12 native roles into `~/.codex/agents/` and 19
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
denial. The global installer now registers each of the 12 roles explicitly in
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
