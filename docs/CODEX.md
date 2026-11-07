# MightyModels Codex port — current status

This branch adds Codex native agent definitions for all 12 MightyModels roles, a portable plugin manifest, an MCP launcher and project-local skill discovery. It is an experimental port, **not an end-to-end validated replacement for Claude Code**.

## Local checkout usage

1. Install Python >= 3.14 and [uv](https://docs.astral.sh/uv/).
2. From this repository root, run `uv sync --locked --no-dev`.
3. Start `codex` from this directory; Codex should read `AGENTS.md`, discover `.codex/agents/`, and connect `mighty_mcp` configured in `.codex/config.toml`.
4. Verify the MCP connection is active and the expected `ticket_*` and `task_*` tools appear. If it fails, run `sh ./bin/mightymodels-mcp-codex` separately for logs; the stdio MCP server normally stays running.
5. If using the manually installed plugin instead, the root portable `plugin.json` and `mcp.json` provide skills and server wiring; the launch wrapper expects `PLUGIN_ROOT` from the plugin environment.

All 19 skills are also linked under `.agents/skills/` to make the existing `skills/` tree available for project-scoped Codex skill discovery. Symlinks work on Linux/macOS; Windows users may need a checkout with symlink support.

## Adaptation rules

- Agent roles are named `mm-{triage,workers,review}-<name>`; see root `AGENTS.md` for exact mappings.
- Claude `Agent` and `SendMessage` refer to Codex's native delegation/follow-up tools, not to literal tools of those names.
- Claude plugin-qualified MCP names must resolve to the actual exposed `mighty_mcp` tool. If it is unavailable, block the workflow instead of guessing or editing ticket state manually.
- Original frontmatter is still in `agents/**/*.md`. Codex TOML sets the role, instructions and reasoning effort. The original model pins, `maxTurns`, tool allowlists and `skills:` preloads do not directly enforce Codex behavior.
- Codex parent permissions govern all children. A prompt-only read-only claim cannot replace the Claude `tools:` allowlist or dispatch guard.
- No Astra usage: the model is inherited from the active Codex session.

## Known gaps and manual acceptance tests

1. Validate actual Codex CLI discovery of all 12 custom agents and the 19 skills.
2. Test MCP startup and tool invocation using a real Codex client, with a clean environment and both checkout and installed-plugin modes.
3. Confirm a planned `engineer` dispatch includes an active started task, owned file list, and the correct acceptance criteria; verify an invalid dispatch is **refused**, rather than merely warned.
4. Confirm an engineer can implement a scoped task and a separate fact-checker independently verifies it; validate persisted state and the three-failed-fix ceiling.
5. Verify read-only scouts cannot modify files under your actual parent permissions. Run controlled sandbox tests—do not assume the agent prompt enforces this.
6. Check session-resume, compaction, `SubagentStop` and `AskUserQuestion` equivalents. The original `hooks/hooks.json` still targets Claude events and matchers; do not enable it unchanged without exercising each path.
7. Confirm GitHub/Jira side effects and CI workflows happen only through permitted tools.

There is not yet a passing live Codex integration test suite for these scenarios. A static TOML or unit test is not proof of runtime enforcement.

## Source of truth

Keep original upstream MightyModels code and Claude support intact. The Codex-specific adaptation lives in `.codex/`, `.agents/skills/`, `AGENTS.md`, root portable manifests and `bin/mightymodels-mcp-codex`. See `.codex/compatibility-report.json` for unmapped Claude frontmatter.
