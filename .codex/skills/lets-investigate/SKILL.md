---
name: lets-investigate
description: >-
  Run a chat-first investigation as a gated loop: frame one target, dispatch scouts for
  repository facts and documentation facts, fold every report into a restated in-chat ledger
  (knowns, open questions, decisions, resources), then stop for an explicit native interactive decision where the user
  chooses to dig further, redirect, or consolidate. Persists its ledger as rows
  in the state database and changes nothing else. Not for reviewing a branch or grading a codebase (review-circus), debugging
  with a known reproduction (whats-broken), or non-engineering research such as market or
  vendor comparisons.
when_to_use: >-
  Use at the START of work, before any ticket
  exists, whenever the user wants to understand something before acting: "let's investigate X",
  "look into this claim", "triage this bug report", "why would Y be happening", "dig into this
  error", "how does library Z actually handle this, check the docs and our usage". Also for
  research questions about a dependency, API, protocol, or tool the repository relies on.
argument-hint: "[question, claim or error]"
---

> **Native Codex workflow (generated):** This file is generated from the Claude skill; do not edit it directly. MCP calls must use actual `mighty_mcp` tools exposed by the current Codex session. Use named native `spawn_agent` roles; never invoke Claude Agent/SendMessage APIs or inherit model aliases. Always invoke real `request_user_input` for user questions, never a chat imitation of a popup. Required decisions should invoke native input in Default or Plan mode when exposed; never trust auto-resolved answers. `USER_REQUEST_ARGS` denotes the user-provided invocation text, not a shell variable. Helper paths resolve through the installed `$HOME/.agents/skills/` links; if these links are missing, stop rather than guessing a file location.


> **Codex native user questions (all skills):** Use the actual `request_user_input` tool for every question needing a user answer when available; never simulate an interactive popup using prose or a text multiple-choice list. Default mode should invoke the native tool for choices, including required decisions, when exposed. Invoking a popup is not approval: only a verified explicit user answer satisfies a gate. If the host cannot verify an explicit answer or enforce blocking authorization, leave the gate pending and request Plan mode; if the tool is unavailable, report that fact without an ordinary-chat choice imitation. Empty, missing, timed-out, cancelled, interrupted or automatically resolved responses never count as approval. Preserve the pending decision and persist only a verified explicit answer with available MightyModels MCP tools. This Codex-only contract overrides any later legacy instruction to ask in ordinary chat or use Claude question dialogs.

> **Codex investigation gate:** Required framing, classification, and end-of-round decisions follow the shared Codex required user-input contract above. Offer free-text input in ordinary chat; the legacy Claude question recorder does not run in Codex, so persist real answers through supported MCP tools only.

# lets-investigate

The opening move: understand before anything gets named, ticketed, or built. The session's
product is a ledger, restated in chat at the end of every round, that the user has agreed is
sufficient. The ledger is persisted before every gate by the `investigation_*` tools, so a compaction
or a new conversation resumes from the database instead of from memory; the chat restatement is
the tool's own rendering, so the two cannot disagree.

Read `references/ledger-schema.md` when an entry is rejected.

<important>Invoke `prompting-subagents` before the first dispatch.</important>

The skill runs as a loop with a gate, and the gate is the point. An investigation that runs
until the primary feels done ends up wherever the primary's curiosity went. One that stops after
every round and asks the user whether the picture is sufficient ends up where the user needs
it, and the user hears about a dead end after one round instead of five.

## Round zero: frame the target

**Argument:** what to investigate, given when the skill was started: "USER_REQUEST_ARGS". Empty quotes
mean nothing was given, and the target comes from the conversation.

Write the target as one line the user can disagree with, then work out which of these it is (the
user confirms the classification when the ledger opens):

- **Explain a behavior**: something happens and nobody knows why yet.
- **Check a claim**: someone asserted a fact about the system; find out whether it holds.
- **Research an approach or dependency**: how a library, API, protocol, or tool behaves, and
  how the repository actually uses it.

The classification decides where the first questions go. A behavior needs the code path and
the runtime configuration; a claim needs the exact lines that would make it true or false; a
research question needs the documentation for the version in the lockfile and the call sites
that depend on it.

