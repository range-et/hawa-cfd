# Expanded native wing-flow video

## Scope

This follow-up addresses the pressure-only walkthrough with surrounding-flow
views and more measured angle points. It changes documentation and presentation,
not the solver, public component contract or shipped Grasshopper archive.
The original `35-wing-pressure-study.mp4` remains historical evidence. The new
media is `35-wing-flow-study.mp4`, with capture identities and exact values in
[its provenance](../examples/grasshopper/videos/35-wing-flow-study.provenance.json).

## Evidence available

The parent agent ran the installed plugin in Rhino on Mac CPU, embedded Python
3.9.10 / PyTorch 2.8.0. The foreground environment reports 12 CPU threads; this is
not a measured background-thread or performance guarantee. The fresh +3° case at
1 m/s completed with 499,041 nodes, 0.01 m cells, 3000 settling steps and 201
samples. The stationarity threshold remained 0.05. Its accepted CL is
0.291155128765001 and CD is 1.3570599610499743; lift is
0.021836634657375075 N and drag is 0.10177949707874806 N.
The capture is step 3200 at 0.5542562584220407 s; the averaging window spans
0.5196152422706631–0.5542562584220407 s. All 5288 offset pressure samples are
valid and lie within the shared 0–4 Pa colour range.

Local raw evidence lives in `results/native-flow-video/`:
`environment.json`, `installed-assemblies.json`, `source-case.json`,
`selected-0-video-evidence.json`, `flow-captures-v3/`,
`pressure-final-v2.json` and `combined-capture-v2/`. Earlier capture attempts
with wire overlays or incomplete initial rendering are retained but excluded.
There are 25 real XZ speed-slice positions at Y = −0.36…+0.36 m and 72 real
camera views of the 0.8 m/s speed isosurface. Slice colours use 0–1.4 m/s.
Changing the slice position or camera does not advance simulation time.
The isosurface reaches X = 0.6000000000000001 m, matching the outlet at 0.6 m;
its domain-truncated extent must remain labelled.

The final local `wing-flow-snapshot-labelled.3dm` readback contains 16 valid
native objects in metres, including pressure/speed legends and labels on their
corresponding layers. Pressure and the centre speed slice are visible; geometry
and isosurface layers can be revealed. Use shaded mode with mesh wires off.
This is a baked visual snapshot, not checkpoint/import data. Earlier snapshots
remain preserved.

## Seven-angle measurements and publication recovery

All seven angles are accepted with 201 samples and the unchanged 0.05 threshold.
The recorded batches are +3 alone, −9/−6/−3 and 0/+6/+9, respecting the unchanged
1.5-million aggregate retained-cell guard. The shipped archive and its two
angle defaults are unchanged. Larger charts use native Rhino presentation
geometry baked from exact batch means, not a new public GH plot or batching
feature. The independent finalizer checked exact public means, window, references,
step 3200 and force divided by 0.075 N against CL/CD for every case.

| Angle | CL | CD | Total lift (N) | Total drag (N) |
| --- | --- | --- | --- | --- |
| -9° | -0.25182483315 | 1.37301835510 | -0.01888686249 | 0.10297637663 |
| -6° | -0.12907944508 | 1.35048157161 | -0.00968095838 | 0.10128611787 |
| -3° | 0.00289690847 | 1.34528788613 | 0.00021726814 | 0.10089659146 |
| +0° | 0.15092000538 | 1.35087852331 | 0.01131900040 | 0.10131588925 |
| +3° | 0.29115512877 | 1.35705996105 | 0.02183663466 | 0.10177949708 |
| +6° | 0.41376398126 | 1.37498278515 | 0.03103229859 | 0.10312370889 |
| +9° | 0.55921745488 | 1.41226514548 | 0.04194130912 | 0.10591988591 |

The final batch remained unpublished for over 180 seconds with solution depth
zero, PostProcess state, no pending Hawa refresh requests, valid inputs, empty
outputs and no reported error. One unchanged-input repoll recovered all three completed cases
at generation 3, without a new submission or Run toggle. Raw before/after records
remain in `results/native-flow-video/angle-batches/`. This is **manual recovery**,
not an automatic completion pass. The trigger remains unknown and is tracked in
[#122](https://github.com/range-et/hawa-cfd/issues/122); this media change does not
repair it. The study was cooperatively closed and the original GH document restored.

## Media QA

The media agent inspected 23 decoded frames spanning every chapter, including
the native seven-point charts and final numeric table. The encoded video is
57 seconds, 1920 × 1080, 24 fps, H.264, silent, 2,852,279 bytes; SHA-256 is
`56f9a9593857a4ee17ebc0da8c5955969ff70a0b96e1222efd13a309e4a529db`.
Pressure 0–4 Pa and speed 0–1.4 m/s legends remain visible. The parent agent independently inspected all 23 contact-sheet frames and
full-size decoded frames at 46.5 and 54.0 seconds. Chapter transitions, native
plot labels/markers and the numeric table were readable; values matched the
verified measurements.

Fixed crop bounds and hashes for all 97 slice/orbit frames are retained in
`results/wing-flow-video-tools/flow-crops-v3/crop-provenance.json`;
`still-crop-provenance.json` records the pressure/combined still crops.
The final contact sheet is
`results/wing-flow-video-tools/final57-v1/qa-contact-sheet.png`.
No generated flow frames or fitted polar are substituted for measured evidence.

## Numerical limits

These are experimental whole-body window means using synthetic viscosity.
Instantaneous pressure colours are not per-face force measurements. More angle
points and a clearer view do not resolve the existing grid/domain sensitivity
failure or missing matched physical reference; GitHub #40 remains open.
No time-dependent wake animation, stall qualification or engineering accuracy
is claimed.
