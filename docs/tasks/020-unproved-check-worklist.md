# Task 020 — opt-in unproved-check worklist

## Starting state and scope

Fetched `origin` before work; the working tree was clean. Actual starting
`origin/main`: **`448a37753af8bd592603e176266adeb4a601b415`**, unchanged from
the reviewed main. Verified Task 019 head
`c7d85c393d424ead686e5715492250bbe21b522d` is its ancestor. Created
`feature/020-unproved-check-worklist` from that main without resetting the
previous Task 019 branch.

This is ordinary product reporting development, not a new research campaign.
Task 019 remains closed: **`DO_NOT_ADOPT_BITMAP_PATTERN`**. No bitmap source,
metrics, closeout artifacts, Prefix_Sets or Tasks 015–018 evidence changed.
No Task 021 or human/agent usage trial has started.

## Interface

```sh
spark-refine explain RESULT_DIR --show-unproved
spark-refine explain RESULT_DIR --show-unproved --format json
spark-refine analyze RESULT_DIR --show-unproved --format json
spark-refine prove -P project.gpr --show-unproved --format json
alr exec -- spark-refine prove -P project.gpr --show-unproved --format json -- --checks-as-errors=on
python3 -m spark_refine_diagnostics explain RESULT_DIR --show-unproved
```

Supported only on `explain`, its explicit-path alias `analyze`, and `prove`.
The flag is consumed by spark-refine. The existing first-`--` split remains:
everything after it belongs verbatim to GNATprove, including later `--` or
tokens spelled `--show-unproved`. No new dependency or source access is
required. It works independently of optional `--semantic` and Libadalang.

The small `check_inventory.py` module projects **`ProofRun.unproved`**;
there is no new loader or classifier. Proved and justified checks do not
appear; every unproved occurrence does, including `ALIASING` and disputed
checks. Duplicate-looking occurrences remain separate, with no truncation
and no stable cross-run IDs. Original checks and runs are not mutated.

JSON remains `format_version: 1` and adds optional
**`analysis.unproved_checks`** only when requested:

| Field | Meaning |
|---|---|
| `scope` | Fixed `normalized_checks_in_loaded_result_set` |
| `count` | Number of projected occurrences |
| `by_rule` | Sorted rule-name counts derived from items |
| `items` | Every normalized unproved occurrence |

Each item contains `rule`, `status: "unproved"`, `entity`, `unit`,
`location: {file, line, column}`, `disputed`, `sarif_kind`, `sarif_level`,
`spark_severity`, and the existing `message`. Null unit/line/column/severity
and empty entity are preserved. Existing normalized paths are not resolved
again. Sort order is unit/entity/file/line/column/rule, explicitly missing
first, then the serialized item for deterministic ties. Identical items
retain their full multiplicity.

Invariant: **`count = len(items) = len(run.unproved) = sum(by_rule.values())`**.
Messages participate only as data and a final sort tie-breaker; their prose
cannot affect membership, normalized status or structural counts. Nothing
in a source name or message is executed or followed as an instruction.

Text places one separated section after existing headers, orchestration,
notes and semantic context, before individual SRD diagnostics. Actual
committed `ring_b5` fixture output includes:

```text
Reported unproved checks: 1
  VC_POSTCONDITION: 1
  Scope: loaded normalized checks only, not a complete proof certificate. Justifications, warnings, consistency issues and incomplete-analysis notes remain separate; these raw checks are not specialized SRD diagnostics.
  ring_buffer.ads:39:17 VC_POSTCONDITION [unproved]
    entity: Ring_Buffer.Push; unit: ring_buffer
    postcondition might fail

no SRD diagnostics
summary: 0 diagnostics
```

At zero the section says **No unproved checks in the loaded normalized
result set.** It does not claim program verification or proof completeness.
These are raw reported checks, not SRD findings, bugs or automatic diagnoses.
**11 unproved checks + 0 SRD diagnostics still means proof work remains.**

## Uncertainty and process policy

This worklist is **not a complete proof certificate**. Existing justified
counts, tool/foundation warnings, consistency notes, incomplete-analysis
notes, rule-not-evaluated metadata and semantic provenance limitations stay
unchanged. A `.spark`-only failure can remain a consistency issue rather
than a normalized SARIF Check; no item is invented to reconcile it. Zero
normalized unproved checks with missing `.spark` is not whole-program
completeness. Disputed unproved checks are included and marked `[disputed]`.

The flag is not an acceptance gate. Existing `--fail-on SRDxxx` behavior,
input errors, freshness selection, signal normalization and GNATprove
nonzero exit precedence are unchanged. Exit 0 with unproved checks stays
0 under the existing policy, with its explanatory note; nonzero with fresh
usable output still emits the report and preserves that exit. No usable
result still errors, never fabricating an empty successful worklist.
`prove --dry-run --show-unproved` only emits the existing plan, without
running GNATprove or inspecting artifacts. GNATprove's existing
`--checks-as-errors=on` provides an upstream process gate when desired.

