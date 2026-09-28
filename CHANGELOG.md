# Changelog

## 2.1.5 (2026-09-28)

- A listing re-pull on Windows while a photo from the old pull is open (a viewer, File
  Explorer's preview) now stops with a plain message and keeps the old photos, instead of a
  traceback. Found in a final review pass.

## 2.1.4 (2026-09-28)

- KIE's own failures retry themselves. A clip KIE fails on its side ("Internal Error,
  Please try again later") is retried with a fresh task up to twice inside the same run;
  those failures are not billed (measured 2026-09-28 on Windows: 14 of 20 Veo tasks failed
  that way, 0 credits taken, the finished video cost exactly 7 x 65). Timeouts and download
  errors are still resumed on the next run, never retried with a new task.

## 2.1.3 (2026-09-28)

- A soft carousel cover is a note, not a stop. Typical Airbnb galleries score 37-53 against
  the crispness bar of 80, so the gate fired on nearly every first try. The check now prints
  the note, the slide renders (sharpened harder), and Claude offers the 7-cent photo fix
  after the host has seen the preview. `soft_ok` is still accepted and only silences the note.

## 2.1.2 (2026-09-28)

Money and silent-failure fixes from a Codex review of the whole skill.

- One paid Veo task per clip, ever. A failed poll or download is retried against the same
  task; a second task is only created when Claude asks for a redo with `--only`.
- `clips/_run.json` is saved after every clip with its KIE task id, so an interrupted run
  resumes: finished clips are kept, a created-but-unfinished task is polled again, and only
  what is missing is generated. A clip is regenerated when its photo, prompt, length or
  shape changed (fingerprint per clip); `assemble.py` refuses clips that no longer match
  `plan.json`.
- Every KIE download lands in a `.part` file and must be real media of the right size and
  kind before it replaces anything (no more HTML error pages saved as clips or photos).
- `credits()` and `extract_urls()` tolerate KIE's other answer shapes instead of crashing.
- `assemble.py` no longer ships a shorter video when the closing shot failed; `--without-ending`
  says so on purpose.
- Listing pulls download into a staging folder and swap it in, so a rerun never keeps an
  earlier listing's photos; `photos.py` clears numbered files the same way.
- `listing_pull.py` accepts older Airbnb photo URLs (no `Hosting-<id>`) with a warning,
  the way `photos.py` already did.
- Docs: no literal `[--option]` brackets in commands, a PowerShell form for `"$UV" run`,
  the Mac install line wrapped in `bash -o pipefail` so a failed download cannot exit 0,
  and the video preflight only needs the video lines green.

## 2.1.1 (2026-09-28)

Summit Day 1 polish, all verified on Mac and Windows.

- Setup ends on a green check ("STR Secrets Content Studio is set up"), then asks for an
  Airbnb link and "a carousel or a video?" and makes it in the same chat. No quit and
  reopen in the middle. The offer only comes once the KIE key is in.
- Windows: uv's Python stays under the profile (UV_PYTHON_INSTALL_DIR), never in the
  AppData folder the desktop app redirects. Same fix as the connections kit.
- ffmpeg from the summit prep (~/.local/bin) is found on Windows too, so nothing is
  downloaded twice.
- crop.py creates its output folder; carousel labels always fit on one line (or the slide
  fails); covers must be crisp; every photo gets adaptive output sharpening.

## 2.1.0 (2026-09-28)

Windows-ready, zero-terminal install for the STR Secrets summit Content Studio.

- Carousel mode (CAROUSEL.md): a listing link becomes an on-brand 8 or 9 slide Instagram
  carousel, free. `listing_pull.py` pulls every photo, the listing text and the guest
  reviews; `brand_pull.py` reads the host's colours, fonts and logo off their site;
  `carousel.py` renders 1080x1350 slides and refuses to render copy it cannot back: every
  word and number must come from the listing, the review slide must quote a real 5-star
  review verbatim, and every text line must pass a 4.5:1 contrast check measured on the
  photo behind it. The closing line comes from each host's own `brand.json`.
  `photo_fix.py` (optional, about 14 credits a photo) straightens and relights photos
  without adding anything.
- The carousel scripts run through uv (PEP 723 headers pin Playwright and Pillow), so
  nothing is installed into the system Python. `setup.py` installs uv if it is missing,
  writes the `bin/uv` and `bin/uv.cmd` launchers, and runs `doctor.py` to fetch the
  headless browser once. A `carousels` row joins the checklist; a failure there never
  blocks videos.
- README.md opens with the steps for Claude, so pasting the repo link into Claude Code
  and saying "set this up" is enough.

- One-line install pasted into Claude Code (INSTALL.md). `install.ps1` / `install.sh`
  copy the skill into `~/.claude/skills/`, find a Python 3.9+ or install one through uv
  (the same way the STR Secrets Connections kit does), then run `setup.py`. Re-run to update.
- `setup.py`: checks and fixes everything without asking. ffmpeg and ffprobe are reused
  if the machine has them, else downloaded into the skill's own `bin/` (three mirrors per
  platform, Apple Silicon and Intel, no admin, no PATH edits). Writes the `bin/py`
  launcher (and `bin/py.cmd` for PowerShell). Reuses the KIE key from the Connections kit
  (`~/.claude.json` pointer or the kit folder), else creates and opens a blank `.env`.
  Checks the balance against the 455 credits one video needs.
- `photos.py` replaces the curl/grep/awk photo pull: identical on Windows and Mac,
  follows Airbnb's country redirect, keeps only this listing's photos, checks every
  download for real image bytes, numbered thumbnails plus originals on demand, and
  `--from-urls` for the Firecrawl fallback.
- `sheet.py` expands globs and folders itself (PowerShell never expands `*`) and pulls a
  frame from each clip for the step 6 check, so the shell loop is gone.
- ffmpeg lookup: the skill's `bin/` first, then PATH, then the Homebrew, winget,
  chocolatey and scoop folders the desktop app's PATH tends to miss.
- Redoing the final beat now redoes the closing shot automatically (it is seeded from
  that beat's last frame).
- One failing beat no longer takes the whole `make_clips.py` run down, and KIE network
  errors come back as plain messages instead of tracebacks.
- SKILL.md never types `python3` again: every command runs through the launcher, with a
  PowerShell form for Windows machines without Git Bash.

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
