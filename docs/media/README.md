# Videos

The videos use captions and screenshots from the verified Rhino sessions. They have no audio. The edits use Monad colors and Helvetica titles.

The slides contain no added header bars or title rules. The captured Rhino interface retains its original colors.

| Video | Duration | YouTube | Upload text |
| --- | --- | --- | --- |
| Hawa overview | 0:57 | [Watch](https://youtu.be/Ji_9iOYXSXg) | [Title and description](youtube-first-look.txt) |
| 3D block flow | 1:08 | [Watch](https://youtu.be/PVBanKHGhC4) | [Title and description](youtube-block-workflow.txt) |

## Upload to YouTube

1. Select the new MP4 in YouTube Studio.
2. Copy its title from the supplied text file.
3. Copy its description from that file.
4. Select Public for visibility.
5. Publish the video.
6. Send the video link to this chat.

The website uses YouTube embeds. Add each published YouTube ID to `site/videos.json`.

## Recreate the files

Run `scripts/make_walkthroughs.py` on macOS. The script needs Pillow, ffmpeg, ffprobe, Helvetica Neue, and Menlo.

It reads the pinned palette from `vendor/monad_system/colors.json`. It writes the MP4 files to ignored `dist/videos-monad/`.

`walkthroughs.json` records the captions, chapter times, durations, and Monad revision. The H.264 files use a 1920 × 1080 frame at 30 fps.

## Parametric hull demo

Build the new 131-second captioned walkthrough with:

```sh
.venv/bin/python scripts/make_walkthroughs.py --only hawa-hull-galapagos
```

The local video is `dist/videos-monad/hawa-hull-galapagos.mp4`. The renderer also creates its thumbnail and adds it to the local upload kit. See [the hull guide](../hull-optimization.md), [the recorded population](hull-search.json), and [the verification report](hull-verification.json).
