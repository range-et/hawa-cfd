# Headless coverage and mutation review

Date: November 9, 2026 (America/Toronto). Refs GitHub [#28](https://github.com/range-et/hawa-cfd/issues/28)
and [#45](https://github.com/range-et/hawa-cfd/issues/45); both remain open for their
remaining scope. Reviewers: Codex integration agent, runtime test agent, tooling
test agent and C# contract agent. These are agent reviews, not human scientific
or Rhino acceptance sign-offs.

## Result and scope

The fresh native integrated gate covers **365/365 first-party Python functions**
and **6,164/6,164 executable Python lines**, with zero missing/excluded lines.
Runtime `src/hawa` contributes 3,356 lines, developer scripts 2,414, tools 372,
and embedded Python bootstrap 22. Python branch arcs are 2,240/2,430; no complete
branch-coverage claim is made.

The 11 linked first-party C# files cover **152/152 executable functions** and
**1,618/1,618 instrumented lines**. The suite passed 67 contracts. Another **590
executable C# functions across 23 host-dependent paths remain unmeasured**;
58 declarations have no explicit executable body. Test-host/double lines are
not counted as product lines. The [committed matrix](function-test-matrix.md)
keeps every host row visible; this is not 100% coverage of the whole repository.

The trusted-base ratchet and strict headless check pass. All 236 newly covered
baseline gaps were promoted only after measured execution. The strict check
uses coverage.py's executable statements: raw traced locations can also include
docstrings and must not inflate line denominators.

## Changes and checks

- Runtime tests exercise numerical invariants, admission/rejection, checkpoint
  integrity, immutable field validation, transfer cleanup, background lifecycle,
  public dispatch and legacy archive reconstruction. Production runtime code
  and physical comparison tolerances are unchanged.
- Tooling tests assert command routing, provenance, saved arrays, failure reports,
  source packaging, HTTP ranges, media hashes/captions/licenses and encoder
  failures. Media fixtures and device/process doubles validate contracts;
  they are not live Rhino renders or hardware/atmospheric qualification.
- Developer media/recording scripts now import without launching their workflow;
  direct execution retains defaults. Four benchmark entrypoints expose `main`
  while preserving the original benchmark settings and assertions.
- A rejected stationarity sample previously bypassed report creation or retained
  an earlier successful report. It now writes a failed report for rejection,
  startup or advancement exceptions, always attempts cleanup for created sessions,
  records cleanup errors separately, and never checkpoints rejected populations.
  Tests cover first-sample/later failures, zero progress and session-creation
  failures; a real unavailable-device startup also invalidated stale success.
  Resumed runs preserve a unique byte-for-byte backup before startup/load and
  retain earlier samples when either fails. Malformed original reports are also
  preserved; repeated attempts never overwrite previous backups. Backup names
  use a short fixed prefix and preserve the original report path in metadata;
  250-byte report filenames are covered by the resume regressions. Failure to
  create the backup aborts before modifying the original report.
  Stationarity/drag/profile limits and `physical_validation=False` remain intact.
- The source bundle now includes the pinned palette and its provenance/license,
  needed by the media tooling and its tests. Real plugin compilation/package
  creation passed; the ZIP contains the assemblies, sources and palette, and
  excludes protected legacy 09. No installed assembly was replaced. The build
  emitted 105 warnings, including platform-specific drawing API warnings.
- Nine production C# files have token-identical formatting changes that separate
  callback/local-function body lines for instrumentation. Agents checked Roslyn
  token identity and parse diagnostics. Contracts cover state ownership, stale
  callbacks, scheduling, display and geometry kernels through explicit doubles.

Native environment: macOS 27.0.1 arm64, Python 3.9.25, PyTorch 2.8.0, NumPy 2.0.2,
.NET 10 contract host. Full run: **1,419 passed, 82 skipped, 213 warnings** in
185.98 seconds. Skips retain unavailable-device/optional qualification scope;
warnings include dependency deprecations and an intentional extreme-input
numerical rejection. Fresh artifacts are under `results/quality-pilot/long-resume-gate`;
the source/test fingerprints and per-function evidence are committed in
`docs/function-tests/matrix.json`.

Before the resume-history follow-up, an independent network-disabled Docker run
on Debian 12 arm64, Python 3.9.25, PyTorch 2.8.0+cpu and .NET SDK 10.0.403 passed
**1,331 tests**, with 162 unavailable-GPU skips, plus **67 C# contracts**. That
revision measured 6,157/6,157 Python lines and its source snapshot matched the
then-current checkout (`78fe0b5`); artifacts remain in
`results/quality-pilot/linux-complete-final`. The developer image includes Git,
.NET and installed editable package metadata. A real unavailable-MPS startup
also replaced seeded stale success with a failed report.

The resume-history follow-up passed **82 focused tests on both macOS and Docker
Linux**, including byte-exact backup preservation, repeated attempts, malformed
reports, and create/load failures. Its complete native gate is the current
measurement above; GitHub runs the full Linux gate on the final PR revision.
Focused Linux evidence is in `results/quality-pilot/long-resume-linux`.

```sh
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/bin/python tools/function_coverage.py run --output results/quality-NEW --base-ref origin/main
.venv/bin/python tools/function_coverage.py check --output results/quality-NEW --strict --coverage-scope headless --base-ref origin/main
.venv/bin/python tools/function_coverage.py check --output docs/function-tests --base-ref origin/main
.venv/bin/python scripts/build_plugin.py --output results/quality-bundle-NEW --archive results/Hawa-quality-NEW.zip
```

## Mutation results and automation

Pinned mutmut 2.4.5 completed **398 mutants: 358 killed and 40 reviewed survivors**,
with no timeout/error/skip outcomes. The CLI control has 16 passing tests and
42 mutants (38 killed, four survivors); runtime admission has 91 controls and
356 mutants (320 killed, 36 survivors). The 40 survivors are individually reviewed
equivalent algebra/probe behavior or diagnostic/JSON formatting changes. They
remain survivors, not kills. Raw mutmut exit 2 is preserved; acceptance requires
exact source/test and survivor-diff hashes plus complete collected controls.
See [CLI evidence](verification-cli-mutation.json), [runtime evidence](review-runtime-quality.md)
and [reproduction/policy](function-testing.md).

This covers four Python modules, not all Python mutation sites and not C# mutation
testing. Unexpected survivors, incomplete runs and stale policies fail CI.
GitHub workflows run the strict headless coverage gate and both mutation studies
on PRs and pushes to `main`. Maintainers control required-check repository rules.

## Separate gates and remaining work

- G0/research and G3/physics: no new numerical method or physical-accuracy claim.
  Existing atmospheric qualification failures remain open; thresholds unchanged.
- G1/architecture: no new public nodes or state ownership contract. C# production
  token streams are unchanged; headless contracts do not establish GH scheduling.
- G2/reliability: the complete native suite, strict coverage, mutation controls,
  hostile evidence checks and real build/package checks pass in the stated scope.
- G4/host acceptance: **not run on this branch**. The PR creator supplies the
  [local all-example numerical/visual review](local-rhino-acceptance.md), with
  explicit failures/omissions; the maintainer owns merge acceptance. There are
  32 supported workflows, excluding protected legacy 09. No self-hosted runner
  is required, and screenshots do not become instrumented C# coverage.
- G5/distribution: a development bundle was built and inspected, not installed,
  released or physically qualified.
- G6/compatibility: the matrix verifier and reporting failure paths are tested;
  no fresh exhaustive compatibility sweep or live node/example run is claimed.

Remaining #28 scope is host-dependent measured coverage and local acceptance;
#45 also includes broader mutation and other verification ideas beyond these
four modules. Neither issue is closed by headless percentages alone.
