# Hawa 0.4 experimental update

This is a local development build. The new package has not been published. The corrected [Tools video](https://youtu.be/GN6Ou3yOF_I) and [Wake video](https://youtu.be/zpRlRn9Qbf4) are public and linked from the project website. Use the supplied examples to inspect the implementation and repeat the checks before applying it to an engineering problem.

## Moving-surface development build

Prescribed moving rigid surfaces are implemented as the final experimental base feature for 0.4. Translation, rotation and oscillation drive time-dependent flow and measured body loads. Native and numerical evidence is recorded in the moving-surface guide. See the [moving-surface guide](moving-surfaces-v0.4.md) for boundaries, nodes and acceptance checks. Thermal transport remains outside this release.

## Known numerical issue

The local hardening pass found that the upstream PorousMedium example exceeds the unchanged CPU/MPS comparison tolerance after 50 steps. Both runs finish with finite fields and matching obstacle masks. Its relaxation time is 0.5009765625; the cause of the growing numerical difference remains unresolved. The other 15 upstream example comparisons and the separate engine comparison suite pass. See the [hardening review](hardening-v0.4.md) for measurements and current test results. Do not interpret successful execution as cross-device numerical agreement for this case.

## Added

- GPL-3.0-only for original Hawa code, with corresponding source in the plugin ZIP and retained upstream notices.
- Background geometry, case creation, evaluation and field queries. Search waits for completed candidate IDs. Pause, resume, cancel and document cleanup use cooperative checkpoints.
- Domain wireframes, 3D flow tubes, arbitrary field planes, contours, isosurfaces, surface-offset samples, legends and shared blue-green/spectrum/diverging maps.
- Pressure, Cp, speed, density, velocity components, vorticity magnitude and Q. Derivative stencils touching solids are masked.
- Local Selig/Lednicer airfoil coordinates, CSV/XFOIL polars and offline NACA four-digit generation. Cl, Cd, Cm and L/D are interpolated within the supplied data range. No website requests.
- Unswept tapered-wing geometry and attached-flow lifting-line analysis. Optional local polar data supplies approximate profile drag.
- Field recording, playback and time-dependent particle paths, with physical times and completion metadata.
- Geometry checks, voxel preview, experimental stationary interpolated walls and a fixed 2:1 BGK refinement patch.
- Editable definitions 10–20, including four prescribed-motion workflows. The package contains 19 supported definitions; historical example 09 is excluded.

## Bugs fixed

Older component archives with fewer inputs now restore the archived parameter set before appending new defaults. This preserves existing wire IDs. Native examples 01–08 reopened without archive errors.

Mesh classification now uses three oblique intersection rays with duplicate-hit removal. The analytical sphere check matched all 729 sampled classifications. Curved links use explicit segment/triangle intersections because native mesh intersections missed links on triangle seams.

Example generators clear persistent defaults before setting replacements. Stateful components reject accidental multi-item inputs that could repeatedly start and cancel jobs.

The wind outlet previously became unstable near the outlet in long cylinder runs. Hawa now uses zero-normal-gradient population extrapolation. A regression case that failed near step 750 passes 1,000 steps. The new cylinder demonstration completes 8,000 MPS steps. This remains an approximate outgoing-flow boundary; it can reflect disturbances and requires domain-size checks. Vendored Lettuce source is unchanged.

## Verification

| Check | Evidence |
| --- | --- |
| Hawa Python 3.9 suite | 140 passed, 29 skipped, four inherited warnings |
| Vendored upstream suite, earlier run | 419 passed, 884 skipped, 40 warnings |
| C# Release build | No compile errors; Rhino-provided drawing APIs produce platform annotation warnings |
| Native examples 01–08, 11, 12, 14 | 11 graphs passed; flow cases completed 25 steps with valid field meshes; wing closed; local polar output present |
| Native sphere | 300 MPS steps; plane, isosurface, flow and surface Cp outputs |
| Native recording/playback | Completed, with field and isosurface outputs |
| Native refinement | 200 coarse steps / 400 fine steps; both field planes completed |
| Cylinder wake | 81 recorded fields over 8,000 MPS steps; separate native mesh example also completed with playback, plane and flow outputs |
| New media | Captioned videos rendered from actual fields and Rhino captures; no audio or generated flow footage |

The committed check summary is [verification-v0.4.json](verification-v0.4.json). Saved Run=true reopened at zero iterations. Domain and legend previews now survive definition switching.

Machine-readable native reports are generated under `results/v04` by the verification scripts. These output directories are not version-controlled. `scripts/verify_async_controls.cs` records submit/pause/resume/cancel and close timings plus completed candidate history. `scripts/verify_v04_examples.cs` reopens the supported short-run graphs.

The final native control run returned from submit in 46 ms, pause in 33 ms, resume in 41 ms, cancel in 18 ms and close in 80 ms. Five candidates completed after an input change; initial fitness was 3.90536331 and best fitness was 3.84699993. After closing the test definitions, the embedded runtime reported zero registered jobs, zero sessions and no Hawa worker threads. These short-run scores demonstrate the workflow and do not establish a physical optimum.

## Refinement evidence and limits

The fixed patch uses cubic population reconstruction, two fine substeps and filtered nonequilibrium restriction. In a periodic 2D vortex comparison at 40 coarse steps, relative L2 error against a uniform fine reference was 0.00314, 0.00118 and 0.000559 for parent sizes 16, 24 and 32. Corresponding coarse-grid errors were 0.00785, 0.00320 and 0.00169. The smallest CPU and MPS runs had approximately 1.3 ppm composite mass drift. Constant-flow preservation was checked in 2D and 3D. Physical grid spacing and matching simulation times were checked separately.

These tests do not establish accuracy for refined obstacle forces or arbitrary interface crossings. The method has no exact finite-volume refluxing, dynamic patch movement or automatic adaptive subdivision. It currently supports one rectangular 2:1 patch with BGK and voxel walls. Both grids must share physical settings. Keep interpolation stencils in fluid. Curved-wall links and refinement cannot be combined.

The wall-location benchmark reduced planar Poiseuille error from roughly 3.7–3.9% at 8 sites to 0.6–0.7% at 16 sites. Full curved-obstacle convergence remains open.

## Rhino shutdown and remaining scope

Three earlier test instances were terminated with signals, which caused Rhino's signal handler to write crash reports. That restart procedure was removed. Subsequent restarts use the normal Quit command after closing generated test documents. No new crash report was observed during these graceful restarts. The user's modified example 09 has been left untouched.

CUDA hardware, Windows installation, production CFD accuracy and full-duration upstream convergence remain unverified. The first embedded dependency initialization can occupy the UI. Running multiple large live Solve components can still compete for device memory; use the case budgets and small initial grids.

The aircraft tools do not port XFOIL's viscous solver, XFLR5 VLM/panel methods, stall or stability derivatives. The hull model excludes waves, buoyancy and force-driven free-body motion. The airfoil sample polar is synthetic format data and must be replaced for analysis. A multi-building validation study remains outside the supplied evidence.

## References

- [Autodesk Flow Design](https://help.autodesk.com/view/ADSKFD/ENU/files/homepage.htm): visualization workflow reference.
- [OpenFOAM meshing guide](https://doc.cfd.direct/openfoam/user-guide-v6/snappyhexmesh): geometry and refinement scope reference. No OpenFOAM source is bundled.
- [XFLR5 reference repository](https://github.com/subprotocol/xflr5): aircraft-analysis scope reference. No XFLR5 source is bundled.
- [Grasshopper scheduling API](https://developer.rhino3d.com/api/grasshopper/html/Overload_Grasshopper_Kernel_GH_Document_ScheduleSolution.htm): scheduled updates after background work.
- [Lagrava et al., 2012](https://doi.org/10.1016/j.jcp.2012.03.015): grid coupling formulas.
- [Boundary convergence study](https://arxiv.org/abs/1211.0205): wall accuracy and validation background.
