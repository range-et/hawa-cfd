# Example 35 flow study

[Watch the 57-second flow study](35-wing-flow-study.mp4): 25 real spanwise
speed slices, a 0.8 m/s speed isosurface orbit and native Rhino comparison
charts for seven measured angles. The earlier video is retained below.

All seven cases used **0.01 m cells (499,041 nodes)**, **1 m/s**, 3000 settling
advances and 201 samples. Every measurement window passed the unchanged 0.05
stationarity criterion. Three independent native studies (+3; −9/−6/−3;
0/+6/+9) respected the existing three-fine-case retention limit. The shipped
Grasshopper archive still defaults to two angles. The larger charts are native
Rhino presentation geometry from exact batch means, not a new public plot node.

| Angle | CL | CD | Total lift (N) | Total drag (N) |
| --- | --- | --- | --- | --- |
| -9° | -0.25182483315 | 1.37301835510 | -0.01888686249 | 0.10297637663 |
| -6° | -0.12907944508 | 1.35048157161 | -0.00968095838 | 0.10128611787 |
| -3° | 0.00289690847 | 1.34528788613 | 0.00021726814 | 0.10089659146 |
| +0° | 0.15092000538 | 1.35087852331 | 0.01131900040 | 0.10131588925 |
| +3° | 0.29115512877 | 1.35705996105 | 0.02183663466 | 0.10177949708 |
| +6° | 0.41376398126 | 1.37498278515 | 0.03103229859 | 0.10312370889 |
| +9° | 0.55921745488 | 1.41226514548 | 0.04194130912 | 0.10591988591 |

The last batch required one unchanged-input repoll to publish its completed
results after a stalled Grasshopper publication. Its generation stayed unchanged;
no new solve was submitted. This is a manually recovered run, not an automatic
completion pass. The unresolved trigger is tracked in
[#122](https://github.com/range-et/hawa-cfd/issues/122).

The flow views use the +3° instantaneous capture. Moving a slice or camera does
not animate simulation time. Speed colours span 0–1.4 m/s; pressure spans 0–4 Pa.
The isosurface reaches the outlet and is **domain-truncated**. Seven independent
points do not establish a converged polar or engineering accuracy; numerical
qualification remains open in [#40](https://github.com/range-et/hawa-cfd/issues/40).

[Capture identities, exact values and encoded-media provenance](35-wing-flow-study.provenance.json) ·
[Expanded review and scope](../../../docs/review-wing-flow-video.md).

# Earlier pressure-only walkthrough

[Watch the 28-second Rhino walkthrough](35-wing-pressure-study.mp4).
It shows the editable closed wing, real camera orbits around two retained
pressure fields, and the three native Rhino CL/CD scatter plots.

The CPU run used **0.01 m cells (499,041 nodes)**, 3000 settling advances and
201 samples per case. Both measurement windows passed the 0.05 stationarity
criterion. All 5,288 pressure samples were valid in each case. A shared
**0–4 Pa** legend avoids clipping the positive pressure offset.

| Angle | CL | CD | Total lift (N) | Total drag (N) |
| --- | --- | --- | --- | --- |
| −3° | 0.00289690847 | 1.34528788613 | 0.00021726814 | 0.10089659146 |
| +3° | 0.29115512877 | 1.35705996105 | 0.02183663466 | 0.10177949708 |

Camera motion changes the viewpoint, not the flow. Pressure is an instantaneous
offset sample; loads are whole-body window means, not per-face pressure forces.
Two samples do not define a continuous polar. Grid/domain sensitivity and
physical-reference qualification remain open.

[Provenance and QA](35-wing-pressure-study.json) records the actual installed
build, identities, measurement windows, source hashes and fixed crop bounds.
The 144 orbit images are genuine Rhino captures, with no generated intermediate
frames. Empty margins were cropped consistently; complete wing geometry and
legend labels remain visible. Earlier interrupted runs and the first clipped
camera framing are excluded. Final assembly/lifecycle checks are separate in
[the host review](../../../docs/review-parametric-wing-example.md).
