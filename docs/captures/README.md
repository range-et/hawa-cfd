# Hawa walkthrough captures

These JPEGs are unaltered computer-use screenshots of the running Rhino/Grasshopper UI. They are still images for a later video edit, not a continuous screen recording. The numerical results shown were computed inside Rhino.

| Shot | Content | Suggested use |
| --- | --- | --- |
| 01-hawa-toolbar.jpg | Restored Hawa tab and original icons | Introduce the plugin |
| 02-vortex-ready.jpg | Editable vortex graph and MPS-ready monitor | Explain three workflow groups |
| 03-vortex-mps-completed.jpg | 200 completed iterations on MPS | Demonstrate embedded GPU execution |
| 04-vortex-rhino-preview.jpg | Colored vortex slice in Rhino | Cut from graph to result |
| 05-block-ready.jpg | Domain → Geometry / Physics / Boundaries → Case → Solve → results | Walk through physical setup |
| 06-block-mps-completed.jpg | 300 completed block-case iterations | Show progress and diagnostics |
| 07-block-rhino-preview.jpg | Block, speed slice and snapshot streamlines | Show geometric results |

For a later recording: open `01-tgv3d-bgk.gh`, choose backend, toggle Run, inspect the monitor, switch speed/pressure, and change the slice. Then open `08-wind-around-block.gh`, explain explicit meters and demonstration viscosity, run, and inspect the obstacle and streamlines. Leave Grasshopper open while viewing the Rhino preview. Pause before changing solver inputs. Record both windows together for the continuous interaction sequence.

The colors auto-range; compare their displayed numeric range, not color alone. The block case is a workflow demonstration, not validated atmospheric CFD. No NVIDIA hardware was used in these captures.
