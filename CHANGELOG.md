# Changelog

## Unreleased

### Added

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
