# Hawa v0.3.0 — parametric hull and Galapagos

This experimental release adds a complete hull search assembly in Grasshopper.

- **Parametric Hull** creates a closed canoe hull. Bow, stern, and beam / draft change its shape. Length and mesh volume stay fixed.
- **Evaluate** completes a fresh CFD run before it emits fitness. It measures momentum exchange at the hull boundary.
- **Example 09** contains the hull, fixed tank, fluid controls, result previews, and linked Galapagos object. It opens disabled.
- **17 Hawa components** and **9 editable definitions** are included.

[Download the complete Rhino 8 package](https://github.com/range-et/hawa-cfd/releases/download/v0.3.0/Hawa-0.3.0-rh8.zip). Replace the complete Hawa folder and restart Rhino.

[Hull instructions and limits](https://github.com/range-et/hawa-cfd/blob/main/docs/hull-optimization.md) · [Recorded search](https://github.com/range-et/hawa-cfd/blob/main/docs/media/hull-search.json)

Verification: 83 Python tests passed, 29 skipped. All eight previous definitions reopened and completed 25 MPS steps. The new hull definition passed closure, fixed volume, Galapagos links, completed evaluation, result mesh, and idle-reopen checks. A visible Galapagos run completed ten genomes on MPS. Reinstating the selected hull reproduced its score.

The hull example models a fully submerged stationary body in a viscous demonstration fluid. It excludes waves, a free surface, buoyancy, and boat motion. The coarse grid changes voxel volume. The short search demonstrates the assembly and does not establish an optimum or a real-boat resistance improvement.

CPU and MPS checks passed. NVIDIA hardware and Windows installation checks remain open. The package retains all third-party notices.
