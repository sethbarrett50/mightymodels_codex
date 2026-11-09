---
name: ask-an-adult
description: >-
  Resolve a stuck judgment call through native blocking Plan-mode user input.
  No Wingman/Fable agent or substitute dispatch is available. Persist confirmed
  decisions through supported MCP tools before resuming. Not for retrieving facts (send a
  scout), not for work you can simply do, and not for confirming a plan you have
  already committed to.
when_to_use: >-
  Use when the user says they want a second opinion, when they invoke
  /ask-an-adult, or when the session has stalled on a judgment call - two
  defensible options, a hard-to-reverse choice, conflicting scout reports, a
  failure that survived two attempts, or a guess about user intent. Also use when whats-broken
  ends its phases with a judgment call between defensible options still open, and when any model
  does not know what to do next.
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. Always invoke real `request_user_input` for user questions, never a chat imitation of a popup. Required decisions need blocking Plan-mode input; if unavailable stop without auto-consent. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.

# ask-an-adult — native Codex decision escalation

Codex has no Fable/Wingman agent. **Do not call `spawn_agent` for Wingman, substitute
another agent, or invent an independent review.** The user's explicit decision is the
only authority for resolving this escalation.

## When to ask

Use this for two defensible options, an expensive-to-reverse choice, conflicting
evidence, two failed approaches, or missing user intent. Do not escalate merely
to bless an established plan or retrieve a fact that ordinary inspection can settle.

## 1. Present the decision

Summarize the choice in one sentence, the first-hand evidence and uncertainties,
at least two real options and their costs, and your tentative preference. State
clearly that this is your own analysis, **not a Wingman report**. Include the
information still needed for a well-founded decision.

Use the actual native `request_user_input` question tool in **Plan mode**, offering
at least two choices plus a free-text path when supported. Do not imitate
its UI by listing options in ordinary chat. The user must provide an explicit
answer to the blocking prompt. If the tool or blocking Plan mode is unavailable,
stop and explain the capability needed; do not ask a textual substitute or
proceed. A timeout, dismissal, empty answer, or automatic resolution does not
grant permission. Never silently substitute your preference.

## 2. Persist the actual answer before resuming

Only after an explicit user response, use the available `mighty_mcp` tools.
Do not claim the Claude question recorder ran in Codex.

- **Active investigation:** use `investigation_add` with a `decision` entry,
  `source=user`, the user's actual choice, and a valid round (at least 1).
  Read back the entry with `investigation_render`. If writing or reading fails,
  report the failure and stop without claiming a persisted decision.
- **Active ticket:** call `ticket_show` to read the current context first.
  Preserve its existing lines; use `ticket_update_context` with the **complete**
  revised list including the actual decision, within the ticket schema limits.
  Verify with `ticket_show`. If a safe update cannot fit or fails, do not
  overwrite the old context or pretend persistence succeeded.
- **Neither:** the user's answer is confirmed in this conversation but is not
  automatically durable. Explain that no state target was available. If the
  user wants a cross-session handoff, use `baton-pass` with explicit consent.

Do not store credentials or secret answers in an investigation or ticket.
Never convert a partial answer, silence or hypothetical option into user approval.

## 3. Resume the caller

Only after the user's choice is confirmed and any required state update is
verified may the caller continue within the approved scope. Report the choice,
whether persistence was actually verified, and any still-open uncertainty.
Do not dispatch Wingman, and do not call this an independent reviewer verdict.
