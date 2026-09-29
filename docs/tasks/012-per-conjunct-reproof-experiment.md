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

## Observed results

Appended after the preregistration commit `f55a59c5` and the local runs.
The preregistration section above is unchanged.

### Verdict: VALIDATED_ON_CONTROLLED_CORPUS

On this controlled corpus of independent total top-level conjuncts,
re-running GNATprove separately with a scratch callee `Pre` that contains
one conjunct gave exactly the expected per-occurrence proof evidence. Read
this narrowly (see O7).

### O1. Preconditions

* **Corpus identity.** The committed sources match the pre-registered
  sha256 values. The `sha256sum` digest of the git-tracked corpus files
  (`src/`, `results/`, `experiment.gpr`, `evidence.json`,
  `snapshot.json`) was
  `30f6a2d00104e866b87ee9eb5e91b589794b4799f9b8013dffb84f0f28b956d7`
  before and after the runs. The script also compares a whole-tree digest
  (`corpus_unchanged: true`).
* **Extraction (Libadalang, Task 009's `LalBackend.conjuncts`):**
  * `Ops.Op`: `X > 0 and then Y > 0`, at `ops.ads` 4:19-4:39, gives
    `["X > 0", "Y > 0"]`.
  * `Ops.Op3`: three lines at 8:19-10:28, gives
    `["X > 0", "Y > 0", "Z > 0"]`.

  Both equal P4.
* **Forbidden-trust scan** (Libadalang pragma/aspect nodes plus bodyless
  ghost declarations). Committed corpus: 0 hits. Baseline copy: 0 hits.
  Introduced by each of the 5 probe copies: 0.

### O2. Baseline control (fresh, unmodified, byte-identical copy)

| client | call | observed |
|---|---|---|
| Client.Second_Fails | client.adb:7:10 | UNPROVED |
| Client.First_Fails | client.adb:12:10 | UNPROVED |
| Client.Both_Fail | client.adb:17:10 | UNPROVED |
| Client.Middle_Fails | client.adb:22:10 | UNPROVED |

4/4, as required. `baseline_isolation.changed_file_count = 0`. As in Task
009, the original proof shows all four only as "unproved".

### O3. Source isolation (every probe)

The script copied these files as real files (bytes only, no symlinks):
`experiment.gpr`, `src/client.adb`, `src/client.ads`, `src/ops.adb` and
`src/ops.ads`. Only `src/ops.ads` is rewritten, and only inside the
Libadalang range of the target `Pre` expression. Every probe recorded
`changed_files = ["src/ops.ads"]`, `changed_file_count = 1`,
`changed_range_count = 1`, length preserved, newline positions preserved,
and `gate_problems = []`. Every reparse had zero diagnostics, and the
target `Pre` was exactly the selected conjunct. For example, the `Ops.Op`
conjunct 1 probe changes line 4 only:

```text
<    with Pre    => X > 0 and then Y > 0,
>    with Pre    => Y > 0               ,
```

### O4. Full observed matrix (9 observations)

| callee | conjunct | client | call | pre-registered | observed |
|---|---|---|---|---|---|
| Ops.Op | 0 `X > 0` | Client.Second_Fails | client.adb:7:10 | PROVED | PROVED |
| Ops.Op | 0 `X > 0` | Client.First_Fails | client.adb:12:10 | UNPROVED | UNPROVED |
| Ops.Op | 0 `X > 0` | Client.Both_Fail | client.adb:17:10 | UNPROVED | UNPROVED |
| Ops.Op | 1 `Y > 0` | Client.Second_Fails | client.adb:7:10 | UNPROVED | UNPROVED |
| Ops.Op | 1 `Y > 0` | Client.First_Fails | client.adb:12:10 | PROVED | PROVED |
| Ops.Op | 1 `Y > 0` | Client.Both_Fail | client.adb:17:10 | UNPROVED | UNPROVED |
| Ops.Op3 | 0 `X > 0` | Client.Middle_Fails | client.adb:22:10 | PROVED | PROVED |
| Ops.Op3 | 1 `Y > 0` | Client.Middle_Fails | client.adb:22:10 | UNPROVED | UNPROVED |
| Ops.Op3 | 2 `Z > 0` | Client.Middle_Fails | client.adb:22:10 | PROVED | PROVED |

| | expected | observed |
|---|---|---|
| PROVED | 4 | 4 |
| UNPROVED | 5 | 5 |
| JUSTIFIED | 0 | 0 |
| matches ground truth | 9 | 9 |

Every one of the 13 target queries (4 baseline plus 9 probe) matched
exactly one structural `VC_PRECONDITION` for the expected client entity.
None of those checks was disputed by the loader (SARIF vs `.spark`).

### O5. Critical discrimination control

| client | original result | probe signature over `Ops.Op` [c0, c1] |
|---|---|---|
| Client.First_Fails | VC_PRECONDITION UNPROVED | [UNPROVED, PROVED] |
| Client.Both_Fail | VC_PRECONDITION UNPROVED | [UNPROVED, UNPROVED] |

The two calls are **distinguished**. In the original result their shapes
are structurally identical (Task 009 `ConjunctExperiment`). The scratch
probes supply new GNATprove evidence that tells them apart.

### O6. Determinism and runtime (local)

A second full run produced a byte-identical `evidence.json` (sha256
`559ed7e03dd51ccba3e0c71f1083f39a50539037791ca7216ac8ae28a02be630`).
Local wall time for the whole experiment was about 9 s. The six
GNATprove runs took about 8.5 s in total, roughly 1.4 s each. Runtime is
measurement only: `timing.json` is kept separate from `evidence.json`. The
hosted CI timing is recorded in the pull request.

### O7. Permitted interpretation

The verdict permits only this statement: *for this controlled corpus of
independent total top-level conjuncts, re-running GNATprove separately
with a scratch callee `Pre` that contains one conjunct gave the expected
per-occurrence proof evidence.*

It does **not** mean any of the following:

* arbitrary `Pre` conjuncts can be isolated safely;
* short-circuit-dependent (`and then` guard) conjuncts are handled;
* Task 009's `failed_conjunct` may be populated (it stays `null` with
  `attribution: not_provided_by_gnatprove`);
