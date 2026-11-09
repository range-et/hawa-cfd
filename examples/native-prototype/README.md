# Native panel and live GH sync

Load Hawa.Rhino.rhp, run `Hawa`, then open `21-native-live-sync.gh`.

The three annotated sliders edit the same case as the native panel. Run, pause, resume and cancel in the panel. Changes invalidate the previous simulation. The field mesh output can feed ordinary GH mesh tools; the native viewport already draws it.

The GH file is an unbound template. Its initial slider values are applied to the active case. Save your `.3dm` and `.gh` together after binding. Reopening never starts the solver automatically.

`native-block.3dm` supplies a saved settings example. This is a coarse block-flow demonstration with an artificial viscosity, not a validated aerodynamic prediction. Read `docs/native-v0.5.md` in the package for ranges, ownership and limits.

## 22 / Selected Rhino geometry

Open **22-selected-canopy.3dm** first, run `Hawa`, then open
**22-native-selected-geometry.gh**. This is an editable closed canopy mesh and
physical domain. The two annotated sliders control speed and cell size. Block
width stays disconnected. Right-click a slider for precise values.

The native panel runs without GH. Select bodies and edit domain/fluid settings
in Setup; choose resolution/backend/target in Solve; choose field/slice/colour
limits in View. Press Apply setup or Apply display after editing those forms.
Run, pause, cancel and reset remain visible above all tabs. The default 200-step
run is a workflow demonstration, not a convergence criterion.

Expected output: domain wireframe, valid coloured plane and captured field
step/time. A physical edit or body deletion invalidates results; a display edit
keeps the session. Missing bodies report an error. Reopening preserves object
references and stays idle. Save changed files as a new `.3dm`/`.gh` pair.

The 0.8 m canopy and viscosity 0.1 m²/s are deliberately coarse demonstration
settings. This is not an RC aerodynamic prediction. Use physical fluid properties,
resolved geometry and sensitivity/reference studies before interpreting designs.
Use the review gates and example matrix in the package for repeatable checks.

## 23 / Curved solid

Open `23-curved-solid.3dm`, then open the Hawa dockable panel. The saved case is
idle, with backend Auto, a closed spherical Brep, 0.1 m cells and interpolated
stationary walls enabled. Press Run for the 100-step demonstration. View shows
pressure using the spectrum palette. The radius is 0.43 m, so this is a coarse
workflow example rather than a resolved engineering case.

Compare 0.1 m and 0.05 m cell sizes. Brep tessellation is rebuilt for each spacing.
Compare equal physical times and fixed colour limits; equal iteration counts
represent different times. The viscosity is the demonstration value 0.1 m²/s.
For a GH assembly of the same operation, use example 14 and its optional S input.
See [curved-solid verification](../../docs/curved-boundaries-v0.5.md).