Before dispatching anything, use blocking native `request_user_input` in Plan mode to ask whether the target line is correct
and what the user already knows or has ruled out. End the turn until the user explicitly
answers; do not treat silence, timeout or an automatic response as consent. Scouts pointed at a vague target return precise answers to the wrong question, and facts
the user already holds cost nothing to record and a round to rediscover.

Once the user confirms the target, open the ledger and record their answers as round 0:

Call `investigation_start` with the `target` line and leave `kind` out: the tool asks the user for
the classification and records the answer. An answer starting `needs input` means no one could
be asked through the tool: use blocking native `request_user_input` in Plan mode for the named classification question; wait for a verified user response, then call again with that actual `kind`. Kind `change` means a proposed change to weigh, which what-we-know opens.
`investigation_start` returns the investigation id, and every later call names it.

The session is pointed at the investigation by the first `investigation_add`,
`investigation_render` or `investigation_knowns` call naming its id; `investigation_start`
does not point it. Codex `request_user_input` answers are not automatically recorded by a Claude
question hook. Record confirmed framing facts as `known` entries from `user` in round 0
with cite `user`, using `investigation_add`, and verify them with `investigation_render`.
The classification belongs to `investigation_start`'s `kind` parameter, not a ledger entry.
For every later explicit choice, use `investigation_add` with an entry of kind `decision`,
source `user`, the user's actual words, and a round at least 1 (latest round if positive;
otherwise 1). Read back via `investigation_render` before advancing; if the write fails,
report the failure and do not claim persistence. Never record silence or defaults as decisions.
`known` and `resource` entries require a `cite`.

When the user is resuming an earlier investigation, `investigation_list` shows the ids and
`investigation_render` restores the ledger.

## Each round

**1. Choose two or three questions the ledger cannot answer.** Take them from the ledger's
Next section (round one takes them from the framing). Route each by where the answer lives:

- Repository facts (definitions, call sites, config values, versions, one command's output, a
  GitHub issue or pull request read) go to code-scout with exact paths, symbols, and search terms.
- External facts (documented behavior, changelog entries, defaults, deprecations) go to a
  web-scout with the URL or the search phrase, the version pinned in the lockfile, and the
  specific question. web-scout fetches and cites the page; it does not summarize a library.
- Facts only the user holds (intent, production observations, history) are held for the gate,
  where they are asked alongside the round's decision.

Shape every scout question as locate, list, extract, fetch, or run. A "why" or "should" bounces
back as `NEEDS-ANALYSIS` and costs a dispatch; that judgment is yours, made in the open and
recorded as a decision only once the user agrees with it.

**2. Dispatch through prompting-subagents.** Scouts have not seen this conversation, so each dispatch
carries the question, the scope, and the citation form wanted back. No ticket exists, so no
`subagent-models` routing applies: scouts run on their agent-file default.

**3. Fold reports into the ledger.** Each verdict has one destination, and each destination
is an entry `kind`:

- `VERIFIED` becomes a `known`, with its `file:line` or `URL#heading` citation.
- `INFERRED` becomes an `open` question stating what the inference rests on. It never becomes a
  Known by being repeated.
- `NEEDS-ANALYSIS` is a judgment call for you. Make it in chat with the evidence in view; it
  becomes a Decision only if the user accepts it at the gate.
- `UNKNOWN-BLOCKED` becomes an Open question carrying the location the scout named. If that
  location is outside the repository and the docs, it is a question for the user.
- Two scouts disagreeing is a finding. Record the contradiction as its own Open question with
  both citations; never reconcile it silently.

**4. Persist, then restate the whole ledger.** Write the round's entries in one
`investigation_add` call, then call `investigation_render`. Each scout wave's `investigation_add`
uses the next `round` number, one above the last: core refuses only a round lower than the latest
and accepts a skipped one.

An answered Open question is retired by the entry that answers it (`supersedes`), never
edited. `supersedes` takes the `e` numbers that `investigation_add` and `investigation_render`
print, naming an entry from an earlier call. Paste the `render` output into chat as the restatement: not a delta, the whole ledger.
If `add` cannot write at all, stop at the gate and say so. A gate on an unpersisted round is the loss this skill exists to
prevent.