* the product should rewrite contracts automatically;
* a missing public fact has been identified;
* the original program is proved by any scratch run.

Scratch results prove scratch programs only.

### O8. Limitations (not generalised)

These cases are outside the evidence: pointer/null guards; array bounds
guarded by another conjunct; selected conjuncts that contain calls with
their own `Pre` (`Ops.Nested_Calls` was deliberately not used); partial
expressions; arbitrary `and then` contracts; complex actual/formal
mappings (defaults, named or reordered associations, conversions);
dispatching, overloading and generics; and cost on realistic projects,
where each probe is a full GNATprove run. The overlay method needs ASCII,
LF-only, tab-free source, and it needs each conjunct to fit on the first
line of the original range. The script stops if either condition fails.

A Task 010 group does not transfer one probe result to all of its
occurrences. In this corpus, `Ops.Op` conjunct 0 is PROVED for
`Second_Fails` and UNPROVED for `First_Fails` and `Both_Fail`, all within
one callee/`Pre` group. The contract is rewritten once per conjunct, but
every occurrence is read on its own, keyed by client entity and call
location.

### O9. Product boundary (verified)

* Normal command output is byte-identical to `origin/main`. This was
  checked with a git worktree of `6a53fb00` and `diff -r`. Without
  Libadalang: 684 files (stdout, stderr and exit code) covering `rules`,
  `explain` and `analyze` on every fixture, `compare-provers`,
  `prove --dry-run`, and `--semantic` with and without a project, in text
  and JSON. With real Libadalang 26.0.0 under `alr exec`: 84 files
  covering `explain` with and without `--semantic` on every semantic
  snapshot, and `prove` with a fake GNATprove, in text and JSON. All are
  identical.
* In those real-Libadalang reports all 35 precondition entries keep
  `failed_conjunct: null` and `attribution: not_provided_by_gnatprove`.
* The task changes nothing in `diagnostics/spark_refine_diagnostics/`,
  `pyproject.toml` or `setup_libadalang.sh`, so the Libadalang cache key
  is unchanged. It adds no rule and no CLI command or flag.

### O10. Tests

`diagnostics/tests/test_conjunct_reproof.py` has 43 tests: 38 pure (no
Libadalang, no GNATprove) and 5 Libadalang transformation tests, which
are skipped without Libadalang. CI step
`Task 012: per-conjunct re-proof experiment` in `diagnostics-semantic`
runs the six GNATprove runs and fails unless the verdict is
`VALIDATED_ON_CONTROLLED_CORPUS`.

### O11. Recommended Task 013 (not started)

Before any user-facing CLI, address these in a new pre-registered
experiment:

* **A.** Guard-dependent `and then` conjuncts. Probe conjunct *i* under
  the conjunction of conjuncts 0..*i*-1 as a guard (for example
  `Pre => C0 and then ... and then Ci`, reading a prefix difference), or
  prove that the guard does not matter. Include null/pointer and index
  guards.
* **B.** Selected conjuncts that contain calls with their own `Pre`
  (`Ops.Nested_Calls`). Check that the probe VC at the call site stays
  one check and that nested-call checks do not leak into it.
* **C.** Complex actual/formal mappings: named and reordered
  associations, defaults, conversions, and `in out` / global state.
* **D.** Dispatching, overloading and generic instances.
* **E.** Cost on realistic projects: probes limited to the units that
  are needed, reuse of the GNATprove session, and the run count per
  failure.
* **F.** Presentation. Decide how new scratch-proof evidence could be
  shown, if ever, without it being confused with the production proof or
  with Task 009's `failed_conjunct` policy.
