# MightyModels Codex port — status and installation

The port provides native Codex definitions for **11 enabled agents** (from 12 Claude source roles; Fable/wingman is disabled), **19 skills**, and a
local **35-tool MCP server**. Claude support is retained. It is **experimental**:
static tests and one live read-only subagent test do not establish complete
dispatch authorization or end-to-end workflow equivalence.

## Verified installation and bounded CLI smoke — November 8, 2026

A user-supplied, unprivileged Debian Codex CLI 0.167.0 run after updating to
`main` at `ddbd9f4` established the following:

- `install_codex_user.py` completed without an installation error.
- `codex_doctor.py` reported 11/11 owned native agent registrations, 19/19
  installed skill links, enabled global `mighty_mcp`, an available `uv` launcher,
  and structurally recognized global hooks.
- `sync_codex_agents.py --check` and `sync_codex_skills.py --check` passed.
- `codex mcp list` reported the `mighty_mcp` launcher enabled. This is not proof
  that a particular MCP request or lifecycle callback was executed.
- `codex_live_acceptance.py --live --timeout 90` returned
  `read_only_smoke_completed` in an unrelated disposable Git repository, with
  `fixture_unchanged: true`, one completed turn, and no retained secret transcript.
  The probe reported 39,961 input tokens and 65 output tokens for this run; those
  figures are not a model-to-model quota comparison.

The doctor also emitted `Project-scoped MCP config has unexpected shape`.
That warning was caused by the repository intentionally omitting the optional
`mcp_servers` table in its project config, not by a demonstrated duplicate
server. This case is addressed by PR #85; the observed host output itself is
retained as historical evidence.

**Not verified:** actual hook delivery or trust, MCP tool execution in that
particular run, user-decision persistence, scout handback, resume/compaction,
host-level dispatch admission, child-agent identity or sandbox isolation.
The smoke requests read-only access and compares its disposable fixture; it
is not a proof of global filesystem isolation or host enforcement.

Codex documents `SessionStart`, `PreToolUse`, `PostToolUse`,
`SubagentStop` and `PreCompact` hook events, including local MCP tool
coverage. Configuration support is not evidence that this installation
delivered those events; test that separately in unrelated repositories.
See https://learn.chatgpt.com/docs/hooks for the current host contract.

## Verified Default-mode question and decision persistence — November 9, 2026

User-provided Codex CLI v0.167.0 transcripts from a disposable unrelated
repository demonstrate two native `request_user_input` questions in Default
mode, with explicit answers `Confirm target` and `Continue testing`.
`mighty_mcp.investigation_start` created
`20261109-verify-native-codex-user-decisions`; `investigation_add` saved
`e1: Continue testing (user, round 1)`, and `investigation_render`
returned the same decision. In a separate new Codex session,
`investigation_list` and `investigation_render` recovered the same ID,
target, entry, source and round without rewriting or re-asking.

