---
name: agent-debugging
description: Use when you are an engineer and a task's verification fails after your edit, to debug it alone, record each failed fix, and stop blocked at the third.
when_to_use: >-
  Preloaded into the engineer. It applies the moment a test, lint or type check the task names
  fails on your change, or a fix you tried did not make it pass.
user-invocable: false
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. Always invoke real `request_user_input` for user questions, never a chat imitation of a popup. Required decisions should invoke native input in Default or Plan mode when exposed; never trust auto-resolved answers. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.


> **Codex native user questions (all skills):** Use the actual `request_user_input` tool for every question needing a user answer when available; never simulate an interactive popup using prose or a text multiple-choice list. Default mode should invoke the native tool for choices, including required decisions, when exposed. Invoking a popup is not approval: only a verified explicit user answer satisfies a gate. If the host cannot verify an explicit answer or enforce blocking authorization, leave the gate pending and request Plan mode; if the tool is unavailable, report that fact without an ordinary-chat choice imitation. Empty, missing, timed-out, cancelled, interrupted or automatically resolved responses never count as approval. Preserve the pending decision and persist only a verified explicit answer with available MightyModels MCP tools. This Codex-only contract overrides any later legacy instruction to ask in ordinary chat or use Claude question dialogs.


# agent-debugging

The engineer's form of whats-broken, for one worker with no one to dispatch. The rule is the same: **no fix before evidence.** The engineer does not dispatch architect, code-scout or web-scout here; it reads, runs and tests with its own tools. `failed_fix_record` counts the failed fixes, so the limit holds even when the engineer would rather try one more.

## Steps

**1. Reproduce.** Run the task's failing verification and show its output. When it fails only some of the time, say so with the observed frequency and do not treat it as deterministic.

**2. Evidence.** With `Read`, `Grep` and `Bash`: the failing path, `git log` and `git blame` on it, what the error says against what you assumed it says, and the configuration at the failure site. No fix is proposed in this step.

**3. One hypothesis.** State it once, falsifiable: `I believe <X> is the cause because <evidence>. If true, <Z> will show it.` Two live hypotheses prove neither.

**4. Test it minimally.** The cheapest check that could falsify it: a log line, a narrowed test run. Not a fix. Falsified: back to step 3 with the new evidence. Confirmed: step 5.

**5. Fix inside your owned files, then run the verification again.** A fix that needs a file outside the owned set is not yours to make: report `blocked` with the file and the hypothesis.

**6. Record a fix that failed.** When the verification still fails, call `failed_fix_record` before you try anything else, with the `slug` (the directory in the brief path `.mightymodels/<slug>/briefs/`), the `task_id` from the dispatch, and a `hypothesis` in one sentence, such as "I believe the batch size is zero because the drain log shows an empty batch; the fix that set it did not change the log".

The answer says how many fixes are left. The hypothesis is stored redacted, so keep secrets out of it anyway.

## The limit

The tool stores three failed fixes per task. A fourth call is refused with an error that says the task is blocked and lists the three hypotheses in order. That refusal ends the work: report `blocked`, copy the listed hypotheses into the report, and make no further edit. The coordinator routes a blocked report to the owner's question and the architect, then to whats-broken, and the engineer dispatches neither; a hypothesis already tried is not tried again there. The task tools other than `failed_fix_record` are not yours: do not start, mark or verify a task to get around the refusal.
