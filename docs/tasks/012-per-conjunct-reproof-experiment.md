# Task 012 — Per-conjunct GNATprove re-proof experiment

Status: pre-registered (this section was committed before any Task 012
probe code was written or any Task 012 GNATprove run was made). Base:
`origin/main` `6a53fb00ddfc709a87d857c10100e6f24d4cf03a` (contains the
reviewed Task 011 head `d0e8555c`). This is an **experiment**. It is not a
product feature and changes no existing diagnostic.

## Pre-registration

This section is frozen at the preregistration commit. Results are appended
below in "Observed results". Nothing in this section is edited after the
experiment has been run.

### P1. Question

Task 009 established that the SARIF/.spark output of FSF GNATprove 16.1.0
does **not** identify which top-level `Pre` conjunct failed. Task 010
grouped repeated failures by identical callee + `Pre` and made no new proof
claim.

Task 012 asks a new question:

> If we make isolated scratch copies of a controlled SPARK program, replace
> a callee's full `Pre` with ONE of its top-level conjuncts, and rerun
> GNATprove, does the resulting call `VC_PRECONDITION` reliably distinguish
> which conjuncts are provable from each caller state?

This produces **new** GNATprove evidence about **scratch programs**. It is
not an inference from the original proof result and it is not proof of the
original program.

### P2. Trust model and vocabulary

GNATprove is the only proof authority. A scratch run proves (or fails to
prove) the scratch program only. The experiment asks exactly:

> With the same caller code and caller assumptions, and with the callee's
> scratch `Pre` replaced by source conjunct Ci, does GNATprove discharge the
> call's `VC_PRECONDITION`?

Allowed vocabulary: *selected-conjunct probe*, *probe proved*, *probe
unproved*, *scratch proof evidence*. The experiment does not speak of root
causes, contract defects, missing contracts, production proofs, or which
conjunct to "fix".

### P3. Corpus (unchanged)

The existing Task 009 corpus,
`diagnostics/tests/semantic_fixtures/conjunct_experiment/`, is used
unchanged (its `src/`, `experiment.gpr`, `results/`, `evidence.json` and
`snapshot.json` are not modified). Committed source sha256 (from its
`snapshot.json`):

| file | sha256 |
|---|---|
| `src/client.adb` | `6c033a9b019f70a1768fae0820e9555f9865448c9be02d3ead58fcfe2e33c51e` |
| `src/client.ads` | `738db3c34770fd711104e0602794890d4b20c56542e582d0d175dd53f1650656` |
| `src/ops.adb` | `4be7470978852f55a16a9a6512af9a77e4637e392873c91811e07ace475dd4b0` |
| `src/ops.ads` | `8ceb30a3a18e075ab308e0565c1f428b38424cd6e30901c2aff348ff0a69939a` |

Relevant declarations:

```ada
procedure Op (X, Y : Integer)
with Pre    => X > 0 and then Y > 0, ...

procedure Op3 (X, Y, Z : Integer)
with Pre    => X > 0
               and Y > 0
               and Z > 0, ...
```

Relevant callers (`client.ads` / `client.adb`):

| caller | caller Pre | call |
|---|---|---|
| `Client.Second_Fails` | `X > 0` | `client.adb:7:10` `Ops.Op (X, Y)` |
| `Client.First_Fails` | `Y > 0` | `client.adb:12:10` `Ops.Op (X, Y)` |
| `Client.Both_Fail` | none | `client.adb:17:10` `Ops.Op (X, Y)` |
| `Client.Middle_Fails` | `X > 0 and Z > 0` | `client.adb:22:10` `Ops.Op3 (X, Y, Z)` |

### P4. Pre-registered extraction

Libadalang identifies `Ops.Op` and `Ops.Op3` and their explicit `Pre`
aspects, and splits top-level `and` / `and then` exactly as Task 009 does
(`semantic_lal.LalBackend.conjuncts`). Before any proof run the extracted
source texts must equal:

```text
Ops.Op   ["X > 0", "Y > 0"]
Ops.Op3  ["X > 0", "Y > 0", "Z > 0"]
```