These results **verify explicit MCP decision persistence and cross-session
read-back**, not automatic hook-backed recording. Both question calls emitted
a hook warning that the response was not automatically persisted; the
explicit MCP fallback succeeded. `SessionStart` pointer injection,
compaction/resume, duplicate-event idempotence and full workflow lifecycle
remain unverified under issues #8 and #14. The unrelated read-only scout
test is not proof of host-level admission denial (issue #9).

## Observed live results — Debian 13, Codex CLI 0.167.0 (November 2026)

**Historical observations, not current end-to-end acceptance.** Static checks and CLI discovery do not demonstrate host-enforced dispatch denial, read-only scout isolation, actual spawned-agent model identity, automatic hook-based decision recording, or complete lifecycle behavior. Track these separately under issues [#9](https://github.com/sethbarrett50/mightymodels_codex/issues/9), [#8](https://github.com/sethbarrett50/mightymodels_codex/issues/8), [#14](https://github.com/sethbarrett50/mightymodels_codex/issues/14) and [#16](https://github.com/sethbarrett50/mightymodels_codex/issues/16).

The separate, unprivileged `codex` user on Debian 13 successfully:

- Installed uv 0.13.7 with Python 3.14 and cloned this repository.
- Passed the generator check in an earlier state (12 Claude sources; currently 11 enabled Codex roles and 19 skills).
- Discovered 12 roles and 19 skills in an earlier session **before Fable/wingman was disabled**; the current 11-role registry has not been host-verified.
- Connected to `mighty_mcp`; 35 tools were listed. A real
  `investigation_list({})` request reached the server, but state reads returned
  "no repository is recorded" because no write unit of work had registered it.
- Ran the native `mm-triage-code-scout` agent to inspect MCP registration code;
  the agent finished and reported the nine registrars.
- Created `~/.local/share/mightymodels/state.db` and an MCP log.
- **Did not establish** that `PreToolUse` blocked unauthorized dispatch or that
  `SubagentStop` persisted the scout report. No implementation workflow ran.

The scout's `/root/...` agent identifier is a coordinator hierarchy identifier;
the OS account was verified as UID 1002 (`codex`), not Linux root.

## Native agent instructions (issue #14)

The generated `.codex/agents/mm-*.toml` role bodies translate supported
Claude-specific tool names into the corresponding Codex interactions:
`exec_command` for file/shell inspection, `apply_patch` for changes, and
`spawn_agent` for permitted delegation. Native roles are referred to by
their full `mm-` names. References claiming MightyModels skills are
automatically preloaded have been replaced with instructions to read the
installed skill's `SKILL.md` explicitly under `$HOME/.agents/skills/`.
The original `agents/**/*.md` definitions remain unchanged.

This mapping is a **textual runtime translation**, not host-enforced permissions:
the source `tools`, `skills`, `maxTurns`, and other Claude frontmatter
fields remain documented as unmapped in the compatibility report. Custom
Codex agents inherit the parent's sandbox and approvals. The agent can only
use native tool operations that are actually exposed in its current session;
if unavailable, it must stop rather than silently fall back to a different
tool or unregistered agent. Live workflow acceptance is still required.

### Opt-in native question hook diagnostics (issue #8)

The Codex question recorder intentionally accepts Plan-mode answers only.
Default-mode `request_user_input` has been observed working interactively,
but the available post-tool event has not yet been proven to distinguish
an explicit user selection from an auto-resolved response. Do not delete
the Plan-mode restriction merely to suppress the warning.

To collect a **sanitized hook receipt** from a fresh Codex session without
logging prompts, answers, session IDs, working-directory paths or MCP state,
opt in using a private on-disk marker:

```sh
install -d -m 700 ~/.local/state/mightymodels
install -m 600 /dev/null ~/.local/state/mightymodels/codex-question-probe.enabled
cd /path/to/disposable-repo
codex
```

The private marker is preferred over `MIGHTYMODELS_CODEX_QUESTION_PROBE=1 codex`
because a Codex host may not propagate the shell environment to hook
processes. An absent, symlinked, foreign-owned or non-0600 marker does not
enable the probe. The existing environment-variable opt-in remains supported.

Invoke one native `request_user_input` question. After exiting Codex, read
the receipt and **disable the marker**:

```sh
cat ~/.local/state/mightymodels/codex-question-probe.log
rm -f ~/.local/state/mightymodels/codex-question-probe.enabled
```

If the receipt remains absent, that does not prove hook delivery failed:
inspect hook trust and whether the host executed the configured script.

The probe writes only a fixed event label, tool label, whitelisted permission
mode and boolean presence/type checks (`input_questions`, `response_object`,
`answers_object`, `timeout_field`), with file mode 0600. Presence of an
`answers` object is **not proof of explicit user consent**. This opt-in
probe is not a substitute for the explicit-answer MCP fallback, and cannot
automatically authorize any pending decision. Remove the log after the test
if no longer needed. Do not paste raw Codex transcripts or secret prompts.

### Opt-in lifecycle delivery receipts (issue #8)

To establish whether the host actually delivered `SessionStart` and
`PreCompact`, enable a *private* local marker before launching Codex.
The hook logs only whitelisted event names and a whitelisted lifecycle
source; it never stores session IDs, paths, prompts or persisted records.

```sh
install -d -m 700 ~/.local/state/mightymodels
install -m 600 /dev/null ~/.local/state/mightymodels/codex-lifecycle-probe.enabled
cd /path/to/disposable-repo
codex
```

For a bounded acceptance, start Codex once, exit and resume that specific
session, then read and remove the probe marker:

```sh
cat ~/.local/state/mightymodels/codex-lifecycle-probe.log
rm -f ~/.local/state/mightymodels/codex-lifecycle-probe.enabled
```

A receipt `event=SessionStart source=resume` proves the Codex bridge
received that event; it does **not** alone prove successful pointer
recovery. With this marker enabled, `event=SessionResumePointer hint=present`
means the bridge returned a bounded persisted pointer hint; `hint=absent`
means no hint was returned, and `hint=warning` means the handler reported a
failure. These sanitized receipts contain no pointer identifiers or answers.
Even `hint=present` does **not** alone prove the Codex host injected the
context into its model; verify that separately in the resumed session.
Validate the resumed pointer separately by reading the exact MCP record, without reconstructing its value from chat. `PreCompact`
delivery requires an actual compaction event. A missing log is
inconclusive until hook trust, matcher and marker ownership are checked.
This probe never changes MCP state or authorization decisions.

### Registered-repository prerequisite for pointer acceptance

A new disposable Git repository has **no MightyModels repository record**.
Read-only MCP calls such as `investigation_list` can fail with
`no repository is recorded ... a write unit of work records it on first use`.
This is expected: investigations and session pointers are repository-scoped;
the investigation ID from a previously registered checkout must **not** be
assumed visible in a new checkout.

A bounded real-host test must use a fresh disposable Git checkout and
explicitly authorize one `mighty_mcp.investigation_start` write *in that
checkout*, supplying a target and kind to avoid interactive questions.
Read the returned investigation ID from the actual tool result, then call
`mighty_mcp.investigation_render` with that **new** ID. The render's named
`investigation_id` input is what permits the Codex `PostToolUse` bridge
to establish a session pointer; the returned ID from
`investigation_start` by itself cannot do so. Do not assume that a failed
tool call, `investigation_list`, or unrelated session history recorded
a pointer. Exit normally and resume the **same Codex session ID** in the
same checkout with the private lifecycle marker enabled.

Expected evidence is all of: the start returned an ID, render succeeded,
the log contains `event=SessionStart source=resume` and
`event=SessionResumePointer hint=present`, and the resumed host independently
reports seeing `MightyModels persisted active investigation:` in injected
SessionStart context *before* any MCP reads. The sanitized `hint=present`
receipt proves the bridge returned a hint, not that the host injected it.
`hint=absent` after an unregistered-repository read failure is a missing
precondition, **not** a pointer-restoration defect. Never auto-resolve pending
choices or run dispatch/security probes as part of this test.

### Session resume pointer fallback (issue #8)

The Codex `SessionStart` bridge uses a read-only persisted session pointer
lookup for the host's `resume` and `compact` sources. When a valid, unexpired
ticket or investigation pointer exists, it returns bounded `additionalContext`
with the reference and directs Codex to reread the latest state using
`mighty_mcp`. It never reconstructs missing decisions, treats auto-resolved
questions as consent, or prints stored answers. Initial startup continues to
prune stale pointers. A missing or expired pointer produces no invented state.

### Live issue #8 acceptance checkpoint — 2026-11-09

**Verified on Codex v0.167.0:** The host received startup and resume
`SessionStart` events in a disposable, registered Git repository. A real
`investigation_start` returned an ID and a successful named
`investigation_render` established a pointer. After resuming the exact
Codex session, the private lifecycle receipt recorded
`event=SessionResumePointer hint=present`; before any MCP reads, the
resumed host explicitly observed the persisted investigation ID in injected
`SessionStart` context. This verifies the real pointer injection pathway,
not merely the generated hook output.

**Separately verified:** In a disposable ticket repository, the live host
accepted repeated `task_declare(T1)`, rejected a duplicate
`task_start(T1)` with no extra attempt, and preserved the `in-progress`
task and `engineer` attempts=1. After exact-session resume, two
`task_show` and two `ticket_show` MCP read-backs matched and retained
the explicit ticket-context handoff marker. No agent was dispatched.

**Still unverified for #8:** full `baton-pass` snapshot/BATON.md workflow,
scout handback/`SubagentStop` delivery on the real Codex host, and
pending user decisions across an interrupted workflow. The earlier
native-question tests must not be mistaken for explicit human authorization.
Host dispatch admission/security acceptance is separately deferred in #9.
Neither milestone completes #14 full native workflow acceptance or #16
effective model and quota measurements.

This distinction is intentional: successful hooks and durable MCP records
do not prove the remaining full-workflow transitions.

### Project-only post-edit Python checks (issue #17)

The MightyModels checkout's `.codex/hooks.json` also declares a
`PostToolUse` hook for `apply_patch`. Its standard-library helper inspects
only successfully applied patch targets inside this source checkout, selects
existing nonsymlinked Python files, and invokes the already-installed local
`.venv/bin/ruff` with `format --check` and `check --no-fix`.
It does **not** install packages, contact a registry, run a formatter that
writes files, touch another Git project, or reproduce source/error text in
hook output. It reports a brief warning and directs the user to `make check`
if either check fails or Ruff is unavailable.

This is best-effort read-only feedback, not automatic formatting, `ty`
coverage, proof that a Codex host delivered `PostToolUse`, or a global
plugin requirement. The existing project PreToolUse suppression/lockfile
guard remains separate. Until host delivery is confirmed, run
`make format` (mutating) and `make check` (validation) explicitly.

For quota-aware reset testing, see [Codex live acceptance after usage resets](CODEX-LIVE-ACCEPTANCE.md). The `--preflight` mode uses no Codex inference, and `--live` runs one bounded smoke without retries. The runbook separates host-dependent follow-up evidence from static CI and keeps issue #9 deferred.

## Source, enabled and reported roles

The source tree includes 12 original Claude roles. The native Codex generator emits 11 enabled roles and deliberately omits Fable/wingman. `.codex/compatibility-report.json` counts the **12 source roles**, including the disabled one: its `count` is not the enabled-install count. All 19 skills have Codex-specific generated equivalents. Run `python3 scripts/sync_codex_agents.py --check` and `python3 scripts/sync_codex_skills.py --check` for generation drift; these checks are not live host acceptance.

### Duplicate Codex role discovery — live host finding

A November 8, 2026 Codex 0.167.0 live read-only MCP test successfully called
`mcp__mighty_mcp__investigation_list` but emitted two duplicate-name warnings
per each of the 11 `mm-*` roles. The user confirmed 11 explicit global role
registrations, 11 corresponding user-global agent symlinks, and 11 source
agent files in the project checkout. The installer now retains the explicit
global `config_file` registrations and removes the redundant managed global
symlinks on reinstall, preserving the per-agent model and effort settings.
The doctor rejects a still-duplicated user-global role file. **Host startup
without duplicate warnings is not yet verified** and must be retested after
reinstall. Unmanaged agent files are never deleted by this migration.

## User-scoped installation across repositories

Run this as the unprivileged Linux user that will launch Codex. Do not use sudo
or place GitHub PATs inside the MightyModels checkout.

```sh
cd ~/code/mightymodels_codex
uv sync --locked --no-dev
python3 scripts/install_codex_user.py
codex mcp list
```

The installer registers all 11 enabled roles explicitly in the managed global
`~/.codex/config.toml` section (referencing their checkout TOML files), and
symlinks 19 skills into `~/.agents/skills/`. It removes only obsolete
installer-owned role symlinks in `~/.codex/agents/` to avoid duplicate global
agent discovery. The project-local `.codex/agents/` definitions remain as
source files. It adds a clearly marked `mighty_mcp` section
to `~/.codex/config.toml`, installs absolute-path hooks at
`~/.codex/hooks.json`, and adds a managed instruction stanza in
`~/.codex/AGENTS.md`. It refuses to overwrite unrelated files and does not
modify sandbox, approval, model, or network settings. It can be rerun.

```sh
python3 scripts/install_codex_user.py --uninstall
```

Uninstall removes only owned links and managed stanzas. It preserves Codex
authentication, unrelated configuration, all user repositories, PAT files, and
the MightyModels state database. Keep this checkout at its installed location;
reinstall after moving it. Restart Codex after installing or uninstalling.

**Caution:** Codex may require explicit trust for newly installed hooks; hooks
being present on disk is not evidence they executed. The installer now safely
merges exact MightyModels event groups into an existing valid global hook file
without deleting unrelated event definitions. It refuses malformed JSON,
symlinked hook manifests, duplicate managed groups and unexpected commands
that resemble a modified MightyModels bridge. Uninstall removes only its
recognized groups while keeping foreign hooks. A hook file carrying unrelated
top-level metadata is never replaced by a template or deleted just because
its recognized MightyModels hook groups are gone. The doctor also rejects
duplicated managed event groups rather than calling such an installation healthy. This is a structural merge,
not a guarantee that Codex loads, trusts or executes both hook sources.

### Invoking MightyModels skills from Codex

Codex skills use a dollar-sign prefix, rather than the original Claude
slash-command syntax. A user running Codex CLI v0.167.0 in a disposable
repository reported the namespaced prompt form `$mightymodels:lets-investigate`.
That observation establishes the entered command form, not that the entire
investigation workflow executed. The generated manifest names are
`lets-investigate`, `open-ticket`, `game-plan`, and so on; try
`$lets-investigate` if the namespaced form is not discoverable.

Use `/skills` to inspect the menu in the running host before assuming a
particular invocation is available. Examples:

```text
$lets-investigate Why does this test fail?
$open-ticket
$game-plan
$agents-assemble
$review-circus
$baton-pass
```

`python3 scripts/codex_doctor.py` checks that all 19 installed global
symlinks point to generated skill directories and each manifest has a
matching name. This is structural validation only: it cannot prove the
running Codex host loaded a skill, resolved a namespaced alias, invoked
an MCP tool, or enforced permissions. Verify discovery interactively
in an unrelated repository before claiming host-level compatibility.

### Per-repository workflow

```sh
cd ~/kc/YOUR_REPO
codex mcp list
codex
```

In the interactive session, ask Codex to list the *registered* `mighty_mcp`
ticket/task tools and delegate a **read-only** scout. Compare with the actual
tools and agent event trace, not just configuration files.

The MCP launcher now keeps the target repository working directory while
loading the MightyModels Python package from this checkout. Repository state is
distinct from the plugin source tree. If the host starts MCP from a different
directory, confirm its reported repository identity before writing state.

## Source checkout mode

From the repository root, install Python >=3.14 and uv, run
`uv sync --locked --no-dev`, then start `codex`. The checkout includes its
own `.codex/config.toml`, local agent definitions and skill links. Do not
run a second duplicate MCP server unintentionally when user-level installation
is active; prefer the user-scoped setup when working across repos.

## Adaptation and safety limitations

- Original Claude definitions live in `agents/**/*.md`. Generated TOML files
  set names, instructions and reasoning effort, but do **not** enforce Claude
  model aliases, `maxTurns`, tool restrictions or automatic skill preloads.
- Codex native delegation replaces Claude's Agent / SendMessage tool names.
  Resolve MCP calls to exposed `mighty_mcp` tools. Never guess tool names.
- Read-only instructions are **not a filesystem sandbox**. Parent permissions
  apply to children.
- The hook adapter converts Codex spawn events into the original admission hook,
  but disabled, untrusted or differently-shaped hooks may bypass the guardrail.
  Verify actual blocked dispatches before write-capable use.
- SubagentStop and PreCompact adapters are implemented; SessionStart and
  PostToolUse state-pointer handling remains unmigrated.

## Remaining live acceptance tests

1. In an unrelated scratch repo, confirm all global agents, skills and MCP
   tools appear, and a read-only scout completes.
2. Verify a missing/invalid started task causes a **real host-level denial** of
   `mm-workers-engineer` delegation. Do not substitute a prompt-only refusal.
3. Verify a valid scoped engineer task, owned-file check, independent
   fact-checker, persisted verdict and three-failed-fix ceiling.
4. Verify scout write prevention using actual sandbox permissions.
5. Verify SubagentStop evidence, compaction, resume, session state and user
   approvals, then test installed-plugin mode separately.
6. Validate GitHub/Jira writes through properly scoped approved tooling.

The project is not production-ready until these acceptance checks pass.

## Native interactive user questions (Codex CLI)

MightyModels requires the **real** Codex `request_user_input` interactive
question tool for questions directed to the user. A plain chat message listing
choices is not an interactive question and must not be presented as one.

The optional Default-mode input tool can be enabled in the user's
`~/.codex/config.toml` (preserve existing settings):

```toml
[features]
default_mode_request_user_input = true
```

Restart Codex and inspect `codex features list`, then verify the tool is
actually available in the running session. The MightyModels installer does
not modify this user preference.

**Native question presentation** and **authorization to proceed** are
separate. For any multiple-choice question, including a required workflow
decision, invoke `request_user_input` when exposed in Default or Plan mode.
Do not suppress the interactive UI merely because the session is in Default
mode. The Default-mode feature flag enables optional native questions, but
its prompts may auto-resolve and cannot by themselves guarantee a blocking
approval gate. A required decision is satisfied only by a verified explicit
user answer, never by a default, cancellation, timeout, missing response,
or a claim that a popup was shown.

When a required decision cannot be safely verified or blocked in Default
mode, leave it pending and instruct the user to switch to Plan mode for a
blocking `request_user_input` interaction. If the native tool is unavailable,
report that limitation without presenting a plain-text choice list as a
popup. Never continue dependent work on an unverified selection.

Only a verified, explicit user answer may be persisted in MightyModels
MCP state. Tool failure, timeout, cancellation, empty replies, auto-resolution
and interrupted sessions are not permission to proceed. Existing pending
decisions remain pending across resume/compaction. The original Claude
`AskUserQuestion` recorder does not run in Codex; use supported MCP writes
and read-back verification instead.

The `request_user_input` schema is controlled by the host. Do not invent
`autoResolutionMs` or `isBlocking` arguments, and never promise a
Default-mode question will remain open indefinitely.

### Global instructions under `~/.codex/AGENTS.md`

The installer manages a stanza pointing to this repository's `AGENTS.md`.
Keep it intact and update the repository checkout; do not append a duplicate
managed stanza. The shared policy overrides older generated skill instructions
that suggest ordinary-chat choice lists for Codex gates.

## Troubleshooting named scout dispatches

A custom role may be listed in an agent TOML file but rejected at runtime with
`agent type is currently not available`. This is a **Codex agent registration
error**, not the normal MCP repository-registration response or an authorization
denial. The global installer now registers each of the 11 enabled roles explicitly in
user `~/.codex/config.toml` via `[agents."mm-..."]` with an absolute
`config_file` path. The source TOML and its instructions remain in
`~/.codex/agents/` and the MightyModels checkout.

After pulling the updated checkout, run `python3 scripts/install_codex_user.py`,
close all old Codex sessions and launch a **fresh** Codex session in the target
repository. Validate a read-only `mm-triage-code-scout` dispatch before resuming
a persisted investigation. The installer checks for unrelated custom role
definitions and refuses to overwrite them. If a freshly started Codex session
still returns this error, collect the actual `spawn_agent` result and
`codex --version` and treat it as an outstanding host compatibility issue.
Do not substitute a generic agent while claiming a named MightyModels scout
ran, and do not relax admission hooks to workaround registry errors.

## Cost-aware native agent routing (issue #6)

| Original Claude tier | Configured Codex tier | Validation |
| --- | --- | --- |
| Haiku | `gpt-6-luna`, medium | Generated; effective model unverified |
| Sonnet | `gpt-6.1-sol`, medium | Generated; effective model unverified |
| Opus | `gpt-6.1-sol`, high | Generated; effective model unverified |
| Fable/wingman | None (disabled) | Escalate decisions to the user |

This documents configured roles, not actual model dispatch or quota savings (issue #16).

Codex roles are generated from the original Claude role tiers. Haiku maps to
`gpt-6-luna` at medium effort (six focused retrieval/mechanical workers).
Sonnet maps to `gpt-6.1-sol` medium (engineer and Terry).
Opus maps to `gpt-6.1-sol` high (architect, merge-vader and uncle-bob).
The Fable-tier wingman is **not generated or installed for Codex** and is
blocked by the dispatch adapter. Its Claude source remains untouched; no
Astra or other premium replacement is selected.

These explicit per-agent model settings prevent ordinary inheritance of the
coordinator's selected model. Model availability depends on the user's Codex
account and CLI: confirm `/model` and test a named Luna scout plus a Sol
worker before declaring live routing validated. An unavailable model must not
silently fall back to the expensive parent. Higher reasoning consumes more
tokens; don't claim a fixed usage reduction without a representative benchmark.
Re-run `python3 scripts/install_codex_user.py` after upgrading and restart
Codex to refresh its agent definitions. The global installer now enables 11
Codex roles and still exposes all 19 skills, some of which may refer to the
unavailable wingman; those paths must block rather than dispatch it.

OpenAI references:
https://learn.chatgpt.com/docs/agent-configuration/subagents
https://learn.chatgpt.com/docs/models?surface=cli

## Codex live dispatch authorization probe — issue #9

The managed `PreToolUse` matcher now covers `spawn_agent`, `Agent`, and
namespaced forms such as `collaborationspawn_agent`. This addresses a
reported multi-agent v2 hook-name mismatch (openai/codex#57539).
Re-running the user installer replaces the exact previous MightyModels matcher
while preserving unrelated user hooks. **Matcher coverage does not imply host
invocation or enforcement**; some Codex versions have reported that native
spawn bypasses `PreToolUse` entirely (openai/codex#49736).

**Safety status: NOT host-verified.** A direct invocation of
`hooks/codex_bridge.py` proves only that its Python logic runs, not that
the Codex host invokes it before native `spawn_agent`. An upstream Codex
report describes `spawn_agent` bypassing `PreToolUse`, allowing an agent
to start without consulting a deny hook:
https://github.com/openai/codex/issues/49736

A scoped opt-in audit marker helps distinguish an installed hook from a
**live host hook invocation**. It contains only a constant event label and
timestamp, never a prompt, argument, role name, token or repository content.
It is OFF by default, and written under the Codex user's private
`~/.local/state/mightymodels/codex-dispatch-probe.log`.

In an unprivileged `codex` shell:

```sh
export MIGHTYMODELS_CODEX_DISPATCH_PROBE=1
rm -f ~/.local/state/mightymodels/codex-dispatch-probe.log
cd ~/kc/kc-backend-core  # or a disposable test repo
codex
```

In that **new** session, ask for a single read-only
`mm-triage-code-scout` to list the repository's top-level filenames.
Exit, then check:

```sh
if test -s ~/.local/state/mightymodels/codex-dispatch-probe.log; then
    grep -E '^(pre_tool_use_spawn_agent_seen|adapter_denied|adapter_no_denial) ' \
      ~/.local/state/mightymodels/codex-dispatch-probe.log
else
    echo 'UNVERIFIED/UNSAFE: no native spawn_agent PreToolUse event was observed'
fi
unset MIGHTYMODELS_CODEX_DISPATCH_PROBE
```

Bridge error responses intentionally include only static denial categories and numeric
subprocess exit codes. They never echo failed-hook stderr, exception text,
unknown role strings, or malformed raw event payloads, because those may
contain secrets. Collect separate local diagnostics only with an appropriate
private log review; never attach raw hook transcripts to public issues.

The opt-in log now distinguishes `pre_tool_use_spawn_agent_seen` (the bridge
was invoked), `adapter_denied` (the bridge prepared a denial) and
`adapter_no_denial` (the bridge did not issue a denial). These are **adapter
observations only**, not proof that Codex respected the decision or that an
agent failed to launch. The log never includes role identifiers or messages.

**Do not test with a destructive command or an unauthorized live write.**
The next acceptance test should be a benign attempted engineer dispatch
without a started task, requiring a real host-level denial before declaring
the gate reliable. Even a marker plus a deny on one CLI version cannot
guarantee protection when hooks are untrusted, disabled or bypassed, and
Codex custom subagents inherit the parent's sandbox. A scout instructed
'read-only' is NOT a separate sandbox; run read-only investigations with a
read-only parent permission mode where possible, and do not rely on an
advisory restriction as security enforcement. This is a bounded diagnostic,
not a workaround that relaxes the gate.

## Codex session lifecycle restoration — issue #8

Codex `SessionStart` now invokes a pruning-only handler, avoiding Claude's
`CLAUDE_ENV_FILE` requirement. Codex `PostToolUse` responses from
`mcp__mighty_mcp__*` invoke the existing session-pointer handler to connect
the session with the most recently used ticket or investigation. The adapter
now sends only the session, checkout, MCP tool name and recognized pointer
fields (`slug`, `ticket`, `investigation_id`). Original MCP responses,
unrelated tool arguments and arbitrary event metadata are discarded rather
than copied to the state helper. Neither hook
prints credentials or logs raw MCP payloads. These records support later
compaction and handoff, and preserve Claude's existing `session-start`
export functionality in its own runtime.

The Codex PostToolUse adapter also handles `request_user_input` responses,
**only in Plan mode** when an actual nonempty answer, question ID/text and
session ID are present. The translated result reaches the existing
`ask-recorder` decision ledger; empty/timeout/malformed responses, secret
questions and Default-mode auto-resolved questions do not become approvals.
Even an explicit `afkTimeoutMs: null` field is treated as a timeout-marked
response and cannot satisfy a required decision.
The adapter forwards only the session ID, checkout directory and
nonsecret question/answer pairs; raw choices, skipped secret questions,
transcript metadata and other original tool fields are discarded. A missing
checkout directory prevents forwarding to avoid an accidental wrong-repository
ledger write.
A warning is returned when no eligible response can be recorded. For a
required decision, a session in Default mode should still invoke the native
question tool when exposed; if a blocking and explicit answer cannot be
verified, the gate remains pending and the user must switch to Plan mode. Neither
a prose-only choice list nor claiming a popup opened counts as tool invocation.
A confirmed response must still be persisted and verified through supported
MCP tools before dependent work advances.

**Important limitations:** hook trust, event presence and the actual
Codex session identifier need real-host verification. An adapter calling
`ask-recorder` does not guarantee a database write: the session must
already have a valid ticket/investigation pointer, and the repository must
be registered. The session-pointer handler only records tool calls whose
inputs identify the target; a bare `investigation_start` response is not
automatically linked until a subsequent named investigation call. Idempotency,
replay behavior, compaction/resume and a genuinely blocked user approval
require real-host acceptance under #8. No response or timeout grants consent.

## Use existing GitHub CLI credentials without exposing secrets (issue #12)

When the `codex` Unix user needs to read Kart-Chaser or other repositories,
first check its existing GitHub CLI session:

```sh
gh auth status -h github.com
gh api user --jq .login
gh repo view OWNER/REPO --json nameWithOwner
```

GitHub CLI commonly keeps its configuration at
`${XDG_CONFIG_HOME:-$HOME/.config}/gh`. This location may include
`hosts.yml`, whose contents can contain PATs. **Treat it as sensitive.**
Use `gh`'s credential management; never read, print, grep, paste, upload,
persist or log raw token material. Never access a different Linux account's
configuration with sudo or copy a user's GitHub token to another account.

To check whether a token environment variable is present without printing it:

```sh
python3 - <<'PY'
import os
for key in ('GH_TOKEN', 'GITHUB_TOKEN'):
    print(key, 'set' if os.environ.get(key) else 'unset')
PY
```

A scoped GitHub command may still need additional approval, authentication
or repository authorization. A failed read does not mean there is no PAT;
a successful read does not authorize unrelated writes. Preserve GitHub
scopes and sandbox/approval boundaries. For missing credentials, ask the
user to use `gh auth login` or the approved credential connector; never
request a token be pasted into the conversation.

### Updating an existing global Codex hook installation

After lifecycle hook changes (issue #8), an older MightyModels-owned
`~/.codex/hooks.json` may contain only the previous PreToolUse,
PreCompact and SubagentStop events. The installer now accepts an existing
manifest only when every defined event matches exactly the current
MightyModels-owned definition. It can then replace that owned subset with the
new version (which adds SessionStart and PostToolUse). It **still refuses** a
symlink, a changed hook or an unrelated event; never remove another tool's
hooks to force installation. This is an intentionally narrow upgrade
compatibility measure. Full coexistence with unrelated hooks, crash-safe
multi-file rollback and duplicate-configuration diagnostics remain under
issue #15. Restart Codex and re-review changed hook trust hashes.

## Generated Codex-only skill files — issue #14 (first migration slice)

The original 19 `skills/*/SKILL.md` remain Claude-compatible and untouched.
Run `python3 scripts/sync_codex_skills.py` after changes to those sources,
then `python3 scripts/sync_codex_skills.py --check` (also enforced by Codex CI).

Codex reads separately generated `.codex/skills/<skill>/SKILL.md` files.
The generator strips Claude-only `allowed-tools` frontmatter, normalizes
MCP tool identifiers, translates legacy helper-file locations into paths
under `$HOME/.agents/skills`, and clarifies native user decisions and
subagent delegation. Original companion directories (`references`,
`scripts`, `assets`, and `evals`) remain available by symlink without
copying or changing them. The user-scoped installer migrates its previously
owned `~/.agents/skills/<name>` symlinks to these generated skill
directories. Project-scope links in `.agents/skills` also point there.

The generator also rewrites legacy Claude `CLAUDE_PLUGIN_ROOT` prose and
Claude-only model-alias instructions in the affected workflows so the Codex
copies reference installed skill links and native role model configuration.
The original Claude skill sources are unchanged.

This is an **initial transport-level translation**; it does NOT make the
Codex host enforce Claude `allowed-tools`, `maxTurns`, or automatic
skill preloads. Required decisions remain fail-closed. Certain multi-agent
Claude-specific workflows and live runtime compatibility still require
testing before claiming full parity with Claude; issue #14 stays open.

## Read-only Codex install doctor — issue #15 (diagnostic slice)

After updating or moving the MightyModels checkout, run as the unprivileged
`codex` account:

```sh
cd ~/code/mightymodels_codex
python3 scripts/install_codex_user.py
python3 scripts/codex_doctor.py
```

The doctor checks ownership and targets of the global MCP registration,
11 native agent role entries, 19 generated Codex skill symlinks, and the
managed global hook manifest. The checkout does not register a duplicate
MCP server or global lifecycle/dispatch hook events. Its project-specific
`.codex/hooks.json` is limited to `apply_patch` edit hygiene; the user-level
installer owns MCP and lifecycle hooks. The global hook source is at
`hooks/codex-global-template.json`. Plugin-mode hooks at
`hooks/codex-hooks.json` are still distinct from global mode; do not enable
both installations without verifying host precedence and duplicate delivery.
A nonzero exit indicates a missing or unexpected installed component.

The doctor makes **no writes**, does not run agent dispatches, and never reads
`~/.config/gh`, token files or credential values. It does not establish that
hooks actually fired or were trusted, or that scouts were sandboxed.
Remaining crash/power-loss transactionality, mixed-hook upgrade edge cases,
plugin-vs-global precedence, and live host enforcement stay open under #15/#9.

## Opt-in disposable live Codex smoke — issue #16

For a bounded read-only Codex host smoke test, run this on the actual
unprivileged Codex account after installing MightyModels:

```sh
cd ~/code/mightymodels_codex
python3 scripts/codex_live_acceptance.py --live --timeout 90
```

The opt-in runner creates and removes a disposable Git fixture, calls
`codex exec --json --sandbox read-only`, and reports only a sanitized Codex
CLI version, event/tool counts and numeric token usage. It also compares the
names, file types and SHA-256 digests of every path outside the temporary
`.git` directory before and after the run. A changed fixture makes the
result unverified rather than successful; no filenames or content hashes are
included in the printed report. This establishes only that this disposable
fixture's final filesystem state is unchanged, not that an agent could never
write or that writes outside the fixture are blocked. It intentionally
does **not** save or print the raw transcript, event IDs, prompt, stderr or
tool arguments. The host may still access its normal Codex credentials and
caches; no credentials are exported or printed by the runner. A timed-out,
unavailable, malformed or failed run exits nonzero and reports
`unverified`, not a fabricated success.

A completed read-only smoke does not certify model identity, authorization,
agent isolation or persistent workflow state. Full #16 acceptance still
requires the subsequent user-host matrix: native named-agent dispatch,
blocked unauthorized engineer, scoped authorized task, independent review,
compaction/resume and actual quota/model evidence.

## Read-only JSONL telemetry for live acceptance — issue #16

Codex's noninteractive `codex exec --json` streams JSONL events with
turn completions, item start events and numeric token usage. To check a
single bounded **read-only** run without saving raw prompts or tool output:

```sh
cd ~/kc/YOUR_DISPOSABLE_REPO
codex --version
codex exec --json --sandbox read-only \
  "Read only: summarize the top-level files and do not edit anything." \
  | python3 ~/code/mightymodels_codex/scripts/codex_trace_summary.py
```

The script parses the stream in memory and prints only counters for started
item types, completed/failed turns and numeric input/cached/output tokens.
It never prints prompts, command arguments, messages, thread IDs or raw
responses. Do not save the **raw** JSONL stream in bug reports, PRs or CI
artifacts. Disable telemetry by omitting the pipe/script entirely.

The report deliberately says `effective_model_identity: unverified` and
`quota_savings: not_measured`: model pins and token counts do not prove
actual child-agent identity, provider quota consumption or cost reduction.
Run matched baseline and MightyModels tasks on a real host and separately
verify agent routing, trust and state transitions before claiming #16 passed.
The summarizer cannot reconstruct hidden child turns or model metadata if
the event stream does not expose them.

### Compare two sanitized Codex runs without assuming quota savings

To compare a baseline run with one using MightyModels, run **the same bounded,
authorized workload** with the same Codex CLI version and capture *only* the
sanitized JSON summary. Never redirect the raw `codex exec --json` stream to
a retained file.

```sh
codex exec --json --sandbox read-only "Inspect README.md without edits or agents" \
  | python3 ~/code/mightymodels_codex/scripts/codex_trace_summary.py > baseline.json
# After enabling the intended MightyModels workflow, run a matched approved prompt
# and save the second sanitized stream summary as candidate.json.
python3 ~/code/mightymodels_codex/scripts/codex_usage_comparison.py \
  baseline.json candidate.json
```

The comparator accepts only the sanitized JSONL-summary schema with valid
nonnegative token counts, completed turns and no error events; missing or
invalid inputs exit nonzero. It reports input+output tokens **per completed
turn** and a relative change, without counting cached inputs twice. These are
observations, not matched-workload proof or provider quota savings. The output
explicitly marks effective child models, matched workload and quota savings
`false`; other telemetry and host evidence must verify them independently.
Delete the sanitized files when no longer needed. Never expose tokens, PATs,
prompts, raw event streams or credential files to CI logs.

## Project hygiene without unverified Claude hooks — issue #17

The original Claude project settings use Write/Edit suppression prompts,
post-edit Ruff formatting, Read diagnostics, and approval rules for sensitive
toolchain files. These Claude matchers are **not** asserted to execute in native
Codex. The global MightyModels hook bridge is for lifecycle/dispatch, not
automatic formatting in arbitrary target repositories.

For development **inside this MightyModels checkout**, the project-only
`.codex/hooks.json` now registers a narrow `PreToolUse` handler for
`apply_patch` / `Edit` / `Write`. Its read-only Python guard refuses newly
added `noqa`, `type: ignore` and `ty: ignore` annotations in the patch and
direct `uv.lock` patch changes. Intercepted root `pyproject.toml`,
`ruff.toml`, `pytest.toml`, `ty.toml` and `CLAUDE.md` edits are denied with a
manual-review reason. The hook **cannot** automatically ask for or verify
approval. Make approved changes through a separately reviewed workflow, not
by silently bypassing project protections. Unknown edit payloads are denied rather than
silently assumed safe. It does not change user/global dispatch or MCP hooks.

**This is not complete host enforcement.** Hook execution requires Codex to load
and trust this project's hooks, and some edits (including shell-driven writes)
may bypass `apply_patch` interception. No `ask` response is emitted: Codex
does not currently support PreToolUse `permissionDecision: "ask"`. A refusal
requires a separate user-approved workflow, not an automatic consent prompt.
The hook never runs a formatter or changes files itself.

Continue using the explicit repository-scoped quality workflow:

```sh
python3 scripts/codex_hygiene_check.py --base origin/main
make format
make check
```

The hygiene command is read-only, compares tracked Python changes against an
existing Git base, and returns 1 when new `noqa`, `type: ignore`, or
`ty: ignore` annotations need review. Exit 2 means the check could not
complete and must **not** be treated as a pass. It does not examine untracked
files, validate every type-suppression form, or replace review. It reports
counts, not potentially sensitive source lines. `make format` intentionally
changes files; run it only where edits are approved. `make check` runs the
repo's lint/tests. Review configuration-file edits explicitly, and regenerate `uv.lock`
through the dependency tooling rather than editing it directly. A static
hook test is not proof that the live host enforced a denial.

For other repositories, use **their own** format, lint, test and approval
procedures. Never run MightyModels' Ruff/ty settings against unrelated code
as an automatic global hook. No live Codex per-read/per-edit hook delivery or
protected-file approval behavior is claimed by this fallback.
