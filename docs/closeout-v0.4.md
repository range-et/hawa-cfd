# Hawa 0.4 local release closeout

The experimental 0.4 feature baseline is complete at commit `6ac6633`. The frozen
local artifact is `dist/releases/v0.4.0/Hawa-0.4.0-rh8.zip`, SHA-256
`be45d17cbcda550141bda6281919688e576aa7073f6d3ae1f39ef4bbc12c0b3c`.
It contains the plugin, embedded Python source, corresponding build source,
license notices, 19 supported definitions and the Rhino MCP agent guide.
This is a local release baseline; no public release or new video upload is implied.

The package has 46 components. All 19 supported definitions were annotated and
rendered for layout review without changing their connections. The modified
legacy example 09 remains untouched and excluded from the package.

[Motion verification](verification-motion-v0.4.json) records 140 passing Python
tests, CPU/MPS engine comparisons, three native moving-body cases, the native
cycle-search lifecycle checks and eleven stationary regression graphs.
[Earlier hardening](hardening-v0.4.json) retains the upstream comparison evidence.
The current artifacts were checked for ZIP integrity and agreement between the
installed assembly/Python files and the checkout. The 30.4-second moving-surface
video was decoded and its beginning, middle and end inspected.

## Carried limitations

- Prescribed moving surfaces and refinement remain experimental. Moving loads
  can contain cell-transition spikes; exact displaced-volume conservation is
  not implemented.
- PorousMedium CPU/MPS comparison remains outside the unchanged tolerance.
- Small moving cases can run slower on MPS than CPU.
- CUDA hardware and Windows installation remain unverified.
- Free surfaces, thermal transport, deforming bodies and force-driven rigid-body
  response remain outside the implemented scope.

The 0.5 prototype begins from this frozen baseline. Its native interface does
not change these numerical claims. See the release notes and moving-surface
 guide for operating limits.
