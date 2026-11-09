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

Codex has **no Fable/Wingman agent**. When any MightyModels skill requests a Wingman consultation, do not attempt a spawn, claim that a consultation occurred, or silently use Sol/Astra. Present evidence and options through the real `request_user_input` interface in Plan mode; if blocking native input is unavailable, stop without a text-choice substitute and resume only after a verified explicit answer. Preserve that answer using the existing MCP mechanisms when available; unanswered/timeout is never permission to proceed. This conditional route applies only to Codex, not to the original Claude workflow.

## Tool translation

1. Use Codex native agent delegation tools to create a subagent with the mapped role; reuse its thread for follow-ups and collect its report before updating task state. Do not treat spawning an agent as task completion.
2. Call MCP tools exposed by `mighty_mcp` using the tool names that Codex actually lists; Claude-qualified `mcp__plugin_mightymodels_mighty-mcp__tool` in skills means the corresponding `tool` from this MCP server. Never guess a tool that isn't exposed.
3. Read the named skill's `SKILL.md` and its references before running the workflow; Claude `skills:` frontmatter was not automatically migrated to a preloaded Codex context.
4. Use the explicit model and reasoning effort in each native role: original Haiku → `gpt-6-luna`, Sonnet → `gpt-6.1-sol` medium, Opus → `gpt-6.1-sol` high. Fable/wingman is disabled; do not spawn it or silently substitute the parent model. An unavailable selected model is a blocker, not permission to escalate to expensive alternatives. The coordinator retains its own chosen model.
5. When a skill asks the user a question, use Codex's actual `request_user_input` tool instead of a chat imitation of a popup. Optional input may use the tool in Default mode when exposed. For choice questions, offer a free-text path where supported. Required decisions must use genuinely blocking native input in Plan mode; if unavailable or in Default mode, stop and instruct the user to switch modes rather than displaying multiple-choice text or choosing a default. Accept only explicit answers; never count auto-resolution, timeout, cancellation or missing input as consent. Do not claim to have opened a popup unless you called the tool. This is distinct from execution approval.

## Model routing policy

The generated roles pin their models independently from the coordinator. Scout, intern, gitty-up, fact-checker, and qualitylens use Luna; engineer and Terry use Sol medium; architect, merge-vader, and uncle-bob use Sol high. Fable is disabled for Codex, not replaced by Astra or Sol. Keep Claude source frontmatter unchanged. On unavailable model, report the error and stop rather than silently using the coordinator model. Model support and observed usage must be verified live in Codex; static checks do not prove the runtime selected the model.

## Codex review model audit

For MCP review runs, the Codex launcher sets `MIGHTYMODELS_RUNTIME=codex` so `review_start` records the effective `gpt-6.1-sol` reviewer model rather than legacy Claude aliases, regardless of review depth. Native merge-vader and uncle-bob both use Sol/high. Depth controls personas and evidence scope; it does not override agent model pins. The Codex MCP refuses Fable `review_override` without writing state. Reject mismatched historical run metadata instead of misrepresenting the model used. Do not set this runtime flag on Claude sessions.

## Interactive gate behavior

Codex's native user-question tool is `request_user_input`. Always prefer the
**actual tool call** for every question directed to the user, never a plain-text
multiple-choice imitation. Check the live tool list; the user-scoped
`[features] default_mode_request_user_input = true` flag in
`~/.codex/config.toml` can expose optional questions in supported Default-mode
sessions after restarting Codex. The installer does not modify that preference.

A **required decision** (framing, approval, escalation, ticket choices,
end-of-round gates) needs blocking `request_user_input` in **Plan mode**.
Default-mode dialogs can auto-resolve; they are not safe permission gates.
If currently in Default mode, the tool is unavailable, or the host cannot
supply blocking input, **stop before the gate** and explain that the user
must switch to Plan mode or enable the native question tool. Never replace
the missing popup with prose/bullets, fabricate a tool call, or select a default.

A missing/empty answer, cancellation, timeout, interruption, tool failure or
automatic resolution never authorizes proceeding. Do not infer consent from
a displayed choice or from a final assistant message. If a verified user
answer is received, persist it through permitted MightyModels MCP tools
and read back the written state when the workflow requires persistence.
Preserve pending decisions across resume and compaction; never reconstruct
a decision from a popup that was not actually answered.

Do not invent tool parameters such as `autoResolutionMs` or `isBlocking` if
they are absent from the host tool schema. No instruction can force a
Default-mode prompt to remain open indefinitely.

## Existing GitHub authentication — discover safely

For GitHub tasks, **use the current Linux user's existing `gh` credentials**, not a copied PAT. Start with `gh auth status -h github.com` and `gh api user --jq .login`; test repository access with an innocuous read (for example `gh repo view OWNER/REPO --json nameWithOwner`) before a permitted write. Honor sandbox/network approval prompts and the current repository's authorization instructions.

`$XDG_CONFIG_HOME/gh` (usually `~/.config/gh`) is a **configuration location**, not blanket permission to read secret files. `hosts.yml`, Git credential helpers, token stores and environment variables may contain access tokens. **Never cat, print, grep token values, paste them into a chat/agent prompt, store them in MightyModels MCP state, check them into git or put them in logs/issues.** Do not inspect another Unix account's credentials or use sudo to bypass access limits. If necessary, check only whether `GH_TOKEN` or `GITHUB_TOKEN` is set, without displaying its value; let `gh` use the token internally.

When authentication or permissions fail, report the actual `gh` error, identify the required scope, and ask the user to complete a secure `gh auth login` or grant the proper access. Never silently switch accounts, fetch a raw PAT or bypass sandbox restrictions.

## Safety invariants — not optional

- **Start the task through the MightyModels MCP server before dispatching an implementer.** The task must have declared ownership, scoped acceptance outcomes, and required verification.
- Before dispatch, verify the owned-file set and worker type against the active task. Decline any dispatch whose scope cannot be verified. The Codex `PreToolUse` bridge is configured, but live host-level denial has not been proven. Refuse dispatch until the started task and owned-file scope are verified.
- Treat read-only worker instructions as a policy, *not* an actual sandbox. All subagents inherit the parent sandbox and approval settings. Do not grant a write-capable scout tasks or elevated permissions.
- After an implementer reports done, independently run the fact-checker and record the coordinator's verdict in MCP. Do not mark a task verified solely on the implementer's report.
- Track failures through the MCP server; respect the original three-attempt ceiling and ticket state transitions. Never bypass denied tool calls or broaden owned files to make a task pass.
- Keep GitHub/Jira and code modifications user-approved per the active session settings. Do not automatically merge or publish based only on model reports.

## Runtime status

Native discovery, MCP tool connectivity and read-only scout delegation were observed in Codex CLI 0.167.0. The Codex hook event bridge and complete fail-closed admission semantics remain **unverified**. Do not claim Codex safety parity or end-to-end MightyModels compatibility until the integration tests in `docs/CODEX.md` are performed. The original Claude files are retained for comparison.
