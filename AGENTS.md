# MightyModels for Codex — orchestration policy

This fork has two runtimes: native Codex roles in `.codex/agents/`, and legacy Claude definitions in `agents/`. **Use the Codex roles** when operating in Codex; do not invoke Claude's `Agent`, `SendMessage`, `AskUserQuestion`, or names beginning `mcp__plugin_mightymodels_mighty-mcp__` literally.

## Role mapping

- `mightymodels:triage:code-scout` → `mm-triage-code-scout`
- `mightymodels:triage:web-scout` → `mm-triage-web-scout`
- `mightymodels:triage:wingman` → `mm-triage-wingman`
- `mightymodels:triage:terry-toolchain` → `mm-triage-terry-toolchain`
- `mightymodels:workers:engineer` → `mm-workers-engineer`
- `mightymodels:workers:architect` → `mm-workers-architect`
- `mightymodels:workers:intern` → `mm-workers-intern`
- `mightymodels:workers:gitty-up` → `mm-workers-gitty-up`
- `mightymodels:review:fact-checker` → `mm-review-fact-checker`
- `mightymodels:review:merge-vader` → `mm-review-merge-vader`
- `mightymodels:review:qualitylens` → `mm-review-qualitylens`
- `mightymodels:review:uncle-bob` → `mm-review-uncle-bob`

## Tool translation

1. Use Codex native agent delegation tools to create a subagent with the mapped role; reuse its thread for follow-ups and collect its report before updating task state. Do not treat spawning an agent as task completion.
2. Call MCP tools exposed by `mighty_mcp` using the tool names that Codex actually lists; Claude-qualified `mcp__plugin_mightymodels_mighty-mcp__tool` in skills means the corresponding `tool` from this MCP server. Never guess a tool that isn't exposed.
3. Read the named skill's `SKILL.md` and its references before running the workflow; Claude `skills:` frontmatter was not automatically migrated to a preloaded Codex context.
4. Resolve Claude model aliases (haiku, sonnet, opus, fable) to the **currently selected Codex model**. Never request Anthropic or Astra models. Use each role's declared reasoning effort where supported.
5. When a skill calls for Claude's `AskUserQuestion`, use Codex's native `request_user_input` tool **if it is actually available in the current session**. Offer concise selectable options with a custom/free-text answer path. Invoke the tool; printing bullets or claiming to have opened a popup is not equivalent. If unavailable, ask the same question explicitly in chat, stop and await the user's answer. Never fabricate or auto-select an answer. This input tool is distinct from execution approval.

## Interactive gate behavior

On the `codex` Linux account, enabling `[features] default_mode_request_user_input = true` in `~/.codex/config.toml` makes the native question tool available in supported Default-mode sessions. Restart Codex after changing it. This is a user-level setting, not a project or plugin setting. The availability of a tool must still be checked at runtime. Codex Default-mode prompts may time out; a timeout or empty answer is **not** consent to progress past a required gate.

For the `lets-investigate` and other interactive MightyModels skills, the investigation framing, user classification, and end-of-round decision must reflect a real user response. Claude's `AskUserQuestion` recorder hook has not been migrated to Codex. If a Codex reply is not automatically persisted by MCP, record the exact user-provided evidence/decision through the existing permitted investigation tools, following the skill's data rules; never invent user decisions.

## Safety invariants — not optional

- **Start the task through the MightyModels MCP server before dispatching an implementer.** The task must have declared ownership, scoped acceptance outcomes, and required verification.
- Before dispatch, verify the owned-file set and worker type against the active task. Decline any dispatch whose scope cannot be verified. The Codex `PreToolUse` bridge is configured, but live host-level denial has not been proven. Refuse dispatch until the started task and owned-file scope are verified.
- Treat read-only worker instructions as a policy, *not* an actual sandbox. All subagents inherit the parent sandbox and approval settings. Do not grant a write-capable scout tasks or elevated permissions.
- After an implementer reports done, independently run the fact-checker and record the coordinator's verdict in MCP. Do not mark a task verified solely on the implementer's report.
- Track failures through the MCP server; respect the original three-attempt ceiling and ticket state transitions. Never bypass denied tool calls or broaden owned files to make a task pass.
- Keep GitHub/Jira and code modifications user-approved per the active session settings. Do not automatically merge or publish based only on model reports.

## Runtime status

Native discovery, MCP tool connectivity and read-only scout delegation were observed in Codex CLI 0.167.0. The Codex hook event bridge and complete fail-closed admission semantics remain **unverified**. Do not claim Codex safety parity or end-to-end MightyModels compatibility until the integration tests in `docs/CODEX.md` are performed. The original Claude files are retained for comparison.
