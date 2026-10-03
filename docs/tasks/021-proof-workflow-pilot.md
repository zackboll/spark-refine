# Task 021 — bounded proof-maintenance workflow pilot

## Scope recorded before editing

One observed agent-development session on a known historical revision, not
a blinded experiment, control-arm comparison, speedup measurement or current
upstream vulnerability discovery. Task 019 remains closed; Task 022 is not
started. GNATprove remains proof authority.

Fetched origin, checked an empty working tree and verified reviewed Task 020
head `f0141a4d21e57113c955cbab2720f6686f931dc8` is an ancestor of actual
starting main **`713bd41e9601587fd54d7324a57aef3268b8105f`**. Branch:
`feature/021-proof-workflow-pilot`.

External base: `https://github.com/bladeacer/Ada_CRDT.git`,
**`5fa2c0cee62deb86368fcc84a8d3b06726028276`**; tree
`1d85fadb5c0efeb4b39e72a345341b05847a25ac`. New detached disposable checkout:
`/home/zboll/git/spark-refine/diagnostics/obj/task021-workflow/working`.
Cloned objects from Task 017 using `--no-hardlinks --no-checkout`; no historical
worktree/artifacts are used as the editable worktree. Preserved `git archive
HEAD` before edits (SHA-256
`ae91148e40c0621156f2b5822a37195cbc97691cf4f96d28b93d8397c3ec87fb`).

Only `src/security/crdt-security-sha256.adb`, inside `Update`, may change.
All specifications, constants, other bodies and other SHA256 routines remain
byte-identical. Preserve arbitrary legal array bounds/null slices, streaming,
byte order, modular bit counter and no-heap design. No upstream push, issue,
PR, deployment, control-revision modification or later-fix copying.

Session began `2026-10-03T02:23:01-04:00`. Setup budget: 20 minutes from the
recorded setup-start timestamp; active repair budget: 90 minutes; at most six
candidate functional proofs after baseline, including two final unchanged
clean confirmations. Stop at the first applicable limit. No extra resources,
loop unrolling, proof suppression, new trust boundary or contract change.

Installed FSF GNATprove 16.1.0 / Why3 1.8.2+git, Alire 2.1.1. Reuse Task
017's publishing manifest, dependency-free root `crdt.gpr`, and proof policy
`-j 30 --steps 10000 --no-loop-unrolling`. Each proof uses a new `--subdirs`
value throughout the project closure and `--output-header`; actual output
locations will be observed, not guessed. Proof through installed current CLI:
`/home/zboll/git/spark-refine/diagnostics/obj/task021-workflow/venv/bin/spark-refine`.
Editable install imports
`/home/zboll/git/spark-refine/diagnostics/spark_refine_diagnostics/__init__.py`,
version `0.0.0.dev0`, at starting main. No product edits permitted.

Intended runtime checks: upstream SHA256 tests plus independent Python hashlib
oracles for empty/short input, lengths 55, 56, 63, 64, 65, 127, 128, 129;
one-shot, one-byte and irregular streaming, intervening empty chunks,
non-one-origin arrays and null slices. Separate external driver/build project;
normal and assertions-enabled builds, with exact inputs/chunking retained.
These checks are not a full cryptographic proof or certification.

## Observations and outcome

Setup `02:23:47–02:24:50 -04:00`: 63 seconds, within 20 minutes. First
launch failed before GNATprove because `/usr/bin/time` was absent; switched
to Python standard-library monotonic timing. This was not a proof invocation.
An auxiliary piped `alr exec -- gnat --version | head -1` printed the version
then an Alire pipe error; functional proof was unaffected.

Fresh baseline: 20.531 seconds, wrapper/GNATprove exit 0, selected
`obj/task021-baseline/gnatprove` by `fresh_discovery`. Header records FSF
16.1.0 and the exact command. Actual worklist: 11 overall, 3 target, 8 LMS.
Native summary: 1006 checks; normalized loader: 1009 (three disputed proved
SARIF `error` entries with no matching `.spark`). SRD001/SRD002 evaluated,
zero findings, ALI `ok`, `GNAT Lib v16`. No semantic enrichment requested.
Existing 13 notes: three consistency disputes and ten partial generic-unit
analysis notices. Exit 0 is not proof success.

Selected from `analysis.unproved_checks.items` (all entity
`CRDT.Security.SHA256.Update`, undisputed, file `crdt-security-sha256.adb`):

