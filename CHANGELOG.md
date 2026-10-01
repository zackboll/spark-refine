# Changelog

## Unreleased

### Research

- Task 016: structural investigation of the unchanged Task 015 artifacts confirms
  that a disputed entity-fallback `sml` unit caused an unnecessary ALI request.
  Dependency completeness now uses analysed `.spark` units when present;
  SARIF attribution and all 19 unexplained consistency disputes remain intact.
  SRD002 can evaluate on the fully proved external run (zero diagnostics),
  not an external positive-case validation. No proof rerun or new rule.

- Task 015: preregistered external SPARK validation on pinned sml-ada
  (fallback after Muen build-context feasibility blocker). Fresh GNATprove
  16.1.0 proved 356/356; unchanged spark-refine core ingested the result.
  SRD001 evaluated with no diagnostics; SRD002 could not evaluate because
  `sml.ali` was absent, and 19 SARIF/.spark results did not pair. No source
  patches, conjunct probes, parser changes, or new CI job. See
  `docs/tasks/015-external-validation-pilot.md` and
  `docs/evidence/task015-external-validation.json`.

- Task 014 (experiment only, no product change): cumulative callee-contract
  prefix re-proofs on a controlled Ada call-binding corpus produced
  `CALL_BINDING_METHOD_VALIDATED_ON_PREREGISTERED_SUPPORTED_CASES`: 26
  resolved calls, 7 contracts, one baseline + 15 prefix programs and 60
  per-occurrence observations. A8's unproved conversion VC was kept
  auxiliary, not clean conjunct evidence. This is scratch evidence, not
  proof of the original program; normal output and CLI are unchanged.
  See `docs/tasks/014-ada-call-binding-reproof.md`.
- Task 013 (experiment only, no product change): a pre-registered
  guard-sensitive conjunct re-proof experiment,
  `diagnostics/scripts/guarded_reproof_experiment.py`. It is outside the
  installed package and adds no CLI command or flag.
  - Corpus: new experimental input
    `diagnostics/tests/experiments/task013_guarded/` with
    `P /= null and then P.all > 0`, `I in A'Range and then A (I) > 0` and
    `X in 12 .. 999 and then F (F (X)) > 20`, plus nine caller states.
  - Method: cumulative source-prefix re-proof. Libadalang gives the
    conjuncts, their source ranges and the original operators. The
    scratch `Pre` is the exact original source slice `C0 .. Ci`, with the
    remainder blanked and newlines preserved. A guarded later conjunct is
    never probed in isolation: the planner refuses Task 012's
    selected-only request. That is 1 control plus 6 prefix runs.
  - Verdict: `PREFIX_METHOD_VALIDATED_ON_GUARDED_CORPUS`. The baseline
    matched 9/9. All 18 prefix statuses and classifications matched:
    `prefix_proved` 9, `newly_unproved` 6, `blocked_by_earlier_prefix` 3.
    There were 0 justified, 0 disputed and 0 nested-unproved results.
    Nested `F` precondition checks were recorded separately and were
    never folded into the target VC.
  - Unchanged: normal command output (byte-identical to Task 012 main),
    `failed_conjunct: null`, `attribution: not_provided_by_gnatprove`,
    and the Task 012 experiment and its corpus.
  - CI: a new step in `diagnostics-semantic`, with `evidence.json` and
    `timing.json` uploaded. There is no new job.
  - See `docs/tasks/013-guard-sensitive-conjunct-reproof.md`.
