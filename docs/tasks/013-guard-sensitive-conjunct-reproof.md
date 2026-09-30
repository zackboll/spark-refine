# Task 013 — Guard-sensitive conjunct re-proof experiment

Status: pre-registered. This section was committed before any Task 013
probe code was written and before any Task 013 GNATprove run. Base:
`origin/main` `4b58e7c3762476782c37a9e1813dc4a0c5fa5fae`, which contains
the reviewed Task 012 head `02d1e163`. This is an **experiment**. It is
not a product feature. It adds no CLI, no SRD rule and no change to
`failed_conjunct`.

Before this commit, the only tool run on the new corpus was an Ada
legality check (`gcc -c -gnatc` on temporary copies). It produces no proof
result.

## Pre-registration

This section is frozen at the preregistration commit. Results are
appended below under "Observed results". Nothing in this section is
edited after the experiment has run.

### P1. Question

Task 012 validated one method: replace a callee `Pre` with **one**
top-level conjunct and re-run GNATprove. It was validated only for
independent, total integer conjuncts. That method is unsafe for
`A and then B` when `A` establishes a fact `B` needs to be well defined:
non-nullness, an index range, or another callee's `Pre`.

Task 013 asks:

> Can a prefix-preserving scratch re-proof provide useful conjunct-level
> evidence for short-circuit-dependent `and then` contracts without
> evaluating a guarded conjunct outside the context supplied by its
> preceding conjuncts?

For `Pre => C0 and then C1 and then ... and then Cn` the experiment
probes only the cumulative **source prefixes**

```text
P0 = C0
P1 = C0 and then C1
...
Pn = the full original Pre
```

It never probes `Ci` (i > 0) on its own.

### P2. Trust model and vocabulary

GNATprove is the only proof authority. Each scratch run proves, or fails
to prove, only the scratch program. The result is **new scratch proof
evidence**. It is not read out of the original GNATprove result, and it
does not prove the original program.

Allowed vocabulary: *prefix transition*, *newly unproved at conjunct i*,
*blocked by earlier prefix*, *scratch evidence*. The experiment does not
speak of a failed conjunct, a culprit or a root cause. Normal Task 009
reports keep `failed_conjunct: null` and
`attribution: not_provided_by_gnatprove`.

### P3. Corpus (new, experimental input only)

`diagnostics/tests/experiments/task013_guarded/` is new in this commit
and is not product code. The historical Task 009 / Task 012 corpus
(`diagnostics/tests/semantic_fixtures/conjunct_experiment/`) is not
modified. Committed source sha256:

| file | sha256 |
|---|---|
| `guarded.gpr` | `4fdddb9c2ce3c57c0b048561b76a1f85d3d1bc23ad90c3f8f06eb452cb11d01e` |
| `src/guarded_client.adb` | `4b6cc0c70ecf4decb15589f4013683225dedc1fb96005716f15549645d25772c` |
| `src/guarded_client.ads` | `146a235bbffae94e4e18b5ce8439de47f29184453e1cd0f5f98b998e94690186` |
| `src/guarded_ops.adb` | `8e1af7ef8a0bac18e11bc0815ad6984d22777a8377cb86f226752c0353548950` |
| `src/guarded_ops.ads` | `06b08015661d612623c10000143dd3a24717913164e2f30829255c228d1ddb76` |

All files are ASCII, LF-only and tab-free.

Guarded contracts (`src/guarded_ops.ads`):

```ada
type Int_Access is access constant Integer;
type Int_Array is array (Positive range <>) of Integer;

procedure Use_Access (P : Int_Access)
with Pre    => P /= null
               and then P.all > 0, ...                      --  lines 11-12

procedure Use_Index (A : Int_Array; I : Integer)
with Pre    => I in A'Range
               and then A (I) > 0, ...                      --  lines 17-18

function F (X : Integer) return Integer
with Pre    => X > 10 and then X < 1000,
     Post   => F'Result = X - 1, ...

procedure Use_Nested (X : Integer)
with Pre    => X in 12 .. 999
               and then F (F (X)) > 20, ...                 --  lines 28-29
```

Every caller body is a single call. The caller's own `Pre` sets up the
caller state:

| case | caller (entity) | caller Pre | call |
|---|---|---|---|
| A1 | Guarded_Client.A1_Guard_And_Value | `P /= null and then P.all > 0` | guarded_client.adb:7:7 `Use_Access (P)` |
| A2 | Guarded_Client.A2_Guard_Only | `P /= null` | guarded_client.adb:12:7 `Use_Access (P)` |
| A3 | Guarded_Client.A3_No_Guard | none | guarded_client.adb:17:7 `Use_Access (P)` |
| B1 | Guarded_Client.B1_Range_And_Value | `I in A'Range and then A (I) > 0` | guarded_client.adb:22:7 `Use_Index (A, I)` |
| B2 | Guarded_Client.B2_Range_Only | `I in A'Range` | guarded_client.adb:27:7 `Use_Index (A, I)` |
| B3 | Guarded_Client.B3_No_Range | none | guarded_client.adb:32:7 `Use_Index (A, I)` |
| C1 | Guarded_Client.C1_Guard_And_Value | `X in 23 .. 999` | guarded_client.adb:37:7 `Use_Nested (X)` |
| C2 | Guarded_Client.C2_Guard_Only | `X in 12 .. 999` | guarded_client.adb:42:7 `Use_Nested (X)` |
| C3 | Guarded_Client.C3_No_Guard | none | guarded_client.adb:47:7 `Use_Nested (X)` |

C1: from `X in 23 .. 999` and `F'Result = X - 1` it follows that
`F (F (X)) = X - 2 > 20`. C2: `X = 12` gives `F (F (X)) = 10`.

### P4. Pre-registered extraction

Libadalang finds each callee's single subprogram declaration and its
explicit `Pre` aspect. The top-level `and` / `and then` split is the same
as Task 009's (`semantic_lal.LalBackend.conjuncts`). The operators come
from the `BinOp` nodes of that same tree. Before any proof run, the
extraction must equal:

```text
Guarded_Ops.Use_Access  conjuncts ["P /= null", "P.all > 0"]        operators ["and then"]
Guarded_Ops.Use_Index   conjuncts ["I in A'Range", "A (I) > 0"]     operators ["and then"]
Guarded_Ops.Use_Nested  conjuncts ["X in 12 .. 999", "F (F (X)) > 20"]  operators ["and then"]
```

Pre expression spans (Libadalang, end column exclusive):

| callee | start | end |
|---|---|---|
| Guarded_Ops.Use_Access | 11:19 | 12:37 |
| Guarded_Ops.Use_Index | 17:19 | 18:37 |
| Guarded_Ops.Use_Nested | 28:19 | 29:42 |

If the extraction differs, the experiment stops (exit 2) and gives no
verdict. The expected strings are not updated to make a run pass. Ada is
never parsed with regular expressions.

### P5. Prefix construction (planner)

A pure planner takes the ordered conjuncts (text and byte range) and the
top-level operators. For each `i` it produces one plan item:

* `conjunct_index = i`
* `conjunct_text = Ci`
* `prefix_text` = the **exact original source bytes** from the start of
  `C0` to the end of `Ci`
* `predecessor_index = i - 1`, or `null` for `i = 0`
* `requires_predecessor = (i > 0)`

It refuses input where `C0` does not start the `Pre` expression, where
conjuncts are not in increasing, non-overlapping source order, or where
the operator count is not the conjunct count minus one. It never rewrites
operators (`and` stays `and`, `and then` stays `and then`), never reorders
conjuncts, and never builds Ada text from a normalised expression.

The planner can schedule only prefix probes. A request for a
selected-only (Task 012) probe of a conjunct with an `and then` before it
is **refused**, and pure tests check this. The experiment itself also
checks that every scratch `Pre` it generated re-extracts to a planned
prefix.

Pre-registered exact prefixes, as JSON strings (`\n` is a newline; 18
spaces of indentation):

| callee | prefix | exact prefix text |
|---|---|---|
| Guarded_Ops.Use_Access | 0 | `"P /= null"` |
| Guarded_Ops.Use_Access | 1 | `"P /= null\n                  and then P.all > 0"` |
| Guarded_Ops.Use_Index | 0 | `"I in A'Range"` |
| Guarded_Ops.Use_Index | 1 | `"I in A'Range\n                  and then A (I) > 0"` |
| Guarded_Ops.Use_Nested | 0 | `"X in 12 .. 999"` |
| Guarded_Ops.Use_Nested | 1 | `"X in 12 .. 999\n                  and then F (F (X)) > 20"` |