If they differ, the experiment stops. The expected strings are not updated
to make it pass. Ada is never parsed with regular expressions.

### P5. Pre-registered ground truth (9 observations)

**Ops.Op — conjunct 0: `X > 0`**

| client | call | expected probe |
|---|---|---|
| Client.Second_Fails | client.adb:7:10 | PROVED |
| Client.First_Fails | client.adb:12:10 | UNPROVED |
| Client.Both_Fail | client.adb:17:10 | UNPROVED |

**Ops.Op — conjunct 1: `Y > 0`**

| client | call | expected probe |
|---|---|---|
| Client.Second_Fails | client.adb:7:10 | UNPROVED |
| Client.First_Fails | client.adb:12:10 | PROVED |
| Client.Both_Fail | client.adb:17:10 | UNPROVED |

**Ops.Op3 — Client.Middle_Fails at client.adb:22:10**

| conjunct | text | expected probe |
|---|---|---|
| 0 | `X > 0` | PROVED |
| 1 | `Y > 0` | UNPROVED |
| 2 | `Z > 0` | PROVED |

Total: **9** occurrence/conjunct observations, expected **4 PROVED**,
**5 UNPROVED**, 0 JUSTIFIED.

### P6. Baseline control

Before any probe, one fresh GNATprove run over an unmodified scratch copy
(byte-identical to the committed corpus). Required structural results:

| client | call | required |
|---|---|---|
| Client.Second_Fails | client.adb:7:10 | UNPROVED |
| Client.First_Fails | client.adb:12:10 | UNPROVED |
| Client.Both_Fail | client.adb:17:10 | UNPROVED |
| Client.Middle_Fails | client.adb:22:10 | UNPROVED |

This reproduces Task 009's limitation in the same environment: the
original proof artifacts say only "unproved" for all four.

### P7. Probe method

One independent scratch project per selected callee conjunct:

1. copy the complete experiment project (`experiment.gpr`, `src/*.ad[sb]`;
   real file copies, no symlinks, no committed `obj/`/`results/`) into
   `diagnostics/obj/task012-conjunct-reproof/<run>/`;
2. leave all caller source unchanged;
3. in the scratch copy only, replace the target subprogram's full `Pre`
   expression with one extracted top-level conjunct;
4. run GNATprove;
5. read `VC_PRECONDITION` at every pre-registered call site of that callee.

No `pragma Assert` is inserted into caller code; Ada/GNATprove perform the
actual/formal mapping. Runs: `Ops.Op` x 2, `Ops.Op3` x 3, plus 1 unmodified
control = **6 GNATprove runs**.

### P8. Source transformation

Using the Libadalang source span of the `Pre` expression (never find/replace
by identifier text): every byte of the expression range is replaced by a
space except newline bytes, which are kept; then the selected conjunct text
is written at the start of the range. This preserves file length, newline
count and all line numbers after the expression (each selected conjunct
fits inside the original range). After rewriting: reparse with Libadalang,
require zero parse diagnostics, and require the target's explicit `Pre`
text to be exactly the selected conjunct.

### P9. Source-isolation gate (per probe)

Machine-checked for every probe variant:

* `client.ads`, `client.adb`, `ops.adb`, `experiment.gpr` byte-identical
  to the committed corpus;
* only `ops.ads` differs, and only inside the Libadalang-identified original
  `Pre` expression byte range;
* recorded `changed_file_count = 1`, `changed_range_count = 1`.

The committed source tree is hashed before and after the experiment and must
be unchanged. Destructive filesystem operations are refused unless the
resolved path is below `diagnostics/obj/task012-conjunct-reproof`.

### P10. Forbidden trust constructs

Both the committed corpus and every scratch corpus are scanned before proof
for: `pragma Assume`, `pragma Annotate` with `False_Positive` or
`Intentional`, `Suppress`, `SPARK_Mode => Off`, and axiom mechanisms
(`Annotate` with `Axiom`/`Skip_Proof`/`Skip_Flow_And_Proof`, bodyless ghost
subprograms introduced by the scratch copy). Detection uses Libadalang
pragma/aspect nodes, not English messages. Any hit introduced by a scratch
copy is an experiment failure.