- Task 012 (experiment only, no product change): a pre-registered
  per-conjunct GNATprove re-proof experiment,
  `diagnostics/scripts/conjunct_reproof_experiment.py`. It is outside the
  installed package and adds no CLI command or flag.
  - Method: the unchanged Task 009 corpus is copied into the gitignored
    `diagnostics/obj/task012-conjunct-reproof/`. In each copy, the
    callee's `Pre` expression range (located with Libadalang) is replaced
    by one top-level conjunct, and GNATprove is re-run: 1 unmodified
    control plus 5 probes. The call `VC_PRECONDITION` is then read
    structurally.
  - Verdict: `VALIDATED_ON_CONTROLLED_CORPUS`. The baseline had 4/4
    unproved. All 9 pre-registered observations matched (4 proved,
    5 unproved, 0 justified). `First_Fails` [U, P] and `Both_Fail`
    [U, U] are distinguished; they are identical in the original result.
  - Gates: source isolation (only `ops.ads`, only the `Pre` range), a
    Libadalang forbidden-trust scan, and exactly-one-match structural
    reading.
  - Scope: independent total conjuncts only. This is scratch proof
    evidence, not a proof of the original program.
  - Unchanged: normal command output (byte-identical to Task 011),
    `failed_conjunct: null`, `attribution: not_provided_by_gnatprove`,
    SRD001–SRD003 and JSON.
  - CI: a new step in `diagnostics-semantic`, with `evidence.json`
    uploaded as an artifact. There is no new job.
  - See `docs/tasks/012-per-conjunct-reproof-experiment.md`.

### Fixed

- Task 011: semantic text rendering is fail-safe. A malformed or
  incomplete internal Task 009 semantic entry (for example `resolution:
  "exact"` with `call: {}`) no longer raises `KeyError`/`TypeError`/
  `AttributeError` from `to_text`/`diagnostic_to_text`/`semantic_text`. It
  renders as `semantic entry: incomplete` with a reason and claims no
  call, callee, Pre, conjunct or assertion fact. Completeness is one shared
  structural contract, used by Task 010 grouping and by the renderer: the
  new backend-neutral module `semantic_shape.py`, into which Task 010's
  check moved unchanged. The renderer now dispatches exact entries by
  rule, not by key presence. JSON still serialises the raw semantic object.
  Valid text output is byte-identical to Task 010. SRD001–SRD003, semantic
  resolution, provenance, grouping and the failed-conjunct policy are
  unchanged. There is no new CI job or E2E case. See
  `docs/tasks/011-defensive-semantic-rendering.md`.

### Added

- Task 010: SRD002 semantic triage groups. When `--semantic` enrichment is
  evaluated, the report gains `analysis.semantic.srd002_groups` and an
  `SRD002 semantic triage` text section before the individual
  diagnostics. Exact `VC_PRECONDITION` client failures are grouped by
  identical callee (qualified name, kind, declaration span) and identical
  extracted `Pre` (verbatim text, span, conjuncts). Overloads and textually
  different `Pre`s never merge. Every other failure is `ungrouped` with a
  stable reason (`assertion_has_no_callee`, `semantic_ambiguous`,
  `semantic_unresolved`, `semantic_unavailable`, `semantic_incomplete`,
  `rule_not_groupable`). Every client failure appears exactly once
  (`coverage_problems`). Groups carry no confidence (occurrences keep
  `diagnostic_confidence`) and make no causal or conjunct claim. New
  backend-neutral module `semantic_groups.py` (no Libadalang import).
  Diagnostics, the SRD002 count, Task 009 per-check semantic blocks and
  `format_version` 1 are unchanged. Without `--semantic`, output is
  byte-identical to Task 009. E2E-F and E2E-G are extended; there is no new
  proof run, no new CI job and no new rule. Semantic enrichment stays
  opt-in (`docs/ROADMAP.md`).

- Task 009 (experimental, opt-in): Libadalang semantic enrichment of
  SRD002. `--semantic` for `explain`/`analyze`/`prove`, with `-P/--project`
  for `explain`/`analyze` and `-X NAME=VALUE` scenario values for the
  Libadalang project loader. Each SRD002 client failure gets a
  `resolution` (`exact`/`ambiguous`/`unresolved`/`unavailable`). An exact
  `VC_PRECONDITION` adds the call, the callee (qualified name,
  declaration), and the explicit `Pre` with top-level `and`/`and then`
  conjuncts. A `VC_ASSERT` adds the asserted expression only. The
  pre-registered experiment shows GNATprove 16.1.0 output is NOT
  ATTRIBUTABLE to a Pre conjunct, so `failed_conjunct` is always `null`.
  Source/result provenance gate: sources must match the result set's
  `.ali` `D` records (GNAT checksum, `gnat_checksum.py`, + second-resolution
  mtime). This is GNAT's source identity metadata, not byte identity:
  same-second layout/comment edits are undetectable. Reported as
  `analysis.semantic.provenance` (`layout_exact: false`, `byte_exact:
  false`). New modules
  `semantic.py` and `semantic_lal.py` (the only Libadalang import, lazy).
  `analysis.semantic` and `diagnostics[].semantic` are added only with
  `--semantic`, and `format_version` stays 1. Without the flag, output is
  byte-identical to Task 008. The core package still has no runtime
  dependencies. Libadalang is not on PyPI:
  `diagnostics/scripts/setup_libadalang.sh` builds a pinned, relocatable
  bundle (libadalang 26.0.0, 166 MB). Adds the new CI job
  `diagnostics-semantic` with E2E-F (project-local callees) and E2E-G
  (SPARKlib callees, fresh, same dependency checkout as the proof), 6
  semantic snapshot cases (432 KB), and 56 tests. The snapshots hold
  project-local source only. On an archived fixture, SPARKlib callee
  declarations may degrade to `unavailable` when the active checkout's
  mtime differs from the captured `D` record; the provenance gate is
  unchanged. SRD001–SRD003 are unchanged. There is no new rule.