| Rule | Location | Original GNATprove message |
|---|---|---|
| VC_OVERFLOW_CHECK | 112:44 | overflow check might fail, cannot prove lower bound for (Long_Long_Integer (Bytes'Last) - Long_Long_Integer (Bytes'First)) |
| VC_OVERFLOW_CHECK | 112:79 | overflow check might fail, cannot prove upper bound for (Long_Long_Integer (Bytes'Last) - Long_Long_Integer (Bytes'First)) + 1 |
| ALIASING | 125:23 | formal parameters "Ctx" and "Block" are aliased (SPARK RM 6.4.2) |

The tool supplied this normalized enumeration, dispute flags, rule states,
fresh selection and notes; GNATprove already supplied the rules, locations
and messages. Source/specification inspection supplied the repair reasoning:
`Byte_Array` is `Ada.Streams.Stream_Element_Array`; no Pre restricts bounds;
`Count` is mod `2**64`; `Compress` reads `Block`, writes only `Ctx.H`, and
does not inspect `Len`, `BufN` or modify `Buf`. Per-byte modular increments
therefore give the same final counter, including wrap, independently of
array origins, and a full-block local value preserves byte order.

### Candidate 1 — journal before editing/running

Hypothesis: eliminate signed bound arithmetic by incrementing the existing
modular counter once per consumed byte; pass an independent 64-byte constant
copy to `Compress`. No helper or specification change. Null inputs execute
zero iterations; streaming and modular count are preserved. Expected proof:
no overflow from signed subtraction/addition, and a non-aliased call with
the same full block. Review the new path's flow/initialization/index coverage,
not just vanished old locations. Cost: one counter addition per byte rather
than one per nonempty call, plus 64 bytes of local storage and one 64-byte
copy per full block (compiler optimizations not measured).

Active repair timer starts immediately before this edit; budget 90 minutes.
Candidate count is initially zero; next run uses `task021-candidate1`.
Raw logs/build trees remain ignored.

Candidate 1 result: 13.798 seconds, GNATprove/wrapper exit 0, 0 target /
8 other unproved. Core notes and rule-evaluation states unchanged; the
orchestration note correctly changes exit-0/unproved count from 11 to 8. All 39 unit
names/stop reasons unchanged. SHA256 has `STOP_REASON_NONE`; native report
explicitly lists `Update` as flow analyzed with zero errors/checks/warnings
and proved (1 check), and the normalized checks show its buffer-count range,
Depends and inlined compression initialization checks proved. No helper was
introduced. The two signed-arithmetic VCs were eliminated by replacing the
unsafe operation, not paired to imaginary cross-revision VCs. Copy removes
the prohibited alias; compression's existing inlined path remains analyzed.
Next action: runtime checks and two clean unchanged confirmations.

### Candidate runs 2 and 3 — journal before running

Hypothesis: unchanged candidate 1 is reproducible from wholly isolated fresh
output. Source change: none; same source hash. Requirements: unchanged from
candidate 1. Expected proof consequence: 0 target / 8 unchanged LMS failures,
same 39-unit scope, existing disputes/partial-analysis notes still visible.
These are the two requested final confirmations; sequential runs with unique
`task021-confirm1` and `task021-confirm2` subdirectories, no concurrent proof.

## Final acceptance and bounded effort

**Repair outcome: `TARGET_REPAIRED_AND_VALIDATED`.** This is a target repair,
not a whole-project proof. Workflow assessment: **usable but little
incremental value observed**. No product defect was demonstrated; another
product change is not justified by this session.

| Invocation | Isolated subdir | Elapsed seconds | GNATprove / wrapper rc | Target unproved | Other / overall unproved |
|---|---|---:|---|---:|---|
| Baseline | task021-baseline | 20.531 | 0 / 0 | 3 | 8 / 11 |
| Candidate 1 | task021-candidate1 | 13.798 | 0 / 0 | 0 | 8 / 8 |
| Final clean confirmation 1 (candidate run 2) | task021-confirm1 | 13.677 | 0 / 0 | 0 | 8 / 8 |
| Final clean confirmation 2 (candidate run 3) | task021-confirm2 | 13.519 | 0 / 0 | 0 | 8 / 8 |

Confirmation 1 post-run journal: unchanged source, 13.677 seconds, rc 0,
0 target / 8 other; no new consistency/coverage note, existing core notes
retained. Next action: the already planned second isolated confirmation.
Confirmation 2 post-run journal: unchanged source, 13.519 seconds, rc 0,
0 target / 8 other; same core notes/scope, no new trust. Next action: stop
external proof runs and finish runtime/evidence review and delivery.

All proofs used the same policy and unchanged root project. Baseline command:

```sh
alr exec -- spark-refine prove -P crdt.gpr --show-unproved --format json -- \
  -j 30 --steps 10000 --no-loop-unrolling --subdirs=task021-baseline --output-header
```

For candidate/confirmations, identical command with that run's `--subdirs`
and `--results obj/SUBDIR/gnatprove` before the separator. Baseline first
observed the actual output via fresh discovery, then explicit selection used
the confirmed layout. The full commands, invocation headers, actual result
paths, timings, rule states and before/after worklists are retained in
[observations.json](../examples/task021/observations.json). Local raw logs and
reports live in `/home/zboll/git/spark-refine/diagnostics/obj/task021-workflow/`
under each run name; raw SARIF, `.spark`, `.ali`, `gnatprove.out` live under
`working/obj/SUBDIR/gnatprove`. Each run produced 1 SARIF, 39 `.spark`, 39
`.ali`, all newer than that run's start; no previous run's outputs were reused
or deleted. `--subdirs` applies to the project closure; here the root GPR has
no imported project dependency. Full logs/build trees/caches are not committed.

One distinct intentional candidate source revision; three of six allowed
candidate proof invocations used. No scoped exploratory proof, changed proof
resources or hidden helper. Setup recovery: 63 seconds; initial repository /
documentation context gathering began 46 seconds earlier. Repair/edit/runtime
and patch-check phase: `02:28:04–02:32:58`, 4 minutes 54 seconds. Including
post-run scope/dispute/hash review, independent runtime rechecks and acceptance:
`02:28:04–02:39:05`, **11 minutes 1 second** wall time (includes proof waits;
not CPU effort). All within budget. Documentation/delivery validation afterward
is not an additional repair campaign. Human interventions requested: **0**.
Token usage: **unavailable/null**; human effort and GNATprove-only comparison
effort were not measured.

### Permitted diff and hashes

The working external checkout is intentionally **not tracked-clean**:
`M src/security/crdt-security-sha256.adb`, only 8 insertions / 15 deletions
inside `Update`. [Minimal patch](../examples/task021/sha256-update.patch),
with [upstream MIT attribution](../examples/task021/UPSTREAM-LICENSE.txt).
No constants, `Compress`, `Init`, `Final`, `Digest`, other implementation,
manifest/GPR, or public/private declaration changed. Comparison of the prefix
before `Update` and suffix after `end Update;` was byte-for-byte, not a claim
based merely on `git diff --stat`.

| Content | SHA-256 |
|---|---|
| Original SHA256 body | `ca5277b9ec7c88c320a6e3408d79f5d2baa0d12a655eeb45ce29a20e97c94146` |
| Candidate/final body (identical in both confirmations) | `9759e46bde9ed11f33f1b0f9e57b9a2ba5806e7232e9e2b577b61891ae0d8a5f` |
| Retained patch (one-line diff context) | `604692b8ec58ac1adefd7491b5084af377e61b54fd824daa12a34af9ac8c9bc4` |
| Unchanged SHA256 spec, including private representation | `efc291cce9080e5c3d40655e32c08b976afa567fdc898c8fb0cbca279af974b1` |

All **45 tracked upstream `.ads` files** retain their original individual
hashes, saved in observations. All other tracked files retain their hashes.
The preserved starting archive includes the exact original source tree;
`starting-files.sha256` retains its file inventory locally. A second NEW
disposable clone `diagnostics/obj/task021-workflow/patch-check`, detached at
the exact base, accepted `git apply --check`, then the patch; patched body
matched the working body byte-for-byte and `git diff --check` passed.

Task 017 failing/control tracked statuses and diffs remain empty at their
original SHAs. Before/after content-hash inventories of their SARIF/.spark/ALI
and Task 020 artifact files compare identically. No historical checkout,
control source or evidence was modified. No later upstream fix was read/copied.

### Proof scope, disputes and limitations

Both confirmations: 0 target unproved, 8 overall; SHA256
`STOP_REASON_NONE`, 19 proof entries / 36 flow entries / 0 unproved (baseline
22 / 37 / 3). Native `Update` coverage: flow analyzed, zero errors/checks/
warnings/Assume, proved (1 check). The candidate's normalized target checks
also retain inlined `Compress` initialization and Depends coverage. No helper
or trusted boundary was introduced. The counter uses native modular arithmetic
with no signed bound subtraction, length conversion, or heap object. Null
ranges make no change, and full buffers are copied before compression.

