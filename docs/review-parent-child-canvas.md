# Parent/child canvas roles — November 16, 2026

Example 33 identifies A as outer parent, B as child of A and parent of C, and C
as finer child. Group headings and unconnected guide panels explain one-way
recorded transfer, sample counts versus metres, composed views, and the absence
of a water solver or atmospheric qualification. Functional control nicknames
remain compatible with existing harnesses. This completes the presentation and
live-workflow scope of HAWA-034 / #36, subject to PR merge gates.

Author: Codex root. Independent read-only review: Codex atmosphere_qualification
agent, script/archive preservation, four canvas captures and live output records;
no actionable defect. Gate dispositions below are root self-review.

## Preservation and reproduction

Base: `21bd2056824f84bf4d26dcb559f122a6bed58833`. Only example 33 presentation
changes; example 09 is untouched. Run `scripts/clarify_parent_child_example.cs`
through Rhino MCP after adjusting its checkout path. It saves a local backup,
requires idle toggles and unconnected guide panels, writes a candidate, then
compares serialized archive objects before replacing the source. All 102 IDs,
92 complete functional object archives, and group memberships are identical.
The 10 permitted objects are seven guide panels and three groups.

The script ran twice successfully. Four canvas crops were inspected for fit,
legibility and overlap. Captures and full outputs remain locally in
`results/issue36/`; the compact [machine record](verification-parent-child-canvas.json)
records the committed archive hash and measured outcomes.

Installed host: Rhino 8.37 Mac on Apple M3 Max, embedded Python 3.9 and Torch 2.8,
CPU selected before the first solution. Loaded production assemblies are the
previous combined candidate whose production source matches the base commit:
Grasshopper SHA256 `36c94c17f9339914fbe2cb89ad2136f3c1766bbfe2e055ec842b513e58d87a1c`,
Rhino SHA256 `f507b784a6fc256f500898a6c2b7f3e0956a9e3ce69dfe631152273210ef205f`.
No replacement binary was necessary for a presentation-only archive change.

1. Load a copy of the updated archive in an owned GH document. Use metre units,
   CPU devices, three fresh recording directories and two fresh boundary files.
   Keep all supplied geometry, case values, steps and capture windows.
2. Wait for geometry preparation, then enable A Record, B Capture, B Record,
   C Capture and C Record. Poll without blocking the UI or forcing solutions.
3. All three recordings completed at 512/1024/1792 steps; both captures completed.
   Shared slice accepted all three playback frames; no component errors.
   A/B end at absolute 2.9560333782508845 s (floating-point rounding in B).
   C local time 2.5865292059695237 s plus its capture offset
   0.3695041722813605 s matches that absolute time.
4. Inspect the shared slice at 1.5 m and move it to 9 m. Captures show the nested
   field near the ground and parent-only coverage above both children. The
   component's `domains: 3` message counts input frames, not intersected grids.
5. Disable controls, remove/dispose only the owned graph, restore original active
   graph and millimetre units. Both original empty GH documents remain unmodified;
   native live object count is zero. Runtime audit: zero jobs, sessions, Hawa
   workers and pending cleanup.

## Gates and limits

| Gate | Status | Evidence / bounded claim |
| --- | --- | --- |
| G0 research | PASS | Existing parent/child contract and fixed example inputs retained; no new method/dependency. |
| G1 architecture | PASS | All functional archive chunks/identities and group memberships preserved; no API/state changes. |
| G2 reliability | PASS | Script executed twice, candidate reopened and checked before replacement; completed host workflow and cleanup. No production functions changed, so coverage/mutation matrices remain unchanged. |
| G3 numerical physics | NOT APPLICABLE | Presentation change only. Successful workflow is not convergence or atmospheric validation; #21/#26/#27 remain open. |
| G4 UI/UX | PASS | Four guide crops inspected and actual three-stage CPU workflow completed; shared slice inspected at two heights. |
| G5 release/integration | BLOCKED | Ready PR, required CI and Greptile 5/5 review pending. No packaged/released claim. |
| G6 compatibility/examples | PASS | Fresh Rhino archive inventory: 53 public nodes, 31 definitions, 188 distinct observed port combinations. `verify_examples` passes. Numerical matrix was not rerun; its production inputs are unchanged. |

The fresh inventory also corrects two Geometry Check port descriptions to match
already merged source; it adds no new node or contract. No MPS/CUDA rerun, full
gallery acceptance, new numerical qualification, or release build is claimed.
CI runs the required headless suites independently. PR merge gates must pass
before closing #36.