**5. Stop at the gate.** Use blocking native `request_user_input` in Plan mode for the round's decision and unresolved questions, at most four per call. Wait for an explicit verified response.
Only then persist the answer as a `decision` entry and verify it by reading the ledger.
Offer exactly these choices:

- **Sufficient**: consolidate through what-we-know.
- **Dig further**: run the Next questions as proposed.
- **Redirect**: the target or the Next questions need changing; the user says how.
- **Stop here**: keep the ledger in chat and end without consolidating.

When you believe the picture is complete, say so in the interactive question and recommend Sufficient,
and still ask. When the Next questions would not change the picture, say that too; a user who
hears "one more round would only confirm what we have" can make a real choice. What you do
not do is skip the gate because the answer seems obvious. Ending someone's triage for them is
how half-understood problems get ticketed.

Do not substitute an ordinary-chat choice list or a nonblocking popup or infer an answer from silence. Never dispatch
another round or consolidate until the user makes an explicit choice.

## The ledger

`render` prints it as Knowns, Open, Decisions, Resources and Next, so what-we-know can lift
Knowns and Open straight into its knowns table and uncertainties list.

Rules that keep the ledger honest:

- A claim with no citation goes in Open. ("The retry wrapper is applied everywhere" with no
  line is not a Known.)
- A Decision carries the user's confirmed words, not an inferred approval. In Codex,
  explicitly persist each gate answer with `investigation_add` as kind `decision`, source
  `user`, and verify it with `investigation_render` before moving on. The initial framing
  facts belong as `known` entries in round 0. Your conclusion remains a Known or Open
  item until the user explicitly decides.
- Resources record where facts came from so open-ticket can name them in the issue and the
  next session does not re-find them. A fetched docs page goes here with the version it
  describes; a docs page for the wrong version is a Resource with a warning, not a Known.
- The ledger stays readable in one screen. When it grows past roughly forty lines, merge
  Knowns that say the same thing (one new entry superseding both), retire Open questions the
  user has waved off (a Decision superseding them), and supersede Next items the user has
  redirected away from. Growth
  past that point means the investigation is sprawling, which is itself something to say at
  the gate.

## Research targets

A research question is answered by two facts joined together: what the documentation says for
the version the repository resolves, and where the repository depends on that behavior. One
without the other is trivia. So a research round usually pairs one web-scout with one
code-scout: web-scout fetches the page for the pinned version and cites the section;
code-scout cites the lockfile line and the call sites. Prefer primary sources, in this
order: the project's official documentation, its changelog or release notes, the dependency's
own source at the resolved version. A blog post or forum answer is a lead that names where the
primary source is, not a citation.

## Ending

The loop ends only at a gate. On Sufficient, offer what-we-know and hand it the investigation
id; never invoke it unasked. On Stop here, leave the final rendered ledger as the last message;
the database keeps it for a later session.

## Boundaries

Read-only apart from the ledger rows: no other writes, no edits, no commands beyond
the `investigation_*` tools and the single read-only command a scout runs. If the investigation surfaces something needing immediate
action (a live secret, a data-loss path in production), say so plainly and let the user act;
the pipeline is for work, not for emergencies.

## Example round

Target: `Explain a behavior`: the retry queue drains at roughly a tenth of its configured rate
after 2am.

Round 1 dispatches a code-scout for the drain loop's definition and its concurrency
setting, a code-scout for every reader of `RETRY_CONCURRENCY`, and a web-scout for the
queue client's documented default backoff at the version in `uv.lock`. The reports come back
`VERIFIED`, `VERIFIED`, and `INFERRED` (the docs page found is for a newer major version). The
ledger restates with two Knowns, one Open ("documented backoff for 3.2.x: rests on a 4.x page;
answer lives in the 3.x changelog"), one Resource carrying the version warning, and a Next
section proposing the 3.x changelog fetch and a code-scout to run the drain loop's unit test once.
The gate asks the user to choose, and adds the held question: "does the slowdown correlate
with the nightly compaction job you mentioned?" The user picks Dig further and answers yes;
both land in the ledger as `user, round 1` entries before round 2 dispatches.