- Task 008: `spark-refine prove -P PROJECT [-- GNATPROVE_ARGS...]`, fresh
  GNATprove orchestration (`diagnostics/spark_refine_diagnostics/orchestration.py`).
  It runs GNATprove as an argv (`shell=False`) after printing the exact
  command to stderr, and relays GNATprove's output to stderr so stdout
  carries only the report. It analyzes only the one result set whose
  `gnatprove.sarif` this run created or changed (stamp: dev, inode,
  size, mtime_ns, ctime_ns, sha256). Stale result sets are ignored;
  zero or several fresh result sets are refused. `--results PATH` must
  be freshly written, with no fallback. GNATprove's nonzero exit code is
  preserved even when diagnostics are produced; `--fail-on` applies only
  when GNATprove exited 0. Also adds `--gnatprove PATH` and `--dry-run`
  (with an optional JSON plan). `analysis.orchestration` is added to the
  JSON, and `format_version` stays 1. The real GNATprove 16.1.0
  repeated-run freshness behavior is recorded in
  `docs/tasks/008-proof-run-orchestration.md`. Adds 51 tests (fake
  GNATprove, no toolchain), fresh E2E-D/E-E in `diagnostics-e2e`, and
  installed-package `prove` checks. `explain`/`analyze`/`compare-provers`
  output on all 49 fixtures is byte-identical. SRD001–SRD003 are
  unchanged. There are no new rules and no runtime dependencies. The
  legacy Ada `spark_refine` now also redirects `prove`.

- Initial project motivation and ecosystem gap analysis.
- Architecture, trust model, MVP, benchmark, and roadmap documentation.
- Proposed manifest and circular-sequence proof pattern.
- Minimal Ada CLI bootstrap.
- Repository structural checks.
- Task 001: fully proved manual ring-buffer baseline (`examples/ring_buffer`)
  with a SPARKlib functional-sequence model, a representation-independent
  client proof, runtime tests, five machine-checked negative proof fixtures,
  a proof-support inventory (`BASELINE_METRICS.md`), and a pinned
  GNAT/GNATprove/SPARKlib 16.1.0 CI proof job.
- Task 004: reusable SPARK proof-pattern library `proof_patterns/`
  (`SPARK_Refine_Prefix_Sets`) with three independent proof-only validation
  instances; a library-backed fixed-pool variant
  (`examples/fixed_pool/variants/library_backed`) with an unchanged public
  API, client proof and runtime tests; public-API equivalence, inventory
  (`R`, `L`, `A`), negative (L1-L6) and library-validation gates; a new CI
  job; `LIBRARY_METRICS.md`. Pre-registered decision: PIVOT (R = 10).