Native totals: 1006 before, 1002 after; normalized totals: 1009 before, 1005
after. The reduction is not a stable-VC discharge metric: unsafe signed
operations and an aliasing call were replaced, with one unnecessary conversion
check also removed. Manual review of the actual changed path and coverage is
the acceptance basis; changed-source checks were not paired by source order
or line/column identity. All normalized check occurrences outside SHA256
match as multisets after excluding nondeterministic prover statistics, on
byte-unchanged source. The eight unchanged LMS obligations are seven overflow
and one postcondition, all undisputed; no outside regression was introduced.

All 39 analyzed unit names and stop reasons remain the same. Three proved
SARIF `error`-rule entries (LMS 193:14, SHA256 62:14, HMAC 14:13) still have no
matching `.spark` entry: **disputed, not independently resolved or extra
functional VCs**. All three consistency notes and ten generic partial-analysis
notes remain visible; exit-0-with-failures note correctly changes from 11 to 8.
SRD001 and ALI-backed SRD002 remain evaluated with zero findings; ALI status
`ok`, version `GNAT Lib v16`. SRD003 is not evaluated in this single-portfolio
workflow. No semantic/SRD diagnosis was forced.

The 36 native tool warnings remain, with three unchanged SHA256 warnings
moving up seven lines according to the exact diff (array-initialization
imprecision in Final and unused final context in Digest). This manual mapping
was checked, not inferred from source-order pairing. Existing native skipped
subprogram reports also compare identically. Existing non-SPARK boundaries
include clock/PN-counter I/O, HLC time access, serialization and test support;
generic/template/instance skips also remain. The report's generic notes are
not a full list of every native skipped body. No independent whole-repository
audit, whole-project proof, complete cryptographic-correctness proof or
security certification is claimed. Justified checks and pragma Assume counts
remain zero in the loaded analysis; no new suppression/trust shortcut,
contract weakening or public input-domain narrowing was introduced.

### Independent runtime validation

Both separate focused builds pass **120 cases**, with one-shot and streaming
digests checked for each (240 digest comparisons per build) against Python
standard-library `hashlib`, not against the modified algorithm as oracle.
[Exact bytes, origins, chunks and digests](../examples/task021/runtime_cases.json)
and [driver/checker](../examples/task021/README.md) are retained. Empty and
`abc`; patterned lengths 55, 56, 63, 64, 65, 127, 128, 129; whole, one-byte,
irregular chunks, including an empty between nonempty chunks and block crossing.
Origins: 1, -17, signed-offset minimum, and the origin that makes the last
element the signed-offset maximum. Small arrays only (maximum 129 bytes).
Every zero chunk exercises both an extreme null array `Offset'Last ..
Offset'First` and a legal null slice `1 .. 0`. Empty one-shot input also uses
extreme null bounds. This checks the originally unsafe null-bound case without
enormous allocations; proof analyzes general arithmetic obligations.

Normal focused build: no `-gnata`. Assertions focused build: clean separate
objects, `-cargs:Ada -gnata` for the entire compiled four-unit closure (driver,
CRDT, CRDT.Security, SHA256), not just the driver. Separate upstream root build
uses its original `-gnata` switches. Existing upstream `test_crdt`: **10,332
passed, 0 failed**, including all five SHA256 vector/streaming checks and its
15 security checks. No swallowed exception, spec change, or proof-project
inclusion of the external runtime driver. These finite tests and existing
contracts do not prove full cryptographic correctness or security.

## Observed tool contribution versus other reasoning

| Step | spark-refine supplied | Already native / agent supplied |
|---|---|---|
| Select work | `analysis.unproved_checks.items`, by-rule counts, entity/unit/location/message/disputed | GNATprove already supplies messages and locations; known target selected by task |
| Establish fresh result | orchestration command, exit code, freshness, actual result path, explicit selection | agent chose new subdirs and inspected native header/tool versions |
| Review remaining work | 11→8 inventory; no SRD findings while rules evaluated; core notes | native has same failures; agent checked unchanged source and no outside regressions |
| Review incomplete evidence | consistency notes and generic partial-analysis notices; existing loader's UnitResults/disputed checks | native detailed report required for subprogram coverage and full existing skipped-body inventory |
| Design repair | no automatic repair or root-cause diagnosis | source/spec review established Count, bounds, Compress's reads/writes and independent-copy reasoning |
| Validate behavior | no runtime oracle | agent driver plus independent hashlib; upstream tests; no speed/accuracy comparator |

