# Task 010 — SRD002 semantic triage groups

Status: implemented. Base: `origin/main`
`2310490cb6694fdce0d61c2325039e9f54c9874e` (contains the reviewed Task 009 head
`c80b7b5c`).

## Result in one paragraph

When `--semantic` enrichment is evaluated, the report gains a report-level
triage view, `analysis.semantic.srd002_groups`, and an `SRD002 semantic
triage` text section placed before the individual diagnostics. Unproved
`VC_PRECONDITION` client failures whose Task 009 resolution is `exact` are
grouped by the **identical resolved declaration and identical extracted
public `Pre`**. Every other client failure is listed once as `ungrouped`,
with a stable machine reason. In `ring_no_is_full_post`, three repeated
`Push` precondition failures become **one** `Ring_Buffer.Push` /
`not Is_Full (B)` group, and the `VC_ASSERT` stays ungrouped. This is
consolidation, **not diagnosis**: no shared cause, no defective contract, no
failed conjunct, and no group confidence. No Diagnostic is created,
removed, merged or changed. Without `--semantic`, output is byte-identical
to Task 009. With `--semantic`, removing `srd002_groups` yields exactly the
Task 009 JSON.

## 1. Product question and answer

*Does grouping semantically identical SRD002 precondition failures make the
report materially easier to triage without adding a proof or causality
claim?*

Pre-registered answer: **yes for repeated call boundaries, neutral
otherwise.** The benefit is local to reports where one public operation is
called repeatedly: `ring_no_is_full_post` goes from 3 Push precondition
checks to 1 callee/contract group. Where every precondition calls a
different operation, grouping adds structure (callee + Pre stated once,
assertions separated with a reason) but does not reduce the count. There is
no aggregate "accuracy" score. Groups are never combined across independent
reports.

## 2. Architecture

```text
SRD002 (srd002.py)            unchanged; knows nothing about semantics
   ↓ Diagnostic objects
semantic.py (Task 009)        per-diagnostic `semantic` blocks (unchanged)
   ↓ after enrichment, only if evaluated
semantic_groups.py (NEW)      build_srd002_groups(diagnostics) -> plain dict
   ↓                          coverage_problems(doc, expected) invariant
analysis.semantic.srd002_groups
   ↓
render.py                     semantic_groups_text(): triage section
```

`semantic_groups.py` is pure Python. It imports no Libadalang and no
`semantic_lal`, reads no check message, and evaluates nothing (AST-checked
by tests). It never mutates its input: the callee, Pre and call objects in
the output are copies. `semantic_lal.py`, `gnat_checksum.py`, `ali.py`,
`srd002.py` and `setup_libadalang.sh` are **unchanged**, so the CI
Libadalang cache key is unchanged. `semantic.py` gains one import and one
line. No CLI flag was added: grouping is part of semantic mode.

## 3. What is groupable

A client failure is grouped only if **all** of these hold: it belongs to an
SRD002 diagnostic, its rule is `VC_PRECONDITION`, its Task 009 resolution
is `exact`, and it carries the complete Task 009 semantic structure
(checked structurally, never interpreted):

* `call`: a dict with string `text` and a complete `location` span;
* `callee`: non-empty string `name` and `kind`, complete `declaration` span;
* `precondition`: a dict with `explicit` exactly `true` or `false`; a
  `conjuncts` list (may be empty) whose every entry has an integer `index`,
  string `text` and complete `location` span; `failed_conjunct` present and
  `null`; `attribution` equal to `not_provided_by_gnatprove`. If `explicit`
  is `true`: string `text` and complete `location` span; if `false`: `text`
  and `location` present and both `null`.

A **complete span** has all of `file` (string), `start_line`,
`start_column`, `end_line`, `end_column` (integers, not booleans); a
start position alone is not enough. Any absent or malformed field makes the
check `semantic_incomplete` (detail: `exact entry lacks complete
call/callee/precondition data`): it is never partially grouped and never
raises, so the renderer only sees groups whose fields it reads exist.

Otherwise it is `ungrouped`, with a `reason` from this fixed vocabulary:

| reason | when |
|---|---|
| `assertion_has_no_callee` | `VC_ASSERT` (never callee-grouped, whatever its resolution) |
| `semantic_ambiguous` / `semantic_unresolved` / `semantic_unavailable` | precondition with that Task 009 resolution |
| `semantic_incomplete` | `exact` precondition lacking required grouping data, an unknown resolution, or no semantic entry at all (malformed internal state) |
| `rule_not_groupable` | any other client rule (none today: SRD002 client rules are exactly `VC_PRECONDITION` / `VC_ASSERT`) |

