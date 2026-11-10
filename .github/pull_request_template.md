## Change

Describe the problem, resulting behavior and linked GitHub issues.

## Automated checks

Record commands/results and link CI. Include function/line coverage and mutation
results for applicable first-party scope; identify remaining unmeasured host code.
New or changed Python/C# functions require meaningful measured tests.

## Local Rhino acceptance (important soft gate)

For code changes, follow [the local review](../docs/local-rhino-acceptance.md):
open **all supported examples**, execute/render them, and inspect numbers and
images. The PR creator supplies evidence; the maintainer owns the merge decision.
No self-hosted CI runner is required. Do not mark unrun checks as passed.

- Commit and actual loaded plugin artifact/hash:
- OS / Rhino / Grasshopper / Python / PyTorch / actual device:
- Per-example evidence record (settings, steps/time, observed numbers, inspected
  canvas/viewport images, failures and omissions):
- Required / executed / numerically inspected / visually inspected / pass / fail
  / blocked / not-run totals:
- Reviewer/date; maintainer disposition for failures or accepted omissions:

Preserve user documents and modified legacy example 09; use supported example 10.
Use new recording paths and confirm owned-work cleanup. Local host review is not
measured host coverage or physical qualification. For a documentation-only PR,
explain why live execution is not applicable rather than claiming a pass.
