# Changelog

## 2.1.0 (2026-09-26)

Carousel mode. The summit design was carousel + video; this adds the carousel half.

- `CAROUSEL.md`: listing link in, 7 to 10 slide on-brand Instagram carousel out. Free.
- `listing_pull.py`: every photo at 2560px, the full listing text and the guest reviews,
  via a headless browser (a plain page fetch has no review text). Folder mode for photos.
- `brand_pull.py`: colours by painted area, fonts and transparent logo cut-outs from the
  host's own website.
- `carousel.py`: the v3 design (one house grade, cover/room/photo/split/diptych/list/last)
  plus a new review slide. Gates before rendering: facts, verbatim 5-star review quotes,
  voice, plan shape. Contrast measured on the painted pixels while rendering.
- `photo_fix.py`: optional Seedream 5.0 Pro polish with a side-by-side and a plain yes.
- Bundled SIL OFL fonts: Cormorant Garamond, Playfair Display, Montserrat, Inter.
- Video mode unchanged.

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
