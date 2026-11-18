# November buildlog and YouTube publication

Date: November 18, 2026. Author/reviewer: Codex root (self-review).
Source baseline: merged main `7558e575069d9f51cb9c8db6021ab5863a46fbda`.
Scope: publish the existing wing video and a dated GitHub Pages development
update. No solver, plugin, example archive, dependency or numerical policy changes.
Original dirty development checkout and all prior worktrees remain untouched.

## Claims and evidence

The [new buildlog](../site/build-log/2026-11.html) links merged PRs #107, #109,
#110, #112–#114, #116, #118–#119, #121 and #123. It distinguishes merged work,
historical verification, development packages and releases. Earlier buildlogs
remain available; the homepage features the new film and links the older one.
The seven table rows are rounded directly from the committed
[video provenance](../examples/grasshopper/videos/35-wing-flow-study.provenance.json).
No new numerical execution or physical qualification is claimed.

The exact 57-second MP4 was uploaded through the user's open YouTube Studio
page. Copyright and Community Guidelines initial checks both reported no issues.
Public visibility was selected; Studio confirmed “Video published” with
[the public URL](https://youtu.be/xTUaspfebHw). The title, technical description,
source links and experimental limits were entered. No paid promotion was started.
[Publication metadata](media/wing-flow-youtube.json) records the source hash and
still-frame times. Native scientific captures were reused without generated imagery.

## Checks and gate decisions

| Gate | Disposition | Actual evidence / limits |
| --- | --- | --- |
| G0 | PASS for publication scope | Claims traced to committed reviews, video provenance, merged PRs and current issue states; no new numerical method or dependency. |
| G1 | NOT APPLICABLE to runtime | Static HTML/CSS/assets and documentation only; no state or API change. |
| G2 | PASS for local static checks | Existing site builder succeeds; changed-page relative paths/anchors, unique IDs, repository evidence links, seven rounded measurement rows and source video SHA256 checked. No Python/C# function changes; no local solver suite or coverage regeneration needed. Exact-head CI/review remain the merge gate. |
| G3 | PASS for representation only | Table values match provenance; synthetic viscosity, grid/domain failures, pressure-versus-force distinction and domain-truncated equal-speed surface are explicit. Historical checks retain their device/source scope. |
| G4 | PASS for bounded browser review | Actual browser renders at 1280px and 390px, dark/light themes, video embed, charts, table, example cards, data instructions, evidence and closing sections inspected. No page-wide overflow at 390px; the table scrolls within its region. Both stills loaded at 1440px natural width; final combined-flow still inspected separately. Homepage viewed at 547px. Local captures retained under results/. |
| G5 | Local build PASS; publication tracked by PR/Pages workflow | YouTube publication confirmed. GitHub Pages publication must follow final-head CI, Greptile 5/5, merge and successful deployment; the eventual PR/deployment record is authoritative. No plugin package/release created. |
| G6 | NOT APPLICABLE | No product combinations, public nodes, formats, executable runtime or GH archives changed. |

Checks used the isolated checkout's Python 3.9 `.venv` and
`scripts/build_site.py --output dist/site`. The local readback script and browser
captures are in `results/`; source HTML and machine-readable video provenance
make the content comparisons reproducible. The buildlog retains #40, #122,
#61, #39, #83 and atmospheric qualification gaps; no issue is closed by this change.
Rhino was not operated or restarted during publication.
