---
name: agent-debugging
description: Use when you are an engineer and a task's verification fails after your edit, to debug it alone, record each failed fix, and stop blocked at the third.
when_to_use: >-
  Preloaded into the engineer. It applies the moment a test, lint or type check the task names
  fails on your change, or a fix you tried did not make it pass.
user-invocable: false
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. A required decision in Default mode uses ordinary chat and stops until a real answer; auto-resolution never grants permission. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.


> **Codex required user-input contract (all skills):** In Default mode, a question that gates further action MUST be asked in ordinary chat; end the turn until the user explicitly replies. The native `request_user_input` popup may auto-resolve and is only for optional feedback in Default mode. In Plan mode, a genuinely blocking native question may be used when the host exposes it, but require a real explicit answer. Empty input, timeout, cancellation, interruption, and automatic resolution never count as consent. Preserve the pending decision and persist only the user's actual answer using available MightyModels tools. This is Codex-only; the Claude `Codex user decision gate` steps below remain unchanged.


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
