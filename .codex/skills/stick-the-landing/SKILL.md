---
name: stick-the-landing
description: >-
  Close an mightymodels sprint: gate the push on `task_ready`, push, open the PR
  with a checked body, have gitty-up watch CI, and route each failing check as a recorded C task
  (mechanical fixes to an engineer residual, then architect once; non-obvious causes to
  whats-broken), treating CI as the hard gate at every new HEAD.
  On green, ask in ordinary chat whether to review now (review-circus) or hand off (baton-pass), then wait for an explicit answer.
  Not for Jira sprint operations, not the review itself
  (review-circus), and not for mid-sprint work (agents-assemble owns the loop).
when_to_use: >-
  Only the user starts it, when the
  sprint's tasks are done: "finish the sprint", "wrap up the ticket", "push and open the PR",
  "get the PR open", "ship it up".
argument-hint: "[ticket-slug]"
disable-model-invocation: true
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. Always invoke real `request_user_input` for user questions, never a chat imitation of a popup. Required decisions should invoke native input in Default or Plan mode when exposed; never trust auto-resolved answers. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.


> **Codex native user questions (all skills):** Use the actual `request_user_input` tool for every question needing a user answer when available; never simulate an interactive popup using prose or a text multiple-choice list. Default mode should invoke the native tool for choices, including required decisions, when exposed. Invoking a popup is not approval: only a verified explicit user answer satisfies a gate. If the host cannot verify an explicit answer or enforce blocking authorization, leave the gate pending and request Plan mode; if the tool is unavailable, report that fact without an ordinary-chat choice imitation. Empty, missing, timed-out, cancelled, interrupted or automatically resolved responses never count as approval. Preserve the pending decision and persist only a verified explicit answer with available MightyModels MCP tools. This Codex-only contract overrides any later legacy instruction to ask in ordinary chat or use Claude question dialogs.


# stick-the-landing

The bridge from "work done" to "work reviewable". It is its own stage so the user gets a look
between the sprint's last commit and anything public, and so CI failures are routed by cause,
not handled by whoever is cheapest.

Run from the repository root. Codex resolves MightyModels helpers through installed `$HOME/.agents/skills/` links:

- `task_ready`, `task_start`, `task_verify`, `task_mark` and `task_show` for task state.
- `python3 "$HOME/.agents/skills/open-ticket/scripts/humanize_tracker_body.py"` for the PR body.

Dispatch through prompting-subagents using the registered native Codex roles and each role TOML model/effort settings. The ticket
`subagent-models` aliases are Claude-only historical values, not dispatch arguments or proof of the effective host model.

**Argument:** the ticket's slug, given when the skill was started: "USER_REQUEST_ARGS". Empty quotes mean
none was given, and the ticket is the session's active one.

## 1. Gate

`REPORT.md` must exist: agents-assemble writes it as its last act, so its absence means the
loop stopped early. Say so and stop rather than papering over it. Then call `task_ready` with
the `slug`. It answers `ready` only when a plan task has been started, every plan task is
verified or superseded, and no C or R task is failed or blocked; otherwise it answers
`not ready` and lists the reasons. It reads task status only and runs no command. Any
`not ready` is the loop's unfinished work: list the reasons and send the user back to
agents-assemble.

CI is the hard gate at landing, and there is no local proof step before a push. Treat every check
on the PR as gating whether or not branch protection requires it.

## 2. Push and open the PR

The primary pushes the branch. A rejected push is reported and the skill stops; never force-push around it.

Write the PR body to `.mightymodels/SLUG/pr-body.md`: the repository's pull request template
(`.github/pull_request_template.md` or `.github/PULL_REQUEST_TEMPLATE/`) filled from REPORT.md,
linking the issue (`Closes #N` for a GitHub issue; the Jira key where the repository's
convention puts it). Then:

```bash
python3 "$HOME/.agents/skills/open-ticket/scripts/humanize_tracker_body.py" fix .mightymodels/SLUG/pr-body.md --shape comment
```

Reword what `fix` reports, then run `check` with the same shape until it exits 0. Open the PR
with `gh pr create --body-file .mightymodels/SLUG/pr-body.md`. When `gh` is unavailable or
fails, surface the exact command and stop; CI watching resumes once the PR exists.

## 3. Watch CI

Dispatch gitty-up with the PR number and nothing else ("Watch PR 214."); it resolves the rest
itself and never touches code. Its report is `pass`, `fail` with per-check findings and log
tails, or `error`. An `error` (no checks, still pending, unresolvable PR) is the user's news:
never treated as a pass, re-watched at most once.

## 4. Route each failing check

One C task per failing check (`C1`, `C2`, ...); checks that fail on the same log line share
one. Apply the log-tail test: *can the fix be stated as one Fix:/Verify: line from the log
tail alone?*

- **Yes, mechanical** (lint rule, formatter drift, missing import, a trivially wrong
  assertion). Record the attempt with `task_start`, then dispatch an **engineer** with the residual variant of its template,
  Fix:/Verify: verbatim, with SLUG, `C1` as the task id and the check's name as the finding:

  The call carries SLUG, `C1` as the task id, `by` `engineer`, `owned` the files the log tail
  names and `acceptance` the outcome sentence the Fix must make true, as one short sentence.

  The residual carries `Fix:` and an outcome sentence, for example "the lint check passes on
  this file". When a local command reproduces the check, the engineer runs it in sandboxed Bash,
  names it and quotes its output. Otherwise the CI check itself proves the outcome after the
  re-push.

- **No, non-obvious** (a behavioral failure, a flake that is not obviously a flake, anything
  where the cause would be a guess). Invoke **whats-broken**; the phased protocol exists so
  the cheapest worker does not symptom-patch CI into a worse state. Its fix dispatch is the C
  task's engineer attempt, recorded with `task_start` the same way.

## 5. Re-push

Run `task_ready`, push, and let CI prove the new HEAD. A C task still in progress does not block
`ready`, since its proof is the CI run the push starts. A CI fix that breaks verified work shows up
as a failing check and is routed as one (step 4). Then gitty-up re-watches.

## 6. Close or climb

- **The check passes.** Close the C task on the evidence of the check it repaired, with
  `task_verify`: the `slug`, `task_id` `C1`, the fix `commit` and `verdict` `verified`, on gitty-up's
  evidence that the check passed. The commit must stay inside the owned set.

- **The check still fails**, or the engineer returns `failed` or `blocked`.
  `task_mark` with `to` `failed` or `blocked` and a `reason` (a task the gate blocked already
  is `blocked`), then the owner's question unless `auto-escalate` is on, as agents-assemble step 6
  has it, and **architect** once (`task_start` with `by` `architect`, the architect
  template with the trigger and the failing tail). The architect also failing goes to
  **whats-broken**; whats-broken's own stop rules end at the user,
  with every attempt's evidence.

After a compaction, `task_show` (with `slug`) and `gh pr view`
are the state; the conversation is not.

## 7. On green

Every check passes and `task_ready` answers `ready`. Tell the user, then
ask in ordinary chat whether to review now or hand off, then end the turn until the user explicitly chooses. Neither a timeout nor an automatic response is consent:

- **Review now**: invoke review-circus in this session. Recommended when this session runs a
  mid-tier primary and has context to spare.
- **Hand off**: invoke baton-pass, which prints the review session's prompt with review-circus
  as the skill to invoke.

## Boundaries

stick-the-landing pushes, opens the PR, and records C tasks. It never force-pushes, merges,
comments on the PR (review-circus owns that), or edits code itself: every fix is a dispatch
gated by the task tools. Every fallback (PR body drafted but not opened, push rejected, CI
`error`) is named in the closing summary.