### P11. GNATprove configuration

Pinned FSF GNATprove 16.1.0 (`alr -n exec --` in `examples/ring_buffer`, as
Task 009's `capture_semantic_fixtures.py produce`), the project's own proof
switches (`-U --mode=all --level=2 --report=statistics`) plus `-j0`. The
exit code and English messages are never used to decide an outcome.

### P12. Structural outcome reading

Results are read with the existing loader (`spark_refine_diagnostics.loader
.load_run`; SARIF `kind`/`suppressions` status classification). For each
pre-registered target (file, line, column, client entity) there must be
**exactly one** `VC_PRECONDITION` check. Zero or more than one is an
experiment failure (no picking). Status PROVED / UNPROVED / JUSTIFIED;
JUSTIFIED is an experiment failure. A target the loader marks `disputed`
(SARIF/.spark disagreement) is also a failure.

### P13. Critical discrimination control

In the original result `Client.First_Fails` and `Client.Both_Fail` are both
simply `VC_PRECONDITION` UNPROVED, and Task 009 showed their result shapes
carry no conjunct attribution. Expected probe signatures over `Ops.Op`
conjuncts [0, 1]:

```text
First_Fails: [UNPROVED, PROVED]
Both_Fail:   [UNPROVED, UNPROVED]
```

If these are not observed, the method has not demonstrated added
discriminating evidence.

### P14. Decision rule (frozen)

Verdict `VALIDATED_ON_CONTROLLED_CORPUS` only if **all** hold:

1. baseline control 4/4 as in P6;
2. all 9 probe observations equal P5;
3. no target result is JUSTIFIED;
4. every target query matches exactly one structural VC;
5. every scratch mutation passes the P9 source-isolation gate (and the P4
   extraction and P8 reparse checks pass);
6. no forbidden trust construct (P10) is introduced.

Otherwise `NOT_VALIDATED`. Percentages are not reported as a product
accuracy claim. This rule is not weakened after seeing results.

### P15. Scope and pre-declared limitations

Replacing `Pre => A and then B` by `Pre => B` does **not** in general
preserve the short-circuit guard assumptions that `A` provides to `B`. The
selected conjuncts here (`X > 0`, `Y > 0`, `Z > 0`) are independent, total
integer comparisons, so no guard is lost. A success validates only this
corpus. It is **not** evidence about pointer/null guards, array bounds
guarded by another conjunct, nested calls whose own `Pre` depends on an
earlier conjunct, partial expressions, or arbitrary `and then` contracts.
`Ops.Nested_Calls` is deliberately not used.

A Task 010 group (identical callee + `Pre`) does not mean one probe result
applies to all its occurrences: different calls have different caller
states. The contract is rewritten once per conjunct, but every call
occurrence is read independently, keyed by client entity and call location.

### P16. What a success would mean

Only: *for this controlled corpus of independent total top-level
conjuncts, independently re-running GNATprove with a scratch callee `Pre`
containing one conjunct provides the expected per-occurrence proof
evidence.* It would not mean that arbitrary conjuncts can be isolated, that
short-circuit-dependent conjuncts are handled, that Task 009's
`failed_conjunct` may now be populated, that contracts should be rewritten,
that a missing public fact has been identified, or that the original
program is proved by any scratch run.

### P17. Product boundary

No new rule (no SRD004), no CLI command or flag, no change to SRD001-SRD003,
`semantic.py`, `semantic_lal.py`, `semantic_groups.py`, `semantic_shape.py`,
text rendering or JSON. Normal reports keep `failed_conjunct: null` and
`attribution: not_provided_by_gnatprove`. The experiment lives in
`diagnostics/scripts/conjunct_reproof_experiment.py` (outside the installed
package); its generated trees and `evidence.json` stay under the gitignored
`diagnostics/obj/task012-conjunct-reproof/`.
