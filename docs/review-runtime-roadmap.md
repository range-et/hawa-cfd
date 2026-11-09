# Runtime roadmap documentation review

- Change: add the runtime foundation and installation decision to `roadmap.md`.
  No code, dependency pins, nodes, examples or packaged binaries changed by this edit.
- Date and reviewer: November 9, 2026; Codex primary agent, self-review only.
- User request: retain Python/PyTorch, prioritize seamless Mac/Windows setup, and
  consider Rust only after finding an actual bottleneck.
- Claim: a product direction, not implementation verification, physical
  validation or a claim of successful installation on every platform.
- References inspected: `quality-gates.md`, `review-record-template.md`,
  `examples/grasshopper/VERIFICATION.md`, `native-v0.5.md`, `pyproject.toml` and
  `src/hawa/backends.py`, as present in the checkout on this date.
- Acceptance criteria: preserve the existing roadmap; explicitly record the
  language decision, platform/setup goals and profiling gate; distinguish future
  acceptance requirements from current verified support. Add no dependency.
- Environment/device/grid/time: documentation-only; no solver device selected,
  no simulation steps, no Rhino session or performance measurement.

| Gate | Reviewer | Decision | Evidence and reason |
| --- | --- | --- | --- |
| G0 research | Codex, self-review | PASS | The section records the user's decision and matches the inspected Python pins, embedded-runtime guide and backend-selection contract; no new performance claim. |
| G1 architecture | Codex, self-review | PASS | Python numerical foundation, C# host and external-engine exceptions remain distinct; native acceleration requires a bounded interface and preserved lifecycle. This is a planning review only. |
| G2 software/reliability | Codex, self-review | NOT APPLICABLE | No executable changes; unit suite and .NET state-contract tests are not required for this prose edit. |
| G3 numerical physics | Codex, self-review | NOT APPLICABLE | No numerical changes or new accuracy claims; future optimizations must retain acceptance criteria. No numerical benchmarks run. |
| G4 UI/UX and examples | Codex, self-review | NOT APPLICABLE | No interface or example changed. Setup UX is a future requirement; no live GH/UI check run. |
| G5 release/integration | Codex, self-review | NOT APPLICABLE | No package or release change. Clean Mac/Windows installation and CUDA checks were not run and receive no pass here. |

## Reproduction and results

Read the new roadmap section against the user request and the references above.
Check whitespace with `git diff --check -- docs/roadmap.md` and resolve relative
Markdown links in both documentation files using the repository Python.

Both documentation checks passed. Numerical, performance, installer, state and
native-host tests were not run for this documentation-only change. No runtime
or release approval is implied; future implementation must meet the roadmap's
platform, performance and numerical gates with fresh evidence.