Task 009's human `reason` text is kept as an optional `detail`. It is never
the machine key.

## 4. Group identity

The identity is the canonical JSON (sorted keys) of the complete Task 009
`callee` object and the complete `precondition` object:

* callee: fully qualified `name`, `kind`, `declaration` span (file, start
  and end line/column);
* Pre: `explicit`, exact source `text` (verbatim, never normalised),
  `location` span, `conjuncts` (text + span each), `failed_conjunct`
  (always null), `attribution`.

As a result, overloads with the same qualified name but different
declarations stay separate. So does the same name with a different
declaration span, Pre text (even whitespace), or Pre span. If one
declaration comes with inconsistent extracted Pre metadata (e.g.
different conjuncts), the failures are **split** into separate groups and
neither version is chosen. Logically equivalent Pres (`A and then B` vs
`B and then A`) are not merged. This is source-semantic grouping, not
theorem equivalence.

## 5. Ordering (deterministic, independent of input order)

* **Groups**: callee name, declaration file, start line, start column,
  end line, end column, kind, explicit, Pre text, Pre file/line/column,
  then the canonical identity string as a total tie-break.
* **Occurrences** and **ungrouped**: client unit, entity, file, line,
  column, rule.

## 6. Occurrence identity and duplicates

Occurrence identity is (client unit, diagnostic entity, rule, file, line,
column). The input is walked over each diagnostic's `related` checks with
role `client failure`, which are authoritative, paired with the semantic
entry of the same (rule, file, line, column). If the same identity occurs
twice, which SRD002 does not produce, the two are indistinguishable. They
are kept as **one** occurrence with `duplicate_count` (present only if > 1)
and rendered as "(reported N times)". All counts are counts of distinct
occurrences. This is the smallest deterministic behaviour, and it is tested.

## 7. Coverage invariant

`coverage_problems(doc, expected)` returns `[]` iff:

* every expected SRD002 client-failure identity appears **exactly once**
  across all group occurrences and `ungrouped`, never both and never
  neither, and nothing unexpected appears;
* `group.check_count == len(group.occurrences)` for every group,
  `group_count == len(groups)`, `grouped_check_count` and
  `ungrouped_check_count` equal the list sizes, and
  `grouped_check_count + ungrouped_check_count == client_failure_count ==
  |expected|`;
* only `VC_PRECONDITION` is grouped, no group has a `confidence`, no group
  Pre has a non-null `failed_conjunct`, and every ungrouped reason is in the
  vocabulary.

Tests deliberately duplicate and drop occurrences and corrupt each count;
the checker catches every case. E2E-F and E2E-G run the same checker on the
fresh reports.


## 8. JSON (`format_version` stays 1)

```json
"analysis": {"semantic": {
  "...": "Task 009 fields, unchanged and in the same order",
  "srd002_groups": {
    "client_failure_count": 4,
    "group_count": 1,
    "grouped_check_count": 3,
    "ungrouped_check_count": 1,
    "groups": [{
      "callee": {"name": "Ring_Buffer.Push", "kind": "procedure",
                 "declaration": {"file": "src/ring_buffer.ads",
                                 "start_line": 36, "start_column": 4,
                                 "end_line": 38, "end_column": 62}},
      "precondition": {"explicit": true, "text": "not Is_Full (B)",
                       "location": {"file": "src/ring_buffer.ads",
                                    "start_line": 37, "start_column": 17,
                                    "end_line": 37, "end_column": 32},
                       "conjuncts": [{"index": 0,
                                      "text": "not Is_Full (B)",
                                      "location": {}}],
                       "failed_conjunct": null,
                       "attribution": "not_provided_by_gnatprove"},
      "check_count": 3,
      "diagnostic_confidences": ["low", "medium"],
      "occurrences": [{
        "client_unit": "ring_buffer_client_proof",
        "entity": "Ring_Buffer_Client_Proof.Push_Push_Pop",
        "diagnostic_confidence": "low", "rule": "VC_PRECONDITION",
        "location": {"file": "ring_buffer_client_proof.adb",
                     "line": 9, "column": 7},
        "call": {"text": "Push (Q, A)", "location": {}}}]
    }],
    "ungrouped": [{
      "client_unit": "ring_buffer_client_proof",
      "entity": "Ring_Buffer_Client_Proof.Push_Push_Pop",
      "diagnostic_confidence": "low", "rule": "VC_ASSERT",
      "location": {"file": "ring_buffer_client_proof.adb",
                   "line": 16, "column": 43},
      "resolution": "exact", "reason": "assertion_has_no_callee"}]
  }}}
```

