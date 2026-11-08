# Native panel and live GH sync

Load Hawa.Rhino.rhp, run `Hawa`, then open `21-native-live-sync.gh`.

The three annotated sliders edit the same case as the native panel. Run, pause, resume and cancel in the panel. Changes invalidate the previous simulation. The field mesh output can feed ordinary GH mesh tools; the native viewport already draws it.

The GH file is an unbound template. Its initial slider values are applied to the active case. Save your `.3dm` and `.gh` together after binding. Reopening never starts the solver automatically.

`native-block.3dm` supplies a saved settings example. This is a coarse block-flow demonstration with an artificial viscosity, not a validated aerodynamic prediction. Read `docs/native-prototype-v0.5.md` for ranges, ownership and limits.
