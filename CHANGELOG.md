# Changelog

## 2.0.0 (2026-09-25)

Rebuilt on the recipe measured in the Sep 20-21 test runs (Langley farm, Sun Peaks cabin).

- Engine is now KIE Veo 3.1 (pay as you go, about $2 per video). Higgsfield is no longer used.
- One anchor per clip. Start and end frames made every model dissolve and invent the gap.
- Closing shot seeded from the final clip's real last frame, joined with a hard cut.
- Beats joined with free 0.6s ffmpeg crossfades. Generated bridge clips removed.
- Photos are checked by eye on a contact sheet. Scraped room labels are not trusted.
- Every photo is cropped on purpose (crop.py). No blind centre crops.
- Full Airbnb gallery pulled from the listing page (the JSON scrape only returned 5 photos).
- New scripts: kie.py, make_clips.py (dry run, cost check, parallel, --only redo),
  assemble.py (exact timeline, refuses a wrong-length render), crop.py, sheet.py, media.py.
- Python standard library plus ffmpeg only. ASCII-only output so Windows consoles cannot crash.
- stitch.sh removed (assemble.py replaces it).

## 1.x

Claude Code edition of the Desktop/Descript skill: Higgsfield Kling clips, chained with
start and end frames, stitched with stitch.sh.
