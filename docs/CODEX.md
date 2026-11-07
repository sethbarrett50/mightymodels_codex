# Experimental Codex compatibility

This branch adds native Codex role files for all 12 original MightyModels agents and packages the existing skills and Python MCP server using the portable Agent Plugins format. Original Claude Code files remain unchanged. **This is not yet a functional parity port**.

## What's implemented

- `.codex/agents/*.toml` contain the original agent instruction bodies and descriptive metadata.
- `.codex/config.toml` declares all 12 roles.
- `plugin.json` and `mcp.json` add portable plugin packaging for the existing `skills/` directory and `uv` MCP command.
- `.codex/compatibility-report.json` records source model pins and frontmatter that has not been mapped.
- No Astra model is configured; active Codex model selection is inherited.

## Important limits

- Claude's `Agent(...)` and `SendMessage` tool calls and plugin-qualified names do not automatically translate to Codex dispatch APIs.
- Claude agent tool allowlists, `skills:` preloading, and `maxTurns` settings aren't enforceable by converting Markdown to TOML. Native Codex agents inherit the parent session's permissions and MCP connections.
- Claude hook events such as `PreToolUse`, `SubagentStop`, `PostToolUse` and `PreCompact` require a separate compatibility audit. Do **not** assume safety admission hooks are active.
- `mcp.json` is packaging metadata; the `uv` MCP process must be started from a context where its Python project resolves. Actual startup is untested.
- Original skill documents still contain Claude-specific names such as `mcp__plugin_mightymodels_mighty-mcp__...` and model aliases. Those workflows need runtime adaptation.

## Next steps before normal use

1. Add a dispatcher adapter mapping MightyModels' plugin-qualified role names to the Codex custom roles and native agent tools.
2. Ensure `task_start`, owned-file enforcement, admission, and independent `task_verify` checks cannot be bypassed through missing hooks.
3. Update skills to resolve tool names dynamically or through Codex-specific instructions, keeping Claude originals working.
4. Run a real Codex CLI integration suite covering both successful and rejected dispatches, MCP initialization, verification, and compaction.

**No end-to-end Codex execution or safety-equivalence tests have been run for this branch.**
