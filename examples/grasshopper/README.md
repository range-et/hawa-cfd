# Editable Grasshopper examples

Install the complete Hawa plugin folder, restart Rhino 8, then open one of these `.gh` files. First use installs dependencies inside Rhino. Choose a Backend and double-click Run / Pause. Keep Grasshopper open for the Rhino preview.

| File | Explore |
| --- | --- |
| 01-tgv3d-bgk.gh | 3D decaying Taylor–Green vortex; start here |
| 02-tgv2d-bgk.gh | 2D Taylor–Green vortex |
| 03-tgv2d-trt.gh | Two-relaxation-time collision |
| 04-tgv2d-smagorinsky.gh | 2D Smagorinsky collision |
| 05-tgv3d-smagorinsky.gh | 3D Smagorinsky collision |
| 06-cavity2d-bgk.gh | Driven cavity |
| 07-poiseuille2d-guo.gh | Forced channel flow |
| 08-wind-around-block.gh | Domain, closed obstacle, physics, boundaries, solver, slice and streamlines |
| 09-parametric-hull-galapagos.gh | Constant-volume hull, three shape genes, completed CFD fitness, Galapagos and flow preview |

All definitions contain editable controls and instructions. The block example internalizes its geometry and explicitly uses meters. Its viscosity is a demonstration value, not atmospheric air. The numerical cases use Lettuce reference units.

Run false pauses; Reset true → false clears state; Run false → true resumes. Target iterations is an absolute total. Save a copy before experimenting. This gallery does not yet wrap all sixteen upstream Python/notebook entrypoints.

The hull example uses **Enable evaluation** instead of Run. Enable it, wait for a result, then open Galapagos and start the solver. It models a fully submerged body in a viscous demonstration fluid. See [the hull guide](../../docs/hull-optimization.md).
