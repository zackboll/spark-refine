# Task 008 — Fresh GNATprove orchestration: `spark-refine prove`

**Status:** executed.

**Base:** `origin/main` = `7111d5dd2bff54674fdeaa756ba49c6abc2c8294`,
the PR #7 merge. The ancestor check against the reviewed Task 007 head
`77bdc1f0394f9772354476b687c021e33b43cfdd` succeeded.

**Branch:** `feature/008-proof-run-orchestration`.

## Question

Task 006 made analysis easy to invoke, but it did not make analysis fresh
by construction: `gnatprove` followed by `spark-refine explain` analyzes
whatever is on disk. Can spark-refine safely combine "run GNATprove" and
"explain the result" without becoming a proof authority, and without
guessing which output belongs to the run?

**Answer: yes.** `spark-refine prove` is orchestration only. It runs
GNATprove as an argv list, never through a shell, and shows the command
first. It analyzes only the one result set that this invocation created
or changed. GNATprove's exit status is preserved.

## Command

```text
spark-refine prove -P PROJECT [--gnatprove PATH] [--results PATH]
                   [--dry-run] [--name N] [--client-unit U ...]
                   [--format text|json] [--fail-on CODE ...]
                   [-- GNATPROVE_ARGS...]
```

* The argv is exactly `[GNATPROVE, "-P", PROJECT, *GNATPROVE_ARGS]`.
  `GNATPROVE` defaults to `gnatprove`, looked up on `PATH`. Everything
  after the **first** `--` is passed on verbatim, including any later
  `--`. This split happens before argparse runs, so argparse's
  version-specific `--` handling cannot change it.
* The process is started with `subprocess.Popen(argv, shell=False,
  stdin=DEVNULL)`. The package contains no `shell=True`, and a test
  checks this.
* Before execution, `GNATprove command:` followed by
  `shlex.join(argv)` is written to **stderr**.
* GNATprove's stdout and stderr are merged and relayed line by line to
  spark-refine's **stderr**. stdout carries only the spark-refine report,
  so the JSON cannot be corrupted.
* GNATprove runs in the current directory, and discovery searches that
  same directory. GPR files are not parsed. If output lands elsewhere,
  use `--results`.
* For Alire, run the whole CLI in the crate environment:
  `alr exec -- spark-refine prove -P project.gpr`. There is no
  Alire-specific layer.

### `--dry-run` (option A: plan JSON)

`--dry-run` builds and displays the command, then exits 0. It does not
execute anything and does not inspect any result set, stale or not. With
`--format json` it prints a small deterministic plan:

```json
{"format_version": 1, "tool": "spark_refine_diagnostics",
 "orchestration": {"command": ["gnatprove", "-P", "p.gpr", "--level=2"],
                   "dry_run": true, "result_selection": "fresh_discovery",
                   "result_path": null}}
```

## Freshness

### Observation on the pinned toolchain (§11, done before the design)

The unchanged ring-buffer baseline was proved three times in a row into
an isolated object directory
(`alr -n exec -- gnatprove -P ring_buffer.gpr -j0
-XRING_BUFFER_VARIANT=freshness_probe`, FSF GNATprove 16.1.0):

| | run 1 (clean) | run 2 | run 3 |
|---|---|---|---|
| wall time | 2.4 s | 0.5 s (incremental) | 0.5 s |
| exit | 0 | 0 | 0 |
| `gnatprove.sarif` mtime / ctime | T1 | **later** | **later** |
| `gnatprove.sarif` inode, size | i, 78407 | same | same |
| `gnatprove.sarif` sha256 | `18269ec1…` | `42860d85…` | `42860d85…` (same as run 2) |
| `*.spark` (mtime, ctime, content) | written | **unchanged** | **unchanged** |
| `gnatprove.out` | written | rewritten, same content | rewritten, same content |

A structural diff of the run-1 and run-2 SARIF showed exactly one
difference, `runs[0].invocations[0].endTimeUtc`, which has one-second
resolution. Runs 2 and 3 fell within the same second and are
byte-identical.

Conclusions:

1. GNATprove 16.1.0 **rewrites `gnatprove.sarif` on every run**, including
   an incremental re-run of an unchanged project. It rewrites the file in
   place (same inode) with a new mtime/ctime.
2. The `.spark` files are **not** rewritten on an incremental run, so
   they cannot serve as the freshness signal.
