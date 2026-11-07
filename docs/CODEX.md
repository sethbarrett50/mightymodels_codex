# MightyModels Codex port — status and installation

The port provides native Codex definitions for **12 agents**, **19 skills**, and a
local **35-tool MCP server**. Claude support is retained. It is **experimental**:
static tests and one live read-only subagent test do not establish complete
dispatch authorization or end-to-end workflow equivalence.

## Observed live results — Debian 13, Codex CLI 0.167.0 (November 2026)

The separate, unprivileged \`codex\` user on Debian 13 successfully:

- Installed uv 0.13.7 with Python 3.14 and cloned this repository.
- Passed \`scripts/sync_codex_agents.py --check\` (12 TOML roles, 19 skills).
- Discovered all 12 roles and all 19 skills in an interactive Codex session.
- Connected to \`mighty_mcp\`; 35 tools were listed. A real
  \`investigation_list({})\` request reached the server, but state reads returned
  "no repository is recorded" because no write unit of work had registered it.
- Ran the native \`mm-triage-code-scout\` agent to inspect MCP registration code;
  the agent finished and reported the nine registrars.
- Created \`~/.local/share/mightymodels/state.db\` and an MCP log.
- **Did not establish** that \`PreToolUse\` blocked unauthorized dispatch or that
  \`SubagentStop\` persisted the scout report. No implementation workflow ran.

The scout's \`/root/...\` agent identifier is a coordinator hierarchy identifier;
the OS account was verified as UID 1002 (\`codex\`), not Linux root.

## User-scoped installation across repositories

Run this as the unprivileged Linux user that will launch Codex. Do not use sudo
or place GitHub PATs inside the MightyModels checkout.

\`\`\`sh
cd ~/code/mightymodels_codex
uv sync --locked --no-dev
python3 scripts/install_codex_user.py
codex mcp list
\`\`\`

The installer symlinks the 12 native roles into \`~/.codex/agents/\` and 19
skills into \`~/.agents/skills/\`, adds a clearly marked \`mighty_mcp\` section
to \`~/.codex/config.toml\`, installs absolute-path hooks at
\`~/.codex/hooks.json\`, and adds a managed instruction stanza in
\`~/.codex/AGENTS.md\`. It refuses to overwrite unrelated files and does not
modify sandbox, approval, model, or network settings. It can be rerun.

\`\`\`sh
python3 scripts/install_codex_user.py --uninstall
\`\`\`

Uninstall removes only owned links and managed stanzas. It preserves Codex
authentication, unrelated configuration, all user repositories, PAT files, and
the MightyModels state database. Keep this checkout at its installed location;
reinstall after moving it. Restart Codex after installing or uninstalling.

**Caution:** Codex may require explicit trust for newly installed hooks; hooks
being present on disk is not evidence they executed. An unrelated preexisting
\`~/.codex/hooks.json\` causes the installer to stop rather than overwrite it.
Merge hook definitions manually in that case.

### Per-repository workflow

\`\`\`sh
cd ~/kc/YOUR_REPO
codex mcp list
codex
\`\`\`

In the interactive session, ask Codex to list the *registered* \`mighty_mcp\`
ticket/task tools and delegate a **read-only** scout. Compare with the actual
tools and agent event trace, not just configuration files.

The MCP launcher now keeps the target repository working directory while
loading the MightyModels Python package from this checkout. Repository state is
distinct from the plugin source tree. If the host starts MCP from a different
directory, confirm its reported repository identity before writing state.

## Source checkout mode

From the repository root, install Python >=3.14 and uv, run
\`uv sync --locked --no-dev\`, then start \`codex\`. The checkout includes its
own \`.codex/config.toml\`, local agent definitions and skill links. Do not
run a second duplicate MCP server unintentionally when user-level installation
is active; prefer the user-scoped setup when working across repos.

## Adaptation and safety limitations

- Original Claude definitions live in \`agents/**/*.md\`. Generated TOML files
  set names, instructions and reasoning effort, but do **not** enforce Claude
  model aliases, \`maxTurns\`, tool restrictions or automatic skill preloads.
- Codex native delegation replaces Claude's Agent / SendMessage tool names.
  Resolve MCP calls to exposed \`mighty_mcp\` tools. Never guess tool names.
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
   \`mm-workers-engineer\` delegation. Do not substitute a prompt-only refusal.
3. Verify a valid scoped engineer task, owned-file check, independent
   fact-checker, persisted verdict and three-failed-fix ceiling.
4. Verify scout write prevention using actual sandbox permissions.
5. Verify SubagentStop evidence, compaction, resume, session state and user
   approvals, then test installed-plugin mode separately.
6. Validate GitHub/Jira writes through properly scoped approved tooling.

The project is not production-ready until these acceptance checks pass.