Fields actually used: `analysis.unproved_checks` items/count/by_rule;
`analysis.orchestration` command/result path/fresh/selection/exit code;
`analysis.rules` evaluation and ALI status; `notes`, run summaries and zero
diagnostic summary. Existing loader supplied unit stop reasons/entry counts,
disputed Check objects and justification/Assume counts. The worklist removed
bespoke **failure** parsing/counting: target was selected by its reported
entity and array lengths/count fields, not log regex or a new SARIF parser.
An ignored 128-line one-off extraction/checking script using `load_run` saved
the compact excerpt and compared hashes/scope; it is not a runner, product
command or reusable evidence framework. Manual scope/diff review was still
necessary; full dataclass comparison initially included nondeterministic
prover times, so comparison explicitly excludes statistics. Moving unchanged
warnings also needed diff-based review. No manual failure tally was needed.

Raw/source/documentation lookups: baseline/candidate `gnatprove.out` headers,
native detailed per-subprogram/skipped coverage and summary; full SHA256 body
and specification, existing tests and license. No counterexample lookup was
needed. Official [SPARK RM 6.4.2 anti-aliasing](https://docs.adacore.com/spark2014-docs/html/lrm/subprograms.html#anti-aliasing)
corroborated mutable/immutable overlapping-actual restrictions; fetched online
docs identify themselves as 28.0w, not the installed compiler's version.
The first extraction was truncated before the relevant section, requiring a
focused section lookup. An Ada RM array-length URL fetch failed; no repair
relied on it and the chosen per-byte counter avoids Length conversion entirely.

**Explicit workflow answers:**

* Worklist removed bespoke failure parsing/counting: **yes**, but not manual
  source/coverage reasoning or compact evidence extraction.
* Fresh-result workflow straightforward: **yes here**, using a new supported
  subdir and observing the path before explicit selection. No stale-output or
  old-install ambiguity. User discipline around isolation still matters.
* Remaining obligations/incomplete analysis easy to see: **yes at unit/worklist
  level**; detailed subprogram skips/inlined coverage still required native
  output and loader objects. A smaller failure count alone was insufficient.
* Misleading/obstructive product behavior: **none observed**. Exit 0 was clearly
  accompanied by the unproved-count warning. No SRD was falsely forced. Native
  versus normalized totals differ by the three visible disputes, requiring
  attention; the worklist itself does not explain repair or certification.
  Launcher timing/pipe mistakes and a background heredoc that consumed no input
  were session-environment friction, not product defects; that empty launcher
  started no GNATprove and consumed no proof attempt.
* Would native output alone be straightforward: **probably yes** for these
  three localized messages, the clear spec and small body. The structured
  worklist/dispute/freshness information was convenient, but incremental benefit
  was small in this known case. There is no control arm or causal comparison.

No percentage speedup, token reduction, improved accuracy, autonomous repair,
current upstream vulnerability or general productivity claim. The agent made
the patch; spark-refine reported GNATprove's evidence. At most one next action:
**review this report/patch as a scoped historical maintenance example**; no
new product feature or automatic additional usage campaign is warranted.

## Repository validation and delivery

Linux x86_64, kernel `6.12.111+deb13-amd64`, Python 3.13.5; GNAT 16.1.0,
GNATprove FSF 16.1.0, Why3 1.8.2+git, CVC5 1.3.2, Z3 4.15.4, Alt-Ergo 2.6.1,
Alire 2.1.1. Prover defaults unchanged; no substituted newer tool.

Structural check passes (54 required files); root tests 4/4 pass; diagnostics
fixture suite 486 tests, OK with 35 existing optional Libadalang skips; wheel
and editable packaging smoke tests pass; existing fresh diagnostics E2E 5/5
pass. These regression proofs are on the product's existing fixtures, separate
from the four external proof invocations above. Patch-application and focused
runtime checks pass. No modifications under
`diagnostics/spark_refine_diagnostics/`, diagnostic expectations, bitmap source
or evidence, Prefix_Sets, or historical Tasks 015–020. Existing CI jobs remain
unchanged; no external proof/cloning/agent execution added to CI.

Runtime artifact SHA-256: driver
`11d77f032d88eea2eceed05c768b99ff069403c785ba1aa53cb387901dc79468`;
saved exact cases
`cdc3476bd94183e4202da1fdb5ad6bc81bd626cb5c5b3ad982d2b3949e267c6f`.

The retained patch uses one context line: default Git diff's space-only blank
context line failed the outer repository's whitespace check. Reducing context
changed patch serialization/hash, not candidate source. Rechecked reverse to
the exact clean base, `git apply --check`, forward apply and byte equality.

Final SHA/PR identity, local/remote/PR head equality, final `git diff --check`
and the single exact-head CI observation are delivered in the final response,
avoiding self-referential commit metadata. No force-push, automatic merge or
upstream PR. Task 019 stays closed; Task 022 is not started.