---
name: break-it-down
description: >-
  Split one mightymodels task that is too large into tasks of one reviewable unit of work each,
  and put the split to the user before anything changes. Size is guidance. Use when
  `task_start` warns that a task is large, when an engineer or architect returns `too-large` with
  its cuts, or when a plan task is plainly several changes. Ends with native `request_user_input` and verified explicit approval for every piece (id, intent, acceptance, owned
  files); only after the user answers is the original superseded and the plan updated. Not for
  revising the ASKED stanza of one task (the architect's `replanned`).
when_to_use: >-
  Use for "break this task down", "split T4", "this task is too big", and when agents-assemble
  routes a `too-large` report or a `task_start` warning here.
argument-hint: "[task id]"
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. Always invoke real `request_user_input` for user questions, never a chat imitation of a popup. Required decisions should invoke native input in Default or Plan mode when exposed; never trust auto-resolved answers. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.


> **Codex native user questions (all skills):** Use the actual `request_user_input` tool for every question needing a user answer when available; never simulate an interactive popup using prose or a text multiple-choice list. Default mode should invoke the native tool for choices, including required decisions, when exposed. Invoking a popup is not approval: only a verified explicit user answer satisfies a gate. If the host cannot verify an explicit answer or enforce blocking authorization, leave the gate pending and request Plan mode; if the tool is unavailable, report that fact without an ordinary-chat choice imitation. Empty, missing, timed-out, cancelled, interrupted or automatically resolved responses never count as approval. Preserve the pending decision and persist only a verified explicit answer with available MightyModels MCP tools. This Codex-only contract overrides any later legacy instruction to ask in ordinary chat or use Claude question dialogs.


# break-it-down

One dispatch is one reviewable unit of work. A task past that size fails in a known way: the
implementer runs out of room, the verification proves half of it, and the reviewer gets a diff
nobody can hold in their head. Size is guidance, not a gate: `task_start` starts every task and
warns above three owned files or four criteria, and an engineer or architect that finds one
mid-task returns `too-large`. Those two, or a plan task that is plainly several changes, are the
routes here, and the user decides whether to split.

**Nothing changes before the user answers.** Until the user explicitly answers the blocking question in step 4 this skill
writes nothing: no task call that moves a task, no edit to the plan or to a
brief. The pieces are a proposal, and the plan is the user's. A timeout, cancellation, dismissal, empty or auto-resolved response is not an answer: keep the decision pending and invoke native `request_user_input` again when available. Do not start a piece.

**Argument:** the id of the task to split, given when the skill was started: "USER_REQUEST_ARGS". Empty
quotes mean none was given, and the task is the one `task_start` just warned about or a worker just returned
as `too-large`.

**Preconditions:** a staged ticket and the task's entry in the task list (`plan.md`, or the
issue's task list after one-shot). Missing either: stop and name it.

## Steps

**1. Read the task as it stands.** Its entry in the task list (intent, acceptance, `depends-on`,
verify), the ASKED stanza of its brief when one was written, and its status from
`task_show` with the `slug`.

A worker's `cuts` are where to begin, because it has read the code. Check them against step 2
before you adopt them, and read the files it listed as already edited: that work is in the tree,
uncommitted, and the pieces have to account for it.

**2. Find the cuts.** Cut where the task already has a seam, trying these in order:

- by behavior: criteria that can be proven apart go to different pieces;
- by module: files that change for different reasons go to different pieces;
- by order: what must land first (a schema before its callers, a helper before its users) is a
  piece of its own, and the pieces that need it name it in `depends-on`.

Every piece has to stand alone, so hold each one to this:

- Two to four acceptance criteria and about three owned files, the sizes `task_start` does not warn about.
- Every criterion of the original lands in exactly one piece, in its own words. None is dropped
  and none is invented. A criterion that two pieces each need half of is two criteria: write both
  out and say in the dialog that it was divided, because that changes what is asked.
- Every file the original owned lands in a piece. Two pieces that edit the same file run in
  order, joined by `depends-on`, never side by side.
- The repository passes after each piece, not only after the last: the plan's invariants hold at
  every task boundary. A piece that cannot be verified alone is not a piece yet.

Some tasks do not cut: one rename across thirty files is one change. Say so in the dialog
and offer the task whole; the user decides, and a warning stops nothing.

**3. Give the pieces ids.** The next free `T` ids of the task list, in dependency order. The
original's id is never reused, because its history stays under it. Each task that named the original in `depends-on` will name the piece that carries what it waited for.

**4. Ask the user once.** Write the pieces out in full in your message, then invoke native `request_user_input` in Default or Plan mode to choose split, keep or revise. Stop until a verified explicit answer; if unavailable, leave the gate pending. Each piece shows its id, its intent, its acceptance and its
owned files:

```text
T7 (sm): <one-line intent: what and where>
  depends-on: []
  acceptance:
  - <the criterion, as the original stated it> (was the first criterion of T4)
  - <another outcome sentence>
  owned: src/queue.py, tests/test_queue.py
```

Below the pieces, list what the split changes outside them: each `depends-on` that moves, each
criterion that was divided, and each file a worker already edited with the piece that takes it.
Use one native `request_user_input` question with these options:

- **Split as shown.** The original is superseded and the pieces replace it.
- **Keep it as one task.** Nothing is split; the task starts whole on the user's approval.
- **Change the split.** The user says what to change, using the native tool free-text option with a verified user response.

## After the answer

**Split as shown.** In this order, so that a session cut off halfway still has a true record:

1. Supersede the original with `task_mark`, `to` `superseded` and a `reason` naming the pieces (such as "split into T7, T8 and T9").
2. Update the task list where it lives (`plan.md`, or the issue's task list as one-shot wrote
   it). Under the original's heading leave one line, `superseded: split into T7, T8, T9`, in place
   of its acceptance and verify. Add the pieces in dependency order, and repoint each `depends-on`
   as the user explicitly approved.
3. Declare the pieces with `task_declare`, passing the `slug` and the new `T` ids, so each can be started.
4. Report one line per piece (id, size, intent) and the original as superseded, then hand back
   to agents-assemble. Each piece runs through its loop as a task of its own, from what-we-know
   onward; the original's brief is not reused.

**Keep it as one task.** Split nothing and change nothing in the task list. A task a worker
returned as `too-large` is still in progress: mark it `blocked` with that reason (`task_mark`),
then agents-assemble starts it again whole, or continues it whole, and the warning stops nothing.

**Change the split.** Return to step 2 with what the user said and ask again with the new pieces.
The earlier answer approved nothing.
