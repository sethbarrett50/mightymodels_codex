# Codex live acceptance after usage resets

This runbook is the **host-acceptance checklist**, not a claim that CI
can enforce host permissions. Run as the normal, unprivileged XPS user with
Codex installed and an available usage allocation. Do **not** run as root.
The probes are opt-in, and only the smoke command invokes Codex inference.

## Phase 0 — safe preflight, zero inference

From the MightyModels checkout:

```bash
cd ~/code/mightymodels_codex
git pull --ff-only origin main
python3 scripts/codex_reset_acceptance.py --preflight
```

Expected: `doctor.healthy: true` and
`status: preflight_passed_live_unverified`. This checks the global MCP
launcher, `uv`, eleven owned agent links, nineteen skill links, and
registered hook groups. It reports **structural** readiness only. A
preflight failure blocks the live phase; rerun
`python3 scripts/install_codex_user.py` (after reviewing existing
user/global configuration and hook trust), then rerun preflight.

## Phase 1 — one quota-bounded smoke

After the allocation actually resets, invoke this **once**:

```bash
python3 scripts/codex_reset_acceptance.py --live --timeout 90
```

This delegates to the existing single `codex exec --json --sandbox read-only` disposable Git fixture: read `README.md`; do not write,
delegate or use credentials. It emits sanitized counters and
`fixture_unchanged`, never a transcript, raw error, or secret. It
does not retry on quota errors. Success is
`read_only_smoke_passed_host_acceptance_incomplete`; a
`possible_usage_or_rate_limit` category means **stop**, not
provider-side proof of a rate-limit cause. An unclassified failure also
means stop and inspect the sanitized outcome before choosing another
paid probe.

A completed turn, unchanged fixture and no *streamed* scope violation
do **not** prove host read-only isolation, hook execution, child models,
or refusal of unauthorized dispatch.

## Phase 2 — manual host observations (separate, opt-in)

Only after Phase 1 passes, use an **unrelated disposable Git repository**
for separate host checks; verify you are using the expected Codex
session, feature flags and installed user-scoped roles. Record only
sanitized counts, capability statuses and observed outcome classes,
not conversation content, auth tokens or private repository paths.

| Issue | Host observation to collect | Pass criteria |
|---|---|---|
| #15 | Start Codex both inside the MightyModels source checkout and in a separate disposable repository; inspect MCP list, effective config and actual hook delivery/trust | One intended MCP server, no unexpected shadowed definitions, correct checkout-scoped project hooks; absence of delivery is a **failure or unverified** status |
| #14 | In a disposable repository, explicitly invoke investigate, plan, sprint, review, landing and handoff using generated native skills/roles | Referenced helper paths and actual agent role names resolve; no Claude-only UI assumed; require explicit user decisions |
| #8 | With a disposable ticket/investigation, record an explicit decision, read back actual state, compact/resume, and verify the same decision and current target | Durable state matches the real user answer, no invented approval; duplicate callback/idempotence needs a unique event identity |
| #16 | Capture sanitized trace counters and independently observed spawned model/effort identifiers, if the host exposes these | Identity is **unverified** unless effective runtime values are observed; no quota savings claim without comparable baseline |
| #17 | Verify project PreToolUse edit guard and PostToolUse read-only Ruff check actually fire in the MightyModels checkout; compare with an unrelated repository | Warn/deny where supported, no modifications to unrelated code; missing events must not silently count as pass |


## Targeted PostToolUse delivery canary (opt-in, one live turn)

A direct `scripts/codex_post_edit_check.py` subprocess test verifies only the
handler, not Codex host delivery. To prove that the host actually invokes the
project hook after a native patch, first review and trust the project's
`PostToolUse` hook with `/hooks` in the **disposable clone**. Then use one
explicit, bounded fixture:

```bash
# Preserve the existing $fixture/repo disposable MightyModels clone.
git -C "$fixture/repo" pull --ff-only
probe_dir="$(mktemp -d)"
(
  cd "$fixture/repo"
  MIGHTYMODELS_CODEX_POST_EDIT_PROBE_FILE="$probe_dir/delivered" \
    codex exec --json --sandbox workspace-write \
      'Use native apply_patch once to add acceptance_post_hook_delivery.py containing value = 1. Do not retry, dispatch agents, use MCP tools, or modify other files.' \
      > "$probe_dir/events.jsonl" 2> "$probe_dir/stderr.log"
)
if test -f "$probe_dir/delivered"; then
  echo 'Observed: Codex delivered PostToolUse apply_patch to the hook'
else
  echo 'Unverified: no PostToolUse delivery receipt'
fi
```

The receipt is created **only** when the environment variable is explicitly
set and points outside the MightyModels checkout. It contains a fixed
nonsecret marker, is mode 0600, and never copies prompts, paths, patches or
source text. Existing receipts are not overwritten. Receipt presence proves
callback entry, **not** that Ruff/ty were available or that format checks
passed. A missing receipt is unverified, not proof that the host disabled
hooks. Do not share the raw JSONL or stderr; report only presence/absence
and the current Codex CLI version. Remove the disposable probe directory
after recording its sanitized result.

### Explicitly deferred: #9

Do **not** launch an unauthorized `mm-workers-engineer` dispatch or
attempt a host admission bypass during this run. The earlier host
admission finding remains open and separate until the user authorizes
that test. The reset gate deliberately does not exercise agent
dispatch or claim denial verification.

## Completion and evidence rules

For each phase, report the Codex CLI version, test scope, observed
pass/fail/unverified status, fixture state and *sanitized* usage/event
counts. Record host flags as observed, not guessed. Do not paste raw
JSONL transcripts, private error messages or credentials into issues.
Do not close #8, #14, #15, #16 or #17 solely on passing preflight or
the read-only smoke; finish their actual acceptance criteria.

All later live tests are manual and separately opt-in so a reset does
not trigger an uncontrolled series of token-consuming prompts.