3. A content digest **alone is insufficient**: two runs within one second
   produce identical bytes. Metadata alone suffices on the pinned
   toolchain, with nanosecond timestamps on the tested ext4 filesystem.

The chosen mechanism therefore distinguishes the second run from stale
output. There was no need to stop or weaken the rule.

Further observations:

* A GNATprove run of **another variant** of the same project
  (`-XRING_BUFFER_VARIANT=probe_neg`) left
  `obj/baseline/gnatprove/gnatprove.sarif` byte- and metadata-identical,
  so stale result sets of other variants are correctly ignored.
* One misconfigured probe made GNATprove touch two result sets. Its
  `RING_BUFFER_SRC` pointed to a head-tail-count fault while the default
  first-length representation was selected. `prove` correctly refused it
  as ambiguous and exited with GNATprove's code, 1, without a report.
  This is exactly the case where guessing would have been wrong.

### Snapshot design

`orchestration.SarifStamp` = `(st_dev, st_ino, st_size, st_mtime_ns,
st_ctime_ns, sha256(content))` of a result set's `gnatprove.sarif`. Two
stamps that differ in any field mean a change. This is conservative
change detection, not security. The only possible miss is a rewrite that
has identical bytes, identical size, the same inode, and falls within one
filesystem timestamp tick of the previous write. That miss fails
**safe**: a missed change is reported as no fresh result, and `prove`
refuses. It never leads to analysis of stale output.

* **Pre-run snapshot** (automatic mode): the stamp of every directory
  under the current directory that directly holds `gnatprove.sarif`,
  whether or not it is a valid result set yet. This uses the same walk as
  Task 006 discovery: sorted, no symlinks, hidden directories and
  `alire/` skipped. Because of this, an old SARIF whose directory
  becomes valid when a `.spark` appears is not treated as new.
* **Post-run:** result sets (Task 006 definition: `gnatprove.sarif` plus
  at least one `*.spark`), each stamped again.
* **Fresh** means the result set is new, or its stamp differs from the
  pre-run stamp. The tool never uses newest, first or largest.

### Selection

| Mode | Outcome |
|---|---|
| explicit `--results PATH` (a result-set directory or its `gnatprove.sarif`; stamped before the run) | after the run it must be a valid result set **and** its stamp must differ. Then it is analyzed (`result_selection: explicit`). Otherwise the error is "GNATprove did not produce fresh results at the requested location." (or "...a valid result set..."). There is **no** fallback to discovery |
| automatic, exactly 1 fresh | analyzed (`result_selection: fresh_discovery`). Unchanged candidates are listed in `stale_result_sets_ignored` |
| automatic, 0 fresh | refused; the stale candidates are listed; no report |
| automatic, more than 1 fresh | refused; the fresh candidates are listed in sorted order; no report |

`explain` discovery (Task 006) is unchanged and separate. It selects
exactly one **existing** result set, and the caller is responsible for
freshness. `prove` selects exactly one result set **freshly changed by
this invocation**.

## Analysis

