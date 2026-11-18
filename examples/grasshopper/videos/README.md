# Example 35 video

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
