# Launch walkthroughs

The two 1920 × 1080 H.264 MP4s use captioned screenshots of the verified Rhino sessions. They contain no audio and are not continuous screen recordings. The underlying observations are described in `docs/captures/README.md`.

| Video | Duration | Download |
| --- | --- | --- |
| First look | 1:03 | [MP4](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/hawa-first-look.mp4) |
| 3D block workflow | 1:14 | [MP4](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/hawa-block-workflow.mp4) |

`walkthroughs.json` records titles, durations and chapter timings. Run `scripts/make_walkthroughs.py` on macOS with Pillow and ffmpeg to recreate the assets in ignored `dist/videos/`. The script uses the system Arial fonts and preserves the result screenshots without fabricating solver motion.
