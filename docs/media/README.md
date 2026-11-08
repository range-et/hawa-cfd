# Videos

The videos use captions and screenshots from the verified Rhino sessions. They have no audio. The edits use Monad colors and Helvetica titles.

The slides contain no added header bars or title rules. The captured Rhino interface retains its original colors.

| Video | Duration | Download | Upload text |
| --- | --- | --- | --- |
| Hawa overview | 0:57 | [MP4](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/hawa-first-look.mp4) | [Title and description](youtube-first-look.txt) |
| 3D block flow | 1:08 | [MP4](https://github.com/range-et/hawa-cfd/releases/download/v0.2.0/hawa-block-workflow.mp4) | [Title and description](youtube-block-workflow.txt) |

## Upload to YouTube

1. Select the new MP4 in YouTube Studio.
2. Copy its title from the supplied text file.
3. Copy its description from that file.
4. Select Public for visibility.
5. Publish the video.
6. Send the video link to this chat.

The website can show the release videos now. Add each YouTube ID to `site/videos.json` to replace its player with a YouTube embed.

## Recreate the files

Run `scripts/make_walkthroughs.py` on macOS. The script needs Pillow, ffmpeg, ffprobe, Helvetica Neue, and Menlo.

It reads the pinned palette from `vendor/monad_system/colors.json`. It writes the MP4 files to ignored `dist/videos-monad/`.

`walkthroughs.json` records the captions, chapter times, durations, and Monad revision. The H.264 files use a 1920 × 1080 frame at 30 fps.