(Abbreviated: only one occurrence is shown, and `{}` spans are the complete
Task 009 span objects.) Optional per-entry keys: `detail` on ungrouped
entries (Task 009's reason), and `duplicate_count` (§6).

It is present only when enrichment is **evaluated**. If `--semantic` is not
given, the backend is missing, or no project was supplied, there is no
`srd002_groups` and nothing is fabricated. Provenance is not copied into
groups; `analysis.semantic.provenance` remains authoritative
(`layout_exact`/`byte_exact` false). A group has **no** confidence;
`diagnostic_confidences` only lists its occurrences' confidences.

## 9. Text

```text
SRD002 semantic triage:
  3 grouped precondition checks -> 1 callee/contract group
  1 ungrouped check

  Ring_Buffer.Push (procedure, src/ring_buffer.ads:36:4)
    public Pre: not Is_Full (B)
    calls: 3
      ring_buffer_client_proof.adb:9:7  Push (Q, A)
      ring_buffer_client_proof.adb:10:7 Push (Q, B)
      ring_buffer_client_proof.adb:25:7 Push (Q, X)

  ungrouped:
    ring_buffer_client_proof.adb:16:43 VC_ASSERT
      assertion_has_no_callee

  Groups are descriptive: sharing a callee and Pre does not establish a
  shared cause, does not identify a failed conjunct and does not show that a
  public contract must change. GNATprove remains the proof authority.
```

The section is followed by the unchanged per-diagnostic output, including
Task 009's semantic blocks: summary plus detail. Renderer tests forbid, in
this section, "root cause", "contract is insufficient", "contract defect",
"fix the contract", "missing contract", "same cause", "is the problem",
"is insufficient" and "recommended fix".


## 10. Known-case results (real Libadalang 26.0.0, capture environment)

| case | SRD002 client failures | exact precondition checks | callee/contract groups | grouped | ungrouped |
|---|---|---|---|---|---|
| `ring_no_is_full_post` | 4 | 3 | **1** (`Ring_Buffer.Push` × 3) | 3 | 1 (VC_ASSERT 16:43) |
| `ring_no_public_model_bound` | 1 | 1 | 1 (`Ring_Buffer.Push` × 1) | 1 | 0 |
| `ring_no_is_empty_post` | 6 | 4 | 4 (`Pop`, `Push`, `Sequences.Get`, `Sequences.Remove`, × 1 each) | 4 | 2 (VC_ASSERT) |
| `pool_spec_no_count_posts` | 3 | 1 | 1 (`Fixed_Pool.Allocate` × 1) | 1 | 2 (VC_ASSERT) |
| `pool_false_client_assert` | 1 | 0 | **0** | 0 | 1 (VC_ASSERT 9:22) |
| **total (5 benchmark cases)** | **15** | **9** | **7** | 9 | 6 |

The totals are descriptive, not an accuracy metric. The 9 → 7 reduction
comes entirely from `ring_no_is_full_post` (3 → 1); groups are per report
and are never merged across reports.

* **Archived `ring_no_is_empty_post`** on a machine whose SPARKlib checkout
  does not match the captured `D` timestamp: `Sequences.Remove/Get` are
  `unavailable` (Task 009 gate, unchanged). They then appear as
  `ungrouped` `semantic_unavailable` (2 groups, 4 ungrouped) and do not
  disappear. This is tested deterministically by altering the D record in
  a temporary copy. In the capture environment they are exact (4 groups).
* **Fresh E2E-G**: all four exact, so 4 groups. Grouping follows the
  semantic evidence rather than forcing a desired shape.
* **`pool_false_client_assert`**: SRD002 still LOW, zero groups, one
  ungrouped `VC_ASSERT` (`assertion_has_no_callee`). The text shows no
  "public Pre" line, so nothing suggests a public operation should change.
* **Experiment corpus (`conjunct_experiment`, not a benchmark case)**:
  13 failures, 12 exact preconditions, 7 groups. Notably, `Ops.Over`
  appears as **two** groups (declarations at lines 32 and 36, Pre `X > 0`
  vs `X`): the overloads do not collapse.

## 11. Compatibility gates

* **No `--semantic`**: 202 outputs (explain and analyze × 49 fixtures ×
  text/json, compare-provers text/json, rules text/json, prove --dry-run
  text/json) from Task 009 main `2310490` and this branch are
  **byte-identical** (`diff -r`: no difference).
* **Task 009 per-diagnostic semantic JSON**: all 6 committed semantic
  snapshots were enriched with real Libadalang on main and on this branch.
  After removing `analysis.semantic.srd002_groups`, the JSON documents are
  **equal**, and every Task 009 text line is preserved in order (the only
  new text is the triage section). The same equality is also a pure unit
  test (`ReportIntegration`, stub backend).
* `format_version` stays 1; the core package has no runtime dependencies;
  `semantic_groups.py` is in the wheel (packaging smoke). On a core install
  without Libadalang, `--semantic` degrades exactly as in Task 009 and
  **no** `srd002_groups` is fabricated (packaging smoke).


## 12. Tests and evidence (reported separately, no combined score)

| suite | count | notes |
|---|---|---|
| existing diagnostics tests (Task 009 main) | 244 | all still pass; the Task 009 E2E-F/G stubs now get the Pre span and call span that real Libadalang always reports |
| new pure grouping tests `test_semantic_groups.py` | 45 | no Libadalang: identity, ungrouped reasons, confidence and ordering, coverage invariant (duplicate/drop/counts/forbidden content), duplicates, no mutation, backend neutrality, text wording, JSON shape, report integration; completeness gate: 34 single-field exact corruptions + 7 malformed `explicit=False` subtests, complete-variant controls, renderer safety (`call = {}`) |
| new tests in `test_semantic.py` | 13 | 6 E2E-F/G grouping-checker tests (no Libadalang), 7 real-Libadalang known-case grouping tests |
| total | 302 | without Libadalang: 21 skipped; **with Libadalang under `alr -n exec`: 0 skipped, 0 failures** |
| E2E-F (fresh `no_is_full_post` + `explain --semantic`) | PASS locally | 1 group Push ×3 at 9:7/10:7/25:7; VC_ASSERT 16:43 ungrouped |
| E2E-G (fresh `no_is_empty_post`, SPARKlib callees) | PASS locally | 4 groups Pop/Push/Remove/Get, 2 assertions ungrouped |

No new proof case, no new CI job and no new GNATprove invocation were added;
E2E-F/G reuse their existing fresh runs. CI cache status and
`diagnostics-semantic` wall time are recorded in the PR (not a correctness
gate).

## 13. Decision: semantic enrichment stays opt-in

Libadalang is not a pip dependency, a cold hosted setup measured ~23.5 min
(Task 009), and the core diagnostics package deliberately keeps zero
runtime dependencies. Grouping therefore appears only under `--semantic`.
Revisit automatic enablement if Libadalang distribution improves. Recorded
in `docs/ROADMAP.md`.

## 14. Recommendation for Task 011

On this corpus, grouping helps exactly where one boundary repeats
(`ring_no_is_full_post`). Elsewhere it clarifies structure but saves
little. The larger unmet need is still the *which conjunct / which missing
fact* question, which Task 009 showed GNATprove output cannot answer.
Candidates, in order of evidence value:

1. A **separately pre-registered per-conjunct re-proof experiment**. It
   would generate scratch clients in `obj/` only, with one `pragma Assert`
   per top-level Pre conjunct at a failing call site, re-proved by
   GNATprove. This produces *new proof evidence* and needs its own trust
   model (scratch sources never touch user sources, and GNATprove decides).
   Task 010 groups make it cheaper: one experiment per group rather than
   per call.
2. **Libadalang distribution work** (e.g. a published prebuilt bundle), to
   lower the barrier to `--semantic` before considering default enablement.

## 15. Non-goals honoured

No new diagnostic rule (no SRD004 or variant). SRD002 trigger, closure,
confidence, text, count, sorting and related checks are unchanged. No
Diagnostic is created, removed, merged or suppressed. There is no group
confidence, no causal or contract-defect claim, and `failed_conjunct` stays
null. There is no conjunct re-proving, no new GNATprove invocation, no
source generation or rewriting, and no contract change. The Libadalang
resolution and provenance policy is unchanged, `semantic_lal.py` /
`setup_libadalang.sh` are untouched, and `compare-provers` is unchanged.
GNATprove remains the proof authority.

