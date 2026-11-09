# Hawa 0.5 review film and build log

Local draft prepared November 8, 2026. Author and reviewer: Codex, self-review.
No upload, Git push, GitHub Pages deployment or YouTube publication was performed.
The user will review the video and page before selecting publication mechanisms.

## Deliverables and reproduction

- Film: `dist/videos-v05/hawa-0.5-build-log.mp4` (also `site/media/`).
- Duration: 250 seconds; 1920 × 1080, 24 fps, H.264, captioned, no audio.
- Article: `site/build-log/0.5.html`; homepage entry: `site/index.html#build-log`.
- Storyboard, chapter times and source hashes: `storyboard.json`.
- Caption track: `site/media/hawa-0.5-build-log.vtt`.
- Run `.venv/bin/python scripts/make_v05_demo.py` to render from the existing
  captures and earlier motion/wake MP4s. These older excerpts are labelled in
  the film. The renderer writes final MP4 decode samples, not only source slides.
- Copy the generated film/caption into `site/media`, provenance into
  `site/assets/v05/storyboard.json`, and the first decoded frame into
  `site/assets/v05/poster.jpg` after an approved edit.
- Build: `.venv/bin/python scripts/build_site.py`.
- Preview: `.venv/bin/python scripts/preview_site.py`.
  Open `http://127.0.0.1:8056/build-log/0.5.html`.

The pinned Monad palette and existing typography guide the page and video.
There are no added floating title bars. Caption wording is direct; no generated
speech is used. The film is a screenshot walkthrough with two recorded simulation
excerpts. It does not claim to be a continuous screen recording of a new run.

## Review gates

| Gate | Decision | Evidence |
| --- | --- | --- |
| G0 scope | PASS | Covers the verified 0.5 panel, selected geometry, live binding, persistence, curved-wall and cleanup changes. Existing GH features and older recordings are identified. |
| G1 architecture | NOT APPLICABLE | No solver, runtime or shared-state production code changed. |
| G2 software | PASS | Site build, JS syntax check, local HTML asset/link checks, MP4 source hash match and complete ffmpeg decode passed. Preview byte-range requests returned correct 206 bodies; chapter seeking was tested in browser. |
| G3 scientific communication | PASS, presentation only | Reviewed against native guide, curved-boundary report, example catalogue and cleanup/full-gate reports. Uniform lattice, reconstructed display colours, physical-time comparison and experimental scope remain explicit. No new numerical claim or new simulation run. |
| G4 media/UI | PASS | Inspected decoded middle and end frames of all 25 scenes, including the final frame. Corrected the physical-setup crop and rerendered. Desktop 1440 × 1000 and mobile 390 × 844 had no document overflow. Checked dark/light theme, loaded images, chapter playback, homepage navigation and console errors (none). |
| G5 publication | NOT RUN | Deliberately local for user review. Hosting and YouTube decisions are pending the user's review. |

One initial setup-scene crop showed empty viewport space. The final cut uses the
actual setup controls. The default Python server lacked byte-range support;
`preview_site.py` fixes local video seeking. Final seek test reached 210 seconds
through the Cleanup chapter button. All 50 final decode samples exist under
`dist/videos-v05/decoded`, with contact sheets beside them. `qa.json` records the
final MP4 hash and checks. Screenshots in this directory show the reviewed page.

The page keeps PorousMedium parity and platform-verification gaps visible. The
video contains no CUDA-pending title card, matching the earlier editorial request.
