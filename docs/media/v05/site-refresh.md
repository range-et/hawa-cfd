# Website refresh after YouTube publication

Codex self-review, November 8, 2026. Local changes only; no Git push or deployment.

The homepage now describes 0.5, its native setup, shared GH case, current examples
and verification limits. Historical 0.3/0.4 material moved to versioned build-log
pages. The index links all three versions. The archived 0.3 download remains
available with its historical scope; no 0.5 release-download URL is invented.

The homepage and 0.5 article embed YouTube video `6oiTFRT7qRg` through the
privacy-enhanced player. Chapter buttons load that player at the selected start
time. Direct YouTube links remain available. The old videos are filtered by
version on the archive pages, and the transcript remains on the 0.5 page.

Raw MP4/VTT website copies were moved out of the source and preview directories
into `results/v05/website-media-archive`; the original rendered film remains in
`dist/videos-v05`. Do not copy the raw film back into the site when rebuilding.
The previous media-review README describes the initial local-film review stage.

Checks performed:

- Static site build and JavaScript syntax checks passed.
- All relative HTML asset and page links resolve.
- No raw video player or MP4 source remains in the homepage or 0.5 article.
- Browser confirmed the YouTube embed and chapter URL with `start=210`.
- Archive pages loaded two 0.4 videos and three earlier 0.3-era walkthroughs.
- Homepage and archive layouts checked at 1440 px and 390 px; no document overflow.
- Homepage and build-log screenshots saved beside this record.

G0/G3: presentation claims reviewed against existing guides and verification
records; no new numerical claim. G1: no engine/shared-state change. G2/G4: checks
above passed. G5: publication intentionally not run. The site's current-build
label does not imply an unrestricted platform or engineering-validation pass.