The last prefix is the full original `Pre`.

### P6. Scratch transformation and isolation

Each run gets a real-file copy (bytes only, no symlinks) of `guarded.gpr`
and `src/*.ad[sb]` in its own directory under the gitignored
`diagnostics/obj/task013-guarded-reproof/<run>/`.

For prefix `i` of callee `K`, only `src/guarded_ops.ads` changes. The
bytes of `K`'s `Pre` expression range from the end of `Ci` to the end of
the expression are overwritten with spaces, except newline bytes, which
are kept. The prefix itself stays as the untouched original bytes. File
length and newline positions are preserved.

Gates, all machine-checked for every run:

* non-final prefix: exactly one changed file (`src/guarded_ops.ads`),
  exactly one changed allowed range, no changed byte outside it, length
  and newline positions preserved;
* final prefix: the copy is byte-identical to the corpus, because the
  prefix is the whole `Pre`;
* baseline: byte-identical to the corpus;
* reparse: zero Libadalang diagnostics. The scratch `Pre` of `K` has text
  exactly `prefix_text`, conjuncts exactly `C0..Ci` and operators exactly
  the original first `i` operators. The other callees' `Pre` text and span
  are unchanged.

All destructive operations resolve **strictly below**
`diagnostics/obj/task013-guarded-reproof/` and use the Task 012 safety
model unchanged: they refuse symlinked scratch directories, symlinked
corpus files, the root itself and any path outside it.

### P7. Forbidden-trust gate

The Task 012 Libadalang structural scan (after its Axiom correction) runs
on the committed corpus and on every scratch copy. It covers
`pragma Assume`; `Annotate` with `False_Positive`, `Intentional`, `Axiom`,
`Skip_Proof` or `Skip_Flow_And_Proof`; `Suppress` / `Suppress_All`;
`SPARK_Mode => Off`; `Import` / `Interface` / `Axiom` mechanisms; and
bodyless Ghost subprograms. The committed corpus must have zero hits, and
no scratch copy may introduce one.

### P8. Runs

Each run is a fresh GNATprove FSF 16.1.0 with the project switches
`-U --mode=all --level=2 --report=statistics` plus `-j0`, from the pinned
Alire environment of `examples/ring_buffer`. That makes **7 runs**:

| run | scratch change |
|---|---|
| `baseline` | none |
| `use_access_p0` | Use_Access Pre := P0 |
| `use_access_p1` | Use_Access Pre := P1 (= original) |
| `use_index_p0` | Use_Index Pre := P0 |
| `use_index_p1` | Use_Index Pre := P1 (= original) |
| `use_nested_p0` | Use_Nested Pre := P0 |
| `use_nested_p1` | Use_Nested Pre := P1 (= original) |

In a run for callee `K`, the three call sites of `K` are the observed
targets. The other six call sites are *untouched targets*. Their callee
`Pre` was not changed, so they must have the baseline status.

### P9. Structural result identity

A target is one `VC_PRECONDITION` matched by rule, client entity, file,
line and column, read from the loader's structural SARIF status and
checked against the `.spark` files (`disputed`). Message text is never
read. Invalid probe: zero matches, more than one match, a disputed check
or a JUSTIFIED status.

### P10. Nested-call and guard well-definedness checks

These checks are recorded **separately** and are never folded into a
target. They are identified structurally by rule, entity (the callee
whose `Pre` contains them), file and location.

* **Nested (critical gate).** In every run where the `Use_Nested` `Pre`
  is the full expression (every run except `use_nested_p0`), there are
  exactly two `VC_PRECONDITION` checks with entity
  `Guarded_Ops.Use_Nested`, at `guarded_ops.ads:29:28` (outer `F`) and
  `guarded_ops.ads:29:31` (inner `F`). Both are PROVED. In
  `use_nested_p0` there are zero `VC_PRECONDITION` checks with that
  entity. No nested check has the location of a target call.
* **Guard well-definedness.** Every `VC_NULL_POINTER_DEREFERENCE` check
  with entity `Guarded_Ops.Use_Access` and every `VC_INDEX_CHECK` check
  with entity `Guarded_Ops.Use_Index` is recorded. Every one of them must
  be PROVED. In `use_access_p0` / `use_index_p0` the guarded expression is
  absent, so there must be zero of the corresponding check. The count in
  other runs is recorded, but it is not a condition.
