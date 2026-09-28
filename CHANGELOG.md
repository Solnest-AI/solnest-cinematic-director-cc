# Changelog

## 2.1.0 (2026-09-28)

Windows-ready, zero-terminal install for the STR Secrets summit Content Studio.

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