- Task 005: deterministic GNATprove diagnostics MVP (`diagnostics/`,
  `python3 -m spark_refine_diagnostics`). It reads SARIF and `.spark`
  with the benchmark gates' classification (parity-tested), plus `.ali`
  through a narrow, non-raising GNAT 16.1.0 adapter. It has three stable
  rules:
  - SRD001: invariant masking risk;
  - SRD002: client-only proof gap; the public abstraction may be
    insufficient (medium confidence for preconditions, low for
    assertions; skipped when dependency information is unavailable);
  - SRD003: prover-portfolio dependency, only for checks matched
    `exact` or `unique_entity`, never by source order; ambiguous
    identities are reported as metadata.

  It ships 49 sanitized real GNATprove 16.1.0 fixtures, including a
  false-client-assertion control, with provenance and ablation-based
  ground truth. It also adds 110 fixture-based unit tests run in CI,
  a small fresh end-to-end GNATprove gate (one case per rule, CI job
  `diagnostics-e2e`), `diagnostics/DIAGNOSTICS_METRICS.md` and
  `docs/tasks/005-proof-diagnostics-mvp.md`. `.ali` files with a version
  header other than `GNAT Lib v16` are rejected (`unsupported_version`;
  SRD002 skipped).
- Task 006: the diagnostics are installable as the `spark-refine` console
  command (`python3 -m pip install ./diagnostics`; `pyproject.toml`,
  setuptools build-time only, no runtime dependencies; fixtures, tests
  and scripts are excluded from the wheel). It adds:
  - `spark-refine explain [PATH]`, the preferred name for single-run
    analysis. Without `PATH` it discovers exactly one GNATprove result
    set (`gnatprove.sarif` + `*.spark`) under the current directory.
    Zero or several candidates give exit 2, and several are listed in
    sorted order; the tool never guesses. `analyze` stays as a
    compatibility alias, and `python3 -m spark_refine_diagnostics` still
    works;
  - additive JSON fields (`format_version` stays 1): per-diagnostic and
    per-rule `category` / `action`, a derived top-level `summary`, and
    `analysis.input` for discovered result sets. `rules --format json`
    and `--version` are also new;
  - `docs/AGENT_INTEGRATION.md`, which documents the agent loop and the
    trust boundary;
  - `scripts/packaging_smoke.py` and CI job `diagnostics-packaging`,
    which build, inspect and install the wheel and run the installed
    CLI outside the repository.

  No new rule. SRD001–SRD003 behaviour is unchanged.

### Changed

- Task 006: the root README was rewritten around the evidence-backed
  project: reusable proof patterns plus proof-aware diagnostics. The
  original generator-centred README is preserved as
  `docs/history/ORIGINAL_README.md`. The root `alire.toml` description
  now reads "Reusable proof patterns and proof-aware diagnostics for
  SPARK". The Ada bootstrap `spark_refine` help now calls it legacy,
  points to the Python `spark-refine explain`, and marks
  `validate`/`generate`/`check` as historical, deprioritized research.

- Task 007: documentation realigned with the evidence-backed direction:
  reusable GNATprove-verified proof patterns plus proof-aware
  diagnostics, with GNATprove as the proof authority.
  - New [ADR 0005](docs/adr/0005-library-and-diagnostics-first.md),
    accepted. It prefers libraries and diagnostics over a
    generator-first architecture. ADRs 0003 and 0004 are marked
    superseded/deferred, and 0001 and 0002 are confirmed current.
  - `docs/VISION.md`, `ARCHITECTURE.md`, `MVP.md` and `ROADMAP.md` were
    rewritten around the current product. Each keeps its generator-era
    content in a labelled historical section.
  - `docs/SPEC.md` and `MANIFEST.md` got historical/deferred banners.
  - `LANDSCAPE.md`, `INTEGRATION.md`, `MOTIVATION.md`, `FAQ.md`,
    `METRICS.md`, `TRUST_MODEL.md`, `CONTRIBUTING.md` and `SECURITY.md`
    were updated.
  - Status notes were added to the remaining design documents.
  - The three kinds of source (implementation, authoritative
    specification, mechanical proof support) are documented as policy.
  - The human workflow is stated consistently:
    `gnatprove` → `spark-refine explain` (SRD001/SRD002; does not run
    GNATprove); SRD003 comes only from `compare-provers`.
  - README gains a "Where to start" documentation hierarchy.
  - `scripts/check_repo.py` now requires ADR 0005 and the Task 007
    record.

  Documentation-focused; no behavior change. See
  `docs/tasks/007-documentation-realignment.md`.

- Root `alire.toml`: dropped the placeholder `maintainers` entry and the
  over-long `formal-verification` tag, which Alire 2.1.1 rejects. Without
  this change `alr build` fails at the repository root.
