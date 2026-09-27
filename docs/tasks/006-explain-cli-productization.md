# Task 006 — Productize `spark-refine explain`

**Status:** executed.

**Base:** `origin/main` = `2fb4692d0fe630c823eeb8bf7027d14acba5a942`,
the PR #5 merge. The ancestor check against the reviewed PR #5 head
`49aee1df2d2d8947d81708cbd8b594096e2b1a06` succeeded.

**Branch:** `feature/006-explain-cli-productization`.

## Question

Task 005 showed that deterministic diagnostics work on real GNATprove
output. Can a developer or an agent now install the engine and invoke it
conveniently on a SPARK project?

```text
gnatprove -P my_project.gpr
spark-refine explain
```

The goal is human-readable text for developers and stable JSON for
agents, CI and editors. The task adds no new rule, no Libadalang, no
source modification, no proof repair, and no GNATprove execution.

## What was built

* **Packaging** (`diagnostics/pyproject.toml`, `MANIFEST.in`, `LICENSE`):
  * setuptools, used at build time only; there are no runtime
    dependencies;
  * console script `spark-refine = spark_refine_diagnostics.cli:main`;
  * an explicit package list, so only `spark_refine_diagnostics` is
    packaged;
  * the version is single-sourced from
    `spark_refine_diagnostics.__version__` (`0.0.0.dev0`).
* **`explain`**, the preferred single-run command:
  * `analyze` is kept as an alias, with byte-identical output for an
    explicit path on all 49 fixtures;
  * `python3 -m spark_refine_diagnostics` is unchanged.
* **Discovery** (`discovery.py`), used when `explain` gets no `PATH`. A
  result set is a directory that directly holds `gnatprove.sarif` and at
  least one `*.spark` file. The search:
  * walks the tree in sorted order and does not follow symbolic links;
  * skips hidden directories and `alire/`;
  * uses exactly one result set if it finds one;
  * exits 2 if it finds zero or several. Several candidates are listed in
    sorted order, and the tool never picks the newest, largest or
    first-found one.

  An explicit path is authoritative and is never combined with
  discovery. `.ali` handling is untouched: only the `.ali` files next to
  the chosen SARIF are read, and SRD002 is skipped otherwise.
* **Agent-facing JSON.** All additions are additive, so `format_version`
  stays 1:
  * `category` and `action` on each diagnostic and in the `rules`
    catalogue, plus `action_description` in the catalogue;
  * a top-level `summary` (`diagnostic_count`, `by_code`,
    `by_confidence`, `by_category`, `by_action`), computed from the
    diagnostics, with every key present and no timestamps;
  * `analysis.input` for discovered result sets.
* **Docs:**
  * `docs/AGENT_INTEGRATION.md`: the agent loop, per-rule guidance and
    the trust boundary;
  * the root README, rewritten; the old one is preserved as
    `docs/history/ORIGINAL_README.md`;
  * `diagnostics/README.md`, `ROADMAP.md` and `CHANGELOG.md`.
* **Ada bootstrap `spark_refine`:** the help text now says it is legacy
  and points to the Python `spark-refine`. It marks
  `validate`/`generate`/`check` as historical research and redirects
  `explain`/`analyze`/`compare-provers`/`rules` to the Python CLI (exit
  1). It does not shell out to Python.
* **Root `alire.toml` description:** "Reusable proof patterns and
  proof-aware diagnostics for SPARK".

| Code | category | action |
|---|---|---|
| SRD001 | `proof_context` | `fix_invariant_then_reprove` |
| SRD002 | `abstraction_boundary` | `validate_client_goal_then_review_public_contracts` |
| SRD003 | `prover_portfolio` | `preserve_portfolio_or_strengthen_proof` |

## Validation

* **Fixture suite:** 137 tests, up from 110. The 110 Task 005 tests and
  every expected diagnostic in `expectations.toml` are unchanged.
* **`scripts/packaging_smoke.py`**, run for a wheel install and for an
  editable install (CI job `diagnostics-packaging`, no Ada toolchain):
  1. build the wheel;
  2. check that it holds only `spark_refine_diagnostics/*.py` plus
     metadata (about 46 KB wheel, about 116 KB unpacked, 84 KB of Python
     source installed);
  3. install it into an isolated venv;
  4. from a temporary directory outside the repository, run `rules`,
     `explain` and `analyze` on absolute fixture paths, run
     `compare-provers`, run discovery with one, zero and two result sets,
     and run `python -m spark_refine_diagnostics`.
* The same job runs the fixture suite on Python 3.11, the minimum
  version.
* `diagnostics-e2e` (fresh GNATprove) and the proof jobs are unchanged.

## Opportunities noted, not implemented

* Proof-run orchestration (`spark-refine prove`, which would run
  GNATprove and then explain). It would also solve freshness.
* Libadalang enrichment for SRD002: naming the callee and `Pre`.