The [agent workflow](../AGENT_INTEGRATION.md#the-loop-preferred) checks
process/orchestration, raw checks independently of SRDs, justifications,
warnings and coverage/consistency, then specialized context. Humans/agents
must review source and authoritative requirements, make an appropriate
change and rerun proof before claiming completion. No authorization to
weaken a public contract is implied. No measured time/token/success-rate
improvement is claimed; the interface can be used in a later usage trial.

## Validation actually run

Local Python: 3.13. Existing stdlib unittest/support import convention is
used, including execution from the repository root and another directory.

| Validation | Result |
|---|---|
| Focused `test_check_inventory.py` | 19 tests; 18 passed + 1 optional real-Libadalang skip without backend; all covered in backend-enabled suite |
| Full diagnostics suite, no Libadalang | 486 tests, OK, 35 optional skips |
| Full diagnostics suite under ring-buffer `alr -n exec`, cached Libadalang 26.0.0 | 486 tests, OK, no skips |
| Root unit tests | 4 tests, OK |
| `scripts/check_repo.py` / `git diff --check` | Passed |
| Wheel packaging smoke | Passed; no runtime dependency/fixture payload; installed console and module invocation outside repository |
| Editable packaging smoke | Passed; same CLI matrix outside repository |
| Fresh E2E-A | Passed; fresh B3 negative detects `VC_INVARIANT_CHECK` at `Ring_Buffer.Pop`, original SRD001 assertion retained |

The focused suite includes the real no-SRD unproved postcondition in
`ring_b5`, SRD-related raw occurrences in `ring_b3`, all 49 core fixture
reports, non-VC/duplicate/proved/justified synthetic edges, null metadata,
empty entity, disputed status, deterministic reordering, nonmutation,
message independence, note preservation and a derived real-fixture
`.spark`-only inconsistency. Synthetic/derived cases are labelled honestly;
no fixture or historical expectation was modified.

Exit tests exercise SRD-specific fail-on, GNATprove 0/1/7 with usable fresh
unproved results, signal 15 → 143, no-result 0 → input error 2, no-result
nonzero 8, clean JSON stdout, stale decoys, unchanged passthrough and
dry-run that rejects execution/inspection. Semantic tests include unavailable
and available fake backends, real Libadalang CLI enrichment for
explain/analyze, and additive worklists with `prove --semantic`.

Packaging exercises **all three commands × both formats × console/module
entry points**, repeated for wheel/editable installs, including exact
explain/analyze equality and removing the optional block/section to recover
the original report. Prove packaging uses an explicitly fake GNATprove,
not a claimed real proof.

Compatibility was compared directly against an archive of starting main,
not against changed fixture expectations:

* 55 core/semantic real result sets × explain/analyze × text/JSON =
  **220 byte-identical default CLI outputs** (stdout/stderr/exit).
* 49 core fixtures × fake GNATprove exits 0/1 × text/JSON =
  **196 byte-identical default prove outputs and exits**, plus additive-only
  requested output for each. Each fixture used a clean result directory.
* Three prover portfolios × text/JSON = **6 byte-identical compare-provers
  reports**.
* Core corpus tests remove the optional JSON block/text section and recover
  unchanged existing reports, diagnostic objects and counts.

The E2E change makes one additional `explain --show-unproved` invocation
on E2E-A's same freshly produced output. It verifies exact projection/count
parity with `load_run(...).unproved`, rule-total parity, and equality to the
original report after removing the block. Actual fresh count: **1**. No
additional proof, external checkout/proof, bitmap job or new CI job was
added; the existing seven jobs remain.

## Task 017 practical replay — exact raw artifacts

**Exact raw artifact-hash replay**, not a new reproduction. Ignored artifacts
were available at `diagnostics/obj/task017-external/failing/obj/gnatprove`.
Verified the external checkout is still
`5fa2c0cee62deb86368fcc84a8d3b06726028276`, with empty tracked-tree status
and unchanged diff before/after. No external build or proof command ran.

Every individual `.sarif`/`.spark`/`.ali` file hash and the three inventory
digests match committed historical
`docs/evidence/task017-positive-external-validation.json`:

| Artifact set | Files | Historical inventory SHA-256 (matched) |
|---|---:|---|
| `.sarif` | 1 | `83cd0e9b4e055fa39cb69155e1b195a130a39eb819f46ba11493e84d65934f23` |
| `.spark` | 39 | `11c0a01912e02f0b14a09183dcf06832501670617fe94b451caf571afb3d20a6` |
| `.ali` | 39 | `0cdd85b74be497001725ab766b7b729ba6213d9c38a4e516efa7b9aaf769a203` |

The actual `gnatprove.sarif` SHA-256 is
`0cdbe86e119db285c836b0ba9c3070a45b97c9e3fb5122b9db899beebb6ff0f3`.
Historical inventory digests are name/hash inventories, not file digests.

The new CLI loaded the raw artifacts and exposed **all 11 individual
checks**, with recorded entity/unit/location/message. Derived breakdown:
**9 `VC_OVERFLOW_CHECK`, 1 `VC_POSTCONDITION`, 1 `ALIASING`**; all 11
undisputed. Their rule/entity/location/status/dispute identities also match
the historical per-check evidence. **SRD001=0, SRD002=0, SRD003=0**;
existing rule evaluation stays intact. The three historical proved SARIF
`error`-rule mismatches remain disputed proved checks and consistency notes,
not extra unproved items. All **13** existing notes (three consistency and
ten incomplete generic-unit analysis notices) remain.

A small [saved demonstration](../examples/task020-unproved-checks.json)
contains the actual CLI inventory, diagnostic summary and notes, with replay
identity. It is an excerpt, not a substitute raw proof artifact or a full
proof certificate. No external source or full raw logs are committed.

## Delivery and limitations

The branch is intended for a non-draft PR titled **Task 020: expose unproved
checks for humans and agents**, against main, with auto-merge disabled and
no merge. Final SHA, PR identity/head equality and the single exact-head CI
observation are reported in the delivery response, avoiding self-referential
commit metadata here.

Local Python 3.11 was unavailable; the existing packaging CI job retains
its Python 3.11 full-suite check. Broader hosted proof jobs are not claimed
as locally rerun by this task. Exact-head hosted CI is separate from the
successful local runs above.

No new diagnostic rule; no SARIF/.spark/ALI parser or loader change; no
SRD001–SRD003, grouping, attribution or normal `failed_conjunct = null`
change; no automatic source repair, contract weakening or bitmap reopening.
GNATprove remains the proof authority.