* **No leakage.** In every run, every check that is not one of the nine
  target `VC_PRECONDITION`s must be PROVED. No other check may be
  UNPROVED or JUSTIFIED. SARIF results at level warning/note (the
  loader's `ToolWarning`s) are not proof checks, and are not a condition.

If a nested `F` precondition check is UNPROVED or JUSTIFIED in the run
for a prefix, that prefix has no clean conjunct result. It is classified
`nested_precondition_unproved`, never `newly_unproved`.

### P11. Baseline control

The baseline (unmodified copy, original full `Pre`) is required to give:

| case | call | required |
|---|---|---|
| A1 | guarded_client.adb:7:7 | PROVED |
| A2 | guarded_client.adb:12:7 | UNPROVED |
| A3 | guarded_client.adb:17:7 | UNPROVED |
| B1 | guarded_client.adb:22:7 | PROVED |
| B2 | guarded_client.adb:27:7 | UNPROVED |
| B3 | guarded_client.adb:32:7 | UNPROVED |
| C1 | guarded_client.adb:37:7 | PROVED |
| C2 | guarded_client.adb:42:7 | UNPROVED |
| C3 | guarded_client.adb:47:7 | UNPROVED |

A1, B1 and C1 are positive controls, not target failures. The six failure
targets reproduce the Task 009 limitation: the original result says only
that `VC_PRECONDITION` is UNPROVED.

### P12. Classification (per call occurrence, per conjunct index)

`status(i)` is the structural status of the occurrence's target in the
run for prefix `i`. For `i = 0` the predecessor is conceptually `TRUE`
(PROVED). The rules apply in this order:

1. The current target is invalid (P9), or the predecessor status is
   missing, invalid or JUSTIFIED: `invalid_probe`.
2. A nested `F` precondition check in the current run is UNPROVED or
   JUSTIFIED: `nested_precondition_unproved`.
3. Predecessor UNPROVED:
   * current UNPROVED: `blocked_by_earlier_prefix`. No claim is made
     about conjunct i.
   * current PROVED: `invalid_probe`. A longer prefix proved after a
     shorter one did not, which is not monotone.
4. Predecessor PROVED, current PROVED: `prefix_proved`. Conjunct i was
   not observed as blocking.
5. Predecessor PROVED, current UNPROVED: `newly_unproved`. Conjunct i
   adds an unproved obligation under the established prefix guards.

`failed`, `culprit` and `root_cause` are never classification values.

### P13. Pre-registered result matrix (18 observations)

| case | caller | call | conjunct | prefix status | classification |
|---|---|---|---|---|---|
| A1 | Guarded_Client.A1_Guard_And_Value | guarded_client.adb:7:7 | 0 | PROVED | prefix_proved |
| A1 | Guarded_Client.A1_Guard_And_Value | guarded_client.adb:7:7 | 1 | PROVED | prefix_proved |
| A2 | Guarded_Client.A2_Guard_Only | guarded_client.adb:12:7 | 0 | PROVED | prefix_proved |
| A2 | Guarded_Client.A2_Guard_Only | guarded_client.adb:12:7 | 1 | UNPROVED | newly_unproved |
| A3 | Guarded_Client.A3_No_Guard | guarded_client.adb:17:7 | 0 | UNPROVED | newly_unproved |
| A3 | Guarded_Client.A3_No_Guard | guarded_client.adb:17:7 | 1 | UNPROVED | blocked_by_earlier_prefix |
| B1 | Guarded_Client.B1_Range_And_Value | guarded_client.adb:22:7 | 0 | PROVED | prefix_proved |
| B1 | Guarded_Client.B1_Range_And_Value | guarded_client.adb:22:7 | 1 | PROVED | prefix_proved |
| B2 | Guarded_Client.B2_Range_Only | guarded_client.adb:27:7 | 0 | PROVED | prefix_proved |
| B2 | Guarded_Client.B2_Range_Only | guarded_client.adb:27:7 | 1 | UNPROVED | newly_unproved |
| B3 | Guarded_Client.B3_No_Range | guarded_client.adb:32:7 | 0 | UNPROVED | newly_unproved |
| B3 | Guarded_Client.B3_No_Range | guarded_client.adb:32:7 | 1 | UNPROVED | blocked_by_earlier_prefix |
| C1 | Guarded_Client.C1_Guard_And_Value | guarded_client.adb:37:7 | 0 | PROVED | prefix_proved |
| C1 | Guarded_Client.C1_Guard_And_Value | guarded_client.adb:37:7 | 1 | PROVED | prefix_proved |
| C2 | Guarded_Client.C2_Guard_Only | guarded_client.adb:42:7 | 0 | PROVED | prefix_proved |
| C2 | Guarded_Client.C2_Guard_Only | guarded_client.adb:42:7 | 1 | UNPROVED | newly_unproved |
| C3 | Guarded_Client.C3_No_Guard | guarded_client.adb:47:7 | 0 | UNPROVED | newly_unproved |
| C3 | Guarded_Client.C3_No_Guard | guarded_client.adb:47:7 | 1 | UNPROVED | blocked_by_earlier_prefix |

Totals: 18 observations, 9 PROVED and 9 UNPROVED prefix statuses,
0 JUSTIFIED. Classifications: `prefix_proved` 9, `newly_unproved` 6,
`blocked_by_earlier_prefix` 3, `nested_precondition_unproved` 0,
`invalid_probe` 0. Each guard family shows the signatures `[P,P]`,
`[P,U]` and `[U,U]`.

### P14. Frozen decision rule

The verdict is **`PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`** only if
ALL of the following hold. Otherwise it is
**`PREFIX_METHOD_NOT_VALIDATED`**.

1. All nine baseline controls match P11.
2. All 18 prefix statuses match P13.
3. All 18 derived classifications match P13.
4. No target result (baseline, observed or untouched) is JUSTIFIED.
5. Every target query matches exactly one structural `VC_PRECONDITION`.
6. No target is disputed (SARIF vs `.spark`).
7. No source-isolation or reparse violation (P6) in any run.
8. No forbidden trust construct in the corpus, and none introduced (P7).
9. All nested-call, guard well-definedness and no-leakage expectations
   of P10 hold in every run.
10. No isolated guarded conjunct was generated: every scratch `Pre`
    re-extracts to a planned source prefix, and the planner refuses the
    selected-only request for every guarded conjunct 1.
11. In every prefix run, all six untouched targets have their baseline
    status.
12. The committed corpus is unchanged by the experiment.

A missing field counts as a failure. This rule is not changed after
results are seen.

### P15. Evidence and determinism

`diagnostics/obj/task013-guarded-reproof/evidence.json` holds canonical
JSON: sorted keys, pre-registered ordering, and no timestamps, absolute
paths or prover messages. Timing goes only into `timing.json`. The
experiment is run twice locally, and `evidence.json` must be
byte-identical. Runtime is measured, but it is not a correctness
condition.

### P16. Permitted interpretation

If validated, the ONLY permitted conclusion is:

> On the controlled access, array-index and nested-call corpus, cumulative
> source-prefix re-proofs preserved preceding short-circuit guards and
> produced the preregistered per-occurrence structural GNATprove evidence.

It does NOT imply any of the following: that arbitrary contracts are
supported; that later conjuncts can be assessed after an unproved prefix;
that a newly-unproved transition is a root cause; that `failed_conjunct`
may be populated in normal reports; that production contracts should be
changed; or that dispatching or generics are handled.

If not validated, no other method is tried in this task. The exact
mismatch is recorded and the next research question is recommended.

### P17. Deferred to Task 014

These are deferred: complex actual/formal mappings (named or reordered
associations, defaults, conversions, `in out`, globals); dispatching;
overload selection; generic instances; realistic-project performance and
GNATprove session reuse; and end-user presentation and CLI
productization. Reason: guard preservation has to be settled before any
broader probe mechanism can be trusted.

## Observed results

Appended after the experiment ran. The pre-registration above is
unchanged: it is byte-identical to preregistration commit `7dcafbb`.

### O1. Verdict

**`PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`**. All twelve P14
conditions hold and `summary.reasons` is empty.

### O2. Extraction and planning (before any proof run)

The Libadalang extraction matched P4 exactly, and it matched Task 009's
`LalBackend.conjuncts`. Each callee has one top-level operator,
`and then`. The planner produced exactly the six P5 prefix texts. Each
final prefix is the unmodified original `Pre`. For each guarded conjunct 1
(`P.all > 0`, `A (I) > 0`, `F (F (X)) > 20`), the recorded selected-only
request was `refused: true` with reason `guarded_and_then_suffix`. No
isolated guarded conjunct was scheduled, generated or proved.

### O3. Source isolation

Each C0-only run changed only `src/guarded_ops.ads`, and only the Pre
bytes after `C0`: 1 file, 1 range, length and newlines preserved. The
three changes, one per run:

```text
<                   and then P.all > 0,
>                                     ,
<                   and then A (I) > 0,
>                                     ,
<                   and then F (F (X)) > 20,
>                                          ,
```

The baseline and the three full-prefix runs are byte-identical to the
corpus (0 changed files). Every scratch `Pre` re-extracted, with zero
diagnostics, to exactly its planned prefix text, conjuncts and operators.
The other callees' `Pre` text and spans were unchanged. `gate_problems`
and `reparse_problems` are empty in all 7 runs.

### O4. Baseline (unmodified copy, 9/9 match)

| case | call | required | observed |
|---|---|---|---|
| A1 | guarded_client.adb:7:7 | PROVED | PROVED |
| A2 | guarded_client.adb:12:7 | UNPROVED | UNPROVED |
| A3 | guarded_client.adb:17:7 | UNPROVED | UNPROVED |
| B1 | guarded_client.adb:22:7 | PROVED | PROVED |
| B2 | guarded_client.adb:27:7 | UNPROVED | UNPROVED |
| B3 | guarded_client.adb:32:7 | UNPROVED | UNPROVED |
| C1 | guarded_client.adb:37:7 | PROVED | PROVED |
| C2 | guarded_client.adb:42:7 | UNPROVED | UNPROVED |
| C3 | guarded_client.adb:47:7 | UNPROVED | UNPROVED |

As in Task 009, the original result shows only a generic
`VC_PRECONDITION` UNPROVED for A2/A3, B2/B3 and C2/C3.

### O5. Prefix matrix (18/18 status, 18/18 classification)

| case | c0 prefix | c1 prefix | c0 classification | c1 classification |
|---|---|---|---|---|
| A1 | PROVED | PROVED | prefix_proved | prefix_proved |
| A2 | PROVED | UNPROVED | prefix_proved | newly_unproved |
| A3 | UNPROVED | UNPROVED | newly_unproved | blocked_by_earlier_prefix |
| B1 | PROVED | PROVED | prefix_proved | prefix_proved |
| B2 | PROVED | UNPROVED | prefix_proved | newly_unproved |
| B3 | UNPROVED | UNPROVED | newly_unproved | blocked_by_earlier_prefix |
| C1 | PROVED | PROVED | prefix_proved | prefix_proved |
| C2 | PROVED | UNPROVED | prefix_proved | newly_unproved |
| C3 | UNPROVED | UNPROVED | newly_unproved | blocked_by_earlier_prefix |

Each observed value equals its pre-registered value. Totals: 18
observations, 9 PROVED, 9 UNPROVED, 0 JUSTIFIED. Classifications:
`prefix_proved` 9, `newly_unproved` 6, `blocked_by_earlier_prefix` 3,
`nested_precondition_unproved` 0, `invalid_probe` 0. Each family showed
`[P,P]`, `[P,U]` and `[U,U]`.

A2, B2 and C2 are distinguished from A3, B3 and C3, although the original
result gives all six the same generic UNPROVED. For A3, B3 and C3 the
experiment makes no claim about conjunct 1.

In every prefix run, all six untouched targets had their baseline
status. All 63 target queries (9 per run × 7 runs) matched exactly one
structural `VC_PRECONDITION`. There were 0 disputed targets and 0
JUSTIFIED targets. The loader recorded 0 SARIF/.spark consistency issues
in any run.

### O6. Nested-call VC inventory (critical gate)

| run | `Guarded_Ops.Use_Nested` `VC_PRECONDITION` checks |
|---|---|
| baseline, use_access_p0/p1, use_index_p0/p1, use_nested_p1 | `guarded_ops.ads:29:28` PROVED, `guarded_ops.ads:29:31` PROVED |
| use_nested_p0 | none (the nested calls are not in the C0-only `Pre`) |

The nested `F` checks have entity `Guarded_Ops.Use_Nested` and locations
inside the callee's `Pre`. The target calls have `Guarded_Client.*`
entities and locations in `guarded_client.adb`. No nested check matched a
target key, so none was folded into a target. None was UNPROVED or
JUSTIFIED, so no probe was `nested_precondition_unproved`.

Guard well-definedness: `VC_NULL_POINTER_DEREFERENCE` at
`guarded_ops.ads:12:30` and `VC_INDEX_CHECK` at `guarded_ops.ads:18:31`
were PROVED in every run whose `Pre` contains them. They were absent in
`use_access_p0` and `use_index_p0` respectively. All 19 other non-target
checks per run were PROVED (flow `GLOBAL_WRONG`, `SUBPROGRAM_TERMINATION`,
`F`'s postcondition and overflow checks). No leakage.

### O7. Trust and corpus

The committed corpus scan found 0 forbidden-trust hits, and no scratch
copy introduced one. The committed corpus digest was unchanged after the
experiment.

### O8. Determinism and runtime (local)

Two full local runs produced a byte-identical `evidence.json`, sha256
`ce4f354b7a300535b8b987524397566f6cbc30ef35936bddbdb71fc36bb76fe5`.
There were 7 GNATprove runs, about 6.3 s each and about 44 s in total. The
whole experiment took about 45 s wall time. Timing is only in
`timing.json`. The hosted CI time is recorded in the pull request.

### O9. Permitted interpretation

The only permitted conclusion is this: *On the controlled access,
array-index and nested-call corpus, cumulative source-prefix re-proofs
preserved preceding short-circuit guards and produced the preregistered
per-occurrence structural GNATprove evidence.*

It does **not** mean any of the following:

* arbitrary contracts are supported;
* later conjuncts can be assessed after an unproved prefix (A3, B3 and C3
  say nothing about conjunct 1);
* a `newly_unproved` transition is a root cause;
* `failed_conjunct` may be populated in normal reports (it stays `null`
  with `attribution: not_provided_by_gnatprove`);
* production contracts should be changed;
* dispatching, overloading or generics are handled;
* any scratch run proves the original program.

The corpus uses only two-conjunct `and then` contracts. Longer chains,
mixed `and` / `and then`, and guards inside nested sub-expressions are
covered by planner unit tests only, not by proof runs.

### O10. Product boundary (verified)

* Normal command output is byte-identical to `origin/main` `4b58e7c`,
  checked with a git worktree and `diff -r` of stdout, stderr and exit
  code. Without Libadalang: 690 files covering `rules`, `explain` and
  `analyze` on every fixture, `compare-provers`, `prove --dry-run`, and
  `--semantic` with and without a project, in text and JSON. With
  Libadalang 26.0.0 under `alr exec`: 72 files covering `explain` with and
  without `--semantic` on every semantic snapshot, in text and JSON.
  Everything is identical, including the Task 010 group sections.
* All 35 precondition entries in the real-Libadalang reports keep
  `failed_conjunct: null` and `attribution: not_provided_by_gnatprove`.
* Nothing changed in `diagnostics/spark_refine_diagnostics/`,
  `pyproject.toml`, `setup_libadalang.sh` or the Task 012 script and
  corpus. The Task 012 experiment still gives
  `VALIDATED_ON_CONTROLLED_CORPUS` with the same `evidence.json` sha256,
  `559ed7e0…`.

### O11. Tests

`diagnostics/tests/test_guarded_reproof.py` has 63 tests: 56 pure and 7
Libadalang. The Libadalang tests are skipped without Libadalang, and CI
forbids skips. The CI step `Task 013: guard-sensitive conjunct re-proof
experiment` in `diagnostics-semantic` runs the seven GNATprove runs. It
fails unless the verdict is `PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`.

### O12. Recommended Task 014 (not started)

A new pre-registered experiment, still without a user CLI:

* **A.** Actual/formal mapping: named and reordered associations,
  defaults, conversions, `in out` parameters and globals read by the
  `Pre`.
* **B.** Dispatching calls (class-wide `Pre`), overload selection and
  generic instances. The target callee must be identified by Libadalang
  resolution, not by name.
* **C.** Longer and mixed chains (`C0 and then C1 and C2`), and guards
  that are not top-level conjuncts (for example inside `if` / `case`
  expressions or quantified expressions), exercised by proof runs.
* **D.** Cost: probes limited to the needed units, GNATprove session or
  `--replay` reuse, and a run-count bound per failure on a realistic
  project (ring buffer / fixed pool).
* **E.** Presentation only after A–D: how prefix-transition evidence
  could be labelled as scratch evidence, if it is ever shown.