With one fresh result set selected, `prove` calls the existing
`analyze_path_report` directly, not a second process, and renders with
the existing renderers. It adds `analysis.orchestration` and nothing
else. When GNATprove exits 0 while the result contains unproved checks,
which a project configuration may permit, a note says so. spark-refine
does **not** override GNATprove's exit status. To make CI fail on
unproved checks, configure GNATprove (e.g. `--checks-as-errors=on` in the
project's `Proof_Switches`).

A unit test (`DiagnosticsUnchanged`) checks that the `prove` JSON on a
fresh result set equals the `explain` JSON on the same path, apart from
`analysis.orchestration` and that note. The runs, notes, rules,
analysis, summary and diagnostics are all identical.

## Exit status

| Situation | Exit |
|---|---|
| GNATprove launched and returned nonzero N, fresh result analyzed | **N** (the report is still emitted) |
| GNATprove returned nonzero N, no usable fresh result | **N**, no report. stderr says GNATprove failed before usable fresh result output was found; its console output is shown above on stderr |
| GNATprove 0, `--fail-on CODE` matched | 1 |
| GNATprove 0, analysis succeeded | 0 |
| launch failure, or GNATprove 0 but no unique fresh result, or malformed result | 2 |
| GNATprove killed by signal S (raw return code -S) | 128 + S; the raw code is recorded as `gnatprove_raw_returncode` |
| `--dry-run` | 0 |

GNATprove's nonzero exit status takes precedence over `--fail-on`. A
proof failure is therefore never reported as a `--fail-on` exit 1.

## JSON

`format_version` stays **1**. The addition is purely additive:

```json
"analysis": {
  "rules": {"...": "unchanged"},
  "orchestration": {
    "command": ["gnatprove", "-P", "ring_buffer.gpr", "-j0"],
    "gnatprove_exit_code": 0,
    "result_path": "obj/baseline/gnatprove",
    "result_selection": "fresh_discovery",
    "fresh": true,
    "stale_result_sets_ignored": ["obj/ablation_no_is_full_post/gnatprove", "..."]
  }
}
```

There are no timestamps, UUIDs or tool-added absolute paths.
`stale_result_sets_ignored` appears for `fresh_discovery` only.
`gnatprove_raw_returncode` appears only on signal termination. An
absolute `--results` path is preserved as the user supplied it.

Text output starts with:

```text
proof command: gnatprove -P ring_buffer.gpr -j0
GNATprove exit: 0
fresh results: obj/baseline/gnatprove
selection: fresh_discovery
run obj/baseline/gnatprove: GNATprove FSF 16.1.0; 116 checks: ...
```

## Evidence and metrics

| Item | Result |
|---|---|
| New orchestration unit tests (`tests/test_prove.py`) | **45**, passing. Command construction 8, pass-through 3, dry-run 3, freshness 15 (cases A–H plus variants), exit semantics 12, JSON cleanliness 2, stale safety 1, diagnostics-unchanged 1 |
| New E2E-checker unit tests (`test_e2e_checks.py::E2EProveCheckers`) | **6**, passing. They accept known-good reports and reject a wrong path, selection method, freshness flag, exit code or command, a missing stale list, and an unproved run |
| Whole diagnostics suite | **188** tests (137 pre-existing + 51 new), passing. The 137 pre-existing tests are unchanged |
| Existing fixture compatibility | `explain --format text` and `--format json` on all **49** fixtures, `compare-provers` text/json and `rules --format json` are **byte-identical** to `origin/main` (101 outputs, sha256-compared) |
| Repeated real GNATprove freshness | the SARIF is rewritten on every run (new mtime/ctime; content differs only in `endTimeUtc`, which has 1 s resolution); `.spark` files are untouched on incremental runs (table above) |
| Result-selection cases | explicit: fresh, unchanged, absent-then-created, never written, SARIF-file form, absolute path. Automatic: 1 new, 1 rewritten, 1 of 3 rewritten, same bytes with new metadata, 0 fresh, 2 rewritten, new + rewritten, became valid but old, hidden and `alire/` ignored |
| CLI exit-policy cases | 0 + fresh → 0; 1 + fresh → 1 with report; 7 + fresh → 7; 4 + none → 4 without report; SIGTERM → 143 (raw -15); launch failure → 2; `--fail-on` with GNATprove 0 → 1; `--fail-on` with GNATprove 3 → 3; stale only → 2; ambiguous → 2; explicit unchanged → 2; dry run → 0 |
| JSON cleanliness | a fake GNATprove writes non-JSON text to both streams, tested in-process and in a real child process with real file descriptors. stdout parses as JSON; the noise appears only on stderr |
| Stale safety | for a valid old result, `explain` analyzes it (SRD001). `prove` after a no-op GNATprove (exit 0) refuses it with exit 2 and empty stdout, in both text and JSON |
| E2E-D (real GNATprove 16.1.0, local) | **PASS**. Run after E2E-A/B with a stale decoy placed; 29 stale result sets ignored; `obj/baseline/gnatprove` selected; exit 0; 116/116 proved, 0 justified, 0 pragma Assume; 0 diagnostics |
| E2E-E (real, optional negative) | **PASS**. B3 materialized with the benchmark's own `apply_fault`; GNATprove exit 1; `prove` exit 1; fresh `obj/e2e_prove_b3/gnatprove` selected among 30 stale result sets; SRD001 on `Ring_Buffer.Pop` (checked by the E2E-A checker) |
| Packaging | wheel and editable installs. `orchestration.py` is in the wheel. `prove -P fake.gpr --dry-run` and `python -m ... prove --dry-run --format json` work outside the repository. With a fake GNATprove, a stale result set is refused, and a fresh one is diagnosed with the exit code preserved and JSON-only stdout |
| Runtime dependencies | **0** (standard library only; checked by `test_runtime_imports_are_stdlib_only` and the wheel metadata) |

No accuracy score is claimed. Orchestration adds provenance, not
diagnostic reasoning.

The optional real negative case (§30) turned out to be practical. It
reuses the benchmark gate's own `apply_fault` through `importlib`, with
no duplicated patch machinery, and adds about 3 s of GNATprove.

## Changed files

| File | Change |
|---|---|
| `diagnostics/spark_refine_diagnostics/orchestration.py` | **new**: command construction, `SarifStamp` snapshots, `Freshness` selection, subprocess relay, exit normalization, metadata, dry-run plan |
| `diagnostics/spark_refine_diagnostics/discovery.py` | adds `find_sarif_dirs` (same walk, factored out); `find_result_sets` behavior unchanged |
| `diagnostics/spark_refine_diagnostics/cli.py` | `prove` sub-command and pass-through split. The `explain`/`analyze`/`compare-provers`/`rules` code paths are unchanged |
| `diagnostics/spark_refine_diagnostics/render.py` | provenance lines in text output (only when `analysis.orchestration` exists); dry-run text |
| `diagnostics/tests/test_prove.py` | **new**, 45 tests |
| `diagnostics/tests/test_e2e_checks.py` | E2E-D/E checker tests |
| `diagnostics/scripts/e2e_fresh.py` | E2E-D (`prove`) and E2E-E (`prove_negative`) |
| `diagnostics/scripts/packaging_smoke.py` | wheel module check; installed `prove` checks with a fake GNATprove |
| `.github/workflows/ci.yml` | two steps in `diagnostics-e2e`, artifact paths, comments. No new job |
| `src/spark_refine.adb` | the legacy Ada bootstrap redirects `prove` to the Python CLI and lists it in `--help`. It does not invoke Python |
| `scripts/check_repo.py` | two `REQUIRED` entries |
| current docs | README, diagnostics/README, DIAGNOSTICS_METRICS, AGENT_INTEGRATION, VISION, ARCHITECTURE, ROADMAP, INTEGRATION, FAQ, TRUST_MODEL, MVP, CHANGELOG |

Historical task records (001–007) were not modified.

## Trust boundary

`prove` does not prove anything itself. In authority it is equivalent to
running GNATprove and then running `explain` on the result. Its only
extra property is fresh-result provenance.

```text
GNATprove       proof authority
spark-refine    orchestration + interpretation
human / agent   decides changes
```

`prove` produces SRD001/SRD002 for **one** proof run. SRD003 still
requires `compare-provers` over separate single-prover runs, and `prove`
does not run a prover matrix. `prove` also does not remove every
build/source synchronization risk. Two examples remain the user's
responsibility: sources edited *while* GNATprove runs, and a GNATprove
configuration that writes outside the current directory when
`--results` is not given.

## Scope confirmations

This task adds no Libadalang and no new diagnostic rule. Stale results,
proof-run failure and orchestration failure are orchestration states,
not SRD codes. There is no source rewriting, source generation,
automatic proof repair, contract change or prover-matrix generation.
SRD001–SRD003 semantics and the fixture expectations are unchanged.

## Technical debt (not addressed here)

* `scripts/check_repo.py` still requires and validates the historical
  `examples/ring_buffer/spark-refine.toml` generator manifest. Clean it
  up in a separate change.
* Freshness has been observed only on FSF GNATprove 16.1.0 on
  Linux/ext4. Filesystems with coarse timestamps remain safe by
  construction, because the digest and the fail-safe refusal still
  apply. They may, however, refuse a genuine re-run with identical bytes
  inside the same timestamp tick.

## Recommendation for Task 009

**Libadalang semantic enrichment of SRD002.** Identify the call site,
the callee, and the specific `Pre` conjunct behind a client-only
precondition failure. This remains the main known limitation of the
diagnostics (`diagnostics/README.md`, *Limitations*). `prove` now gives
agents a fresh, provenance-carrying result to attach that information
to. The enrichment should stay additive to `format_version` 1, and it
should degrade to today's SRD002 when Libadalang is unavailable.

