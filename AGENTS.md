# MightyModels for Codex — orchestration policy

This fork has two runtimes: native Codex roles in `.codex/agents/`, and legacy Claude definitions in `agents/`. **Use the Codex roles** when operating in Codex; do not invoke Claude's `Agent`, `SendMessage`, `AskUserQuestion`, or names beginning `mcp__plugin_mightymodels_mighty-mcp__` literally.

## Role mapping

- `mightymodels:triage:code-scout` → `mm-triage-code-scout`
- `mightymodels:triage:web-scout` → `mm-triage-web-scout`
- `mightymodels:triage:wingman` → **disabled in Codex** (Fable not used; no substitute allowed)
- `mightymodels:triage:terry-toolchain` → `mm-triage-terry-toolchain`
- `mightymodels:workers:engineer` → `mm-workers-engineer`
- `mightymodels:workers:architect` → `mm-workers-architect`
- `mightymodels:workers:intern` → `mm-workers-intern`
- `mightymodels:workers:gitty-up` → `mm-workers-gitty-up`
- `mightymodels:review:fact-checker` → `mm-review-fact-checker`
- `mightymodels:review:merge-vader` → `mm-review-merge-vader`
- `mightymodels:review:qualitylens` → `mm-review-qualitylens`
- `mightymodels:review:uncle-bob` → `mm-review-uncle-bob`

## Disabled Wingman decision routing

Codex has **no Fable/Wingman agent**. When any MightyModels skill requests a Wingman consultation, do not attempt a spawn, claim that a consultation occurred, or silently use Sol/Astra. Present the existing evidence and options directly to the user as a required chat decision, end the turn, and resume only after an explicit user answer. Preserve that answer using the existing MCP mechanisms when available; unanswered/timeout is never permission to proceed. This conditional route applies only to Codex, not to the original Claude workflow.

## Tool translation

1. Use Codex native agent delegation tools to create a subagent with the mapped role; reuse its thread for follow-ups and collect its report before updating task state. Do not treat spawning an agent as task completion.
2. Call MCP tools exposed by `mighty_mcp` using the tool names that Codex actually lists; Claude-qualified `mcp__plugin_mightymodels_mighty-mcp__tool` in skills means the corresponding `tool` from this MCP server. Never guess a tool that isn't exposed.
3. Read the named skill's `SKILL.md` and its references before running the workflow; Claude `skills:` frontmatter was not automatically migrated to a preloaded Codex context.
4. Use the explicit model and reasoning effort in each native role: original Haiku → `gpt-6-luna`, Sonnet → `gpt-6.1-sol` medium, Opus → `gpt-6.1-sol` high. Fable/wingman is disabled; do not spawn it or silently substitute the parent model. An unavailable selected model is a blocker, not permission to escalate to expensive alternatives. The coordinator retains its own chosen model.
5. When a skill calls for Claude's `AskUserQuestion`, distinguish **optional feedback** from a **required decision gate**. For optional feedback, use Codex's native `request_user_input` only when actually available in the current session; offer concise options and a free-text path. For a required gate in Default mode, ask directly in chat and stop until the user answers, because the native popup can auto-resolve. In Plan mode a native blocking question may be used when available, but verify a real answer was received. Never claim to have opened a popup without invoking the tool, and never fabricate or auto-select an answer. This tool is distinct from execution approval.

## Model routing policy

The generated roles pin their models independently from the coordinator. Scout, intern, gitty-up, fact-checker, and qualitylens use Luna; engineer and Terry use Sol medium; architect, merge-vader, and uncle-bob use Sol high. Fable is disabled for Codex, not replaced by Astra or Sol. Keep Claude source frontmatter unchanged. On unavailable model, report the error and stop rather than silently using the coordinator model. Model support and observed usage must be verified live in Codex; static checks do not prove the runtime selected the model.

## Interactive gate behavior

On the `codex` Linux account, enabling `[features] default_mode_request_user_input = true` in `~/.codex/config.toml` makes the native question tool available in supported Default-mode sessions. Restart Codex after changing it. This is a user-level setting, not a project or plugin setting. The availability of a tool must still be checked at runtime. Codex Default-mode prompts may time out; a timeout or empty answer is **not** consent to progress past a required gate.

For the `lets-investigate` and other interactive MightyModels skills, the investigation framing, user classification, and end-of-round decision must reflect a real user response. Claude's `AskUserQuestion` recorder hook has not been migrated to Codex. If a Codex reply is not automatically persisted by MCP, record the exact user-provided evidence/decision through the existing permitted investigation tools, following the skill's data rules; never invent user decisions.

## Required user decisions — fail closed

- Identify decision gates explicitly (investigation framing, user classification, end-of-round choice, workflow approval, or any step whose correct next action depends on the user).
- In **Default mode**, do not rely on `request_user_input` for a required decision: its popup can auto-resolve without an answer. Ask one clear question in ordinary chat and **end the turn** until the user responds. Native `request_user_input` is appropriate for optional, non-gating feedback only.
- In **Plan mode**, a native `request_user_input` question can be blocking if the tool is available. A missing/empty/tool-cancelled response is still not a decision.
- A timeout, missing/empty answer, auto-resolution, tool failure, or interrupted session must **never** be interpreted as approval or as permission to advance a required gate.
- Do not dispatch workers, change ticket/investigation state, perform gated writes, or select defaults while the required decision is pending. Unrelated non-gated work may continue only when safe.
- Persist the pending decision using existing permitted MightyModels state/evidence mechanisms when available; restore it across compaction or resume. Never invent a reply or claim a prompt remains visually open.
- Do not attempt to set `autoResolutionMs` or `isBlocking` in a model-facing call unless the active tool schema exposes and documents that parameter. Instructions cannot override Codex TUI timeout behavior.

## Safety invariants — not optional

- **Start the task through the MightyModels MCP server before dispatching an implementer.** The task must have declared ownership, scoped acceptance outcomes, and required verification.
- Before dispatch, verify the owned-file set and worker type against the active task. Decline any dispatch whose scope cannot be verified. The Codex `PreToolUse` bridge is configured, but live host-level denial has not been proven. Refuse dispatch until the started task and owned-file scope are verified.
- Treat read-only worker instructions as a policy, *not* an actual sandbox. All subagents inherit the parent sandbox and approval settings. Do not grant a write-capable scout tasks or elevated permissions.
- After an implementer reports done, independently run the fact-checker and record the coordinator's verdict in MCP. Do not mark a task verified solely on the implementer's report.
- Track failures through the MCP server; respect the original three-attempt ceiling and ticket state transitions. Never bypass denied tool calls or broaden owned files to make a task pass.
- Keep GitHub/Jira and code modifications user-approved per the active session settings. Do not automatically merge or publish based only on model reports.

## Runtime status

Native discovery, MCP tool connectivity and read-only scout delegation were observed in Codex CLI 0.167.0. The Codex hook event bridge and complete fail-closed admission semantics remain **unverified**. Do not claim Codex safety parity or end-to-end MightyModels compatibility until the integration tests in `docs/CODEX.md` are performed. The original Claude files are retained for comparison.
