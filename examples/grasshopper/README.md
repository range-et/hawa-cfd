# Editable Grasshopper examples

Open these definitions in Rhino 8 with the complete Hawa plugin installed. Each supported definition has three guide panels and numbered workflow groups. Read left to right. Inputs sit near their consumers; output panels are on the right. Save a copy before changing a shipped example.

For agent operation through Rhino MCP alone, read [the MCP guide](../../docs/agents/rhino-mcp.md). The plugin bundle carries the same guide in `docs/agents/rhino-mcp.md`.

## Choose an example

| Definition | Explore | Units / main limit |
| --- | --- | --- |
| [01-tgv3d-bgk.gh](01-tgv3d-bgk.gh) | Change grid size, backend and target iterations. Inspect velocity decay. | Reference units. Use this small case to check installation and backend selection. |
| [02-tgv2d-bgk.gh](02-tgv2d-bgk.gh) | Change grid size and target iterations. Compare the same physical time. | Reference units. This is a planar numerical benchmark. |
| [03-tgv2d-trt.gh](03-tgv2d-trt.gh) | Compare the TRT collision model with example 02 at matching settings. | Reference units. Collision models can have different stability limits. |
| [04-tgv2d-smagorinsky.gh](04-tgv2d-smagorinsky.gh) | Change grid resolution and compare decay with example 02. | Reference units. Subgrid modelling does not replace a grid study. |
| [05-tgv3d-smagorinsky.gh](05-tgv3d-smagorinsky.gh) | Compare this 3D case with example 01 at matching settings. | Reference units. Begin with a small grid and increase it gradually. |
| [06-cavity2d-bgk.gh](06-cavity2d-bgk.gh) | Run the cavity and inspect the recirculation pattern. | Reference units. Wall-adjacent fields require grid refinement. |
| [07-poiseuille2d-guo.gh](07-poiseuille2d-guo.gh) | Inspect the velocity profile across the channel. | Reference units. Compare profiles after the flow has settled. |
| [08-wind-around-block.gh](08-wind-around-block.gh) | Edit domain, closed mesh, grid spacing and physics. Inspect slice and flow lines. | Geometry uses metres. Demonstration viscosity is not atmospheric air. |
| [10-responsive-hull-search.gh](10-responsive-hull-search.gh) | Enable evaluation and Run search. Pause holds the current candidate; disabling cancels. | Single fluid, submerged hull. No waves or buoyancy. Short scores demonstrate search; they do not establish an optimum. |
| [11-block-3d-visualization.gh](11-block-3d-visualization.gh) | Use the shared snapshot to compare planes, tubes, contours and isosurfaces. Change field and colour map. | Use one snapshot for comparisons. Keep colour ranges fixed when comparing cases. |
| [12-local-airfoil-rc-wing.gh](12-local-airfoil-rc-wing.gh) | Choose an offline NACA code or local coordinate file. Edit wing span/chord. Load your own local polar. | The bundled polar is synthetic format data. Lifting-line results assume attached flow; stall is not predicted. |
| [13-record-and-playback.gh](13-record-and-playback.gh) | Choose a new absolute output directory. Start Record, wait for completion, then change Frame. | Recording creates files. Use a new directory for each run. Playback must use the returned manifest. |
| [14-curved-sphere-pressure.gh](14-curved-sphere-pressure.gh) | Run the sphere. Inspect pressure and surface samples; compare grid spacings. | Experimental stationary curved links. Do not combine with refinement or moving bodies. |
| [15-fixed-refinement.gh](15-fixed-refinement.gh) | Edit the domain and interior patch; run both grids and compare their field planes. | One fixed 2:1 BGK patch. Keep interpolation stencils in fluid. No automatic adaptive mesh. |
| [16-cylinder-wake-recording.gh](16-cylinder-wake-recording.gh) | Set a new absolute directory, then record the wake. Pause/resume or cancel. Replay saved frames. | The full recording runs 8000 steps. Use a smaller trial first. Outlet and domain size affect the wake. |
| [17-oscillating-cylinder.gh](17-oscillating-cylinder.gh) | Set travel amplitude in metres. Run the case; inspect the shared field snapshot and moved body. | Prescribed motion, uniform BGK. Keep the full trajectory two cells from domain faces. Check grids and cycle averages. |
| [18-pitching-airfoil.gh](18-pitching-airfoil.gh) | Edit the offline NACA section and wing. Set pitch amplitude in radians; run and inspect loads. | Coarse thick-foil demonstration. RC boundary layers are not resolved. Motion does not respond to fluid forces. |
| [19-rotating-paddle.gh](19-rotating-paddle.gh) | Set RPM and run. Inspect body pose, torque and signed fluid power. | Single fluid. No water surface, cavitation or free-body response. This is not a validated propeller model. |
| [20-motion-cycle-search.gh](20-motion-cycle-search.gh) | Run search. Each amplitude is evaluated only after settling and complete measured cycles. Pause or cancel as needed. | Default objective is input power. Compare longer settling, more cycles and finer grids before ranking designs. |

Example **09** is a historical Galapagos definition with user edits. It is preserved in this checkout and excluded from the supported package. Use **10** for asynchronous hull search. It is not part of the layout cleanup.

## Run and inspect

1. Start with example 01 and a small grid. Rhino installs pinned dependencies on first use. This needs internet access and can take time.
2. Select `cpu`, `mps`, `cuda:0` or `auto`. `auto` chooses an available accelerator; small moving cases can be faster on CPU.
3. Wait for geometry/case preparation, then enable the run control. Target iterations is an absolute total.
4. Solve uses Run false to pause and Run true to resume. Reset true then false clears state. Evaluate and Record use Enable/Run false to cancel. Search uses completed candidate IDs; do not feed it partial fitness.
5. Read errors and reports. Require valid output geometry and a completed result before describing a run as successful.
6. Compare the same physical time and fixed colour limits. Check grid, domain-size and settling sensitivity before using loads.

## Recording and moving bodies

Examples 13, 16 and 17–19 include recording controls. Set a **new absolute directory** before starting Record. Use its completed manifest for Playback, then move the Frame slider. Do not point separate runs at the same directory.

Moving bodies use uniform BGK and prescribed rigid motion. Body Preview and the field views should use the same snapshot. Force is fluid force on the body; power is signed fluid work. Motion Evaluate defaults to input power, the negative of fluid power. No waves, buoyancy, free-body response, contact or thermal transport are modelled. Read [the moving-surface guide](../../docs/moving-surfaces-v0.4.md).

## Local airfoil data

Example 12 uses `data/naca0012.dat` and `data/polar-format.csv`. Relative paths resolve from the definition folder; keep the `data` folder beside the definitions. The polar is synthetic format data, not measured aerodynamic evidence. Users supply their own coordinate and polar files. No database or website is queried.

## Maintainer checks

`annotations.json` contains the example-specific descriptions. Run `scripts/annotate_grasshopper_examples.cs` through Rhino MCP after regenerating definitions. It checks that connections are unchanged and saves local backups. `scripts/capture_example_layouts.cs` renders each supported canvas without running its solver. Adjust the checkout path in either script before use on another machine.

The gallery covers selected workflows. It is separate from the sixteen upstream Lettuce entrypoints and does not claim to wrap every upstream example. CPU/MPS PorousMedium parity remains a documented open issue.
