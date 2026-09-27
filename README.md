# Solnest Cinematic Director (Claude Code edition)

Paste a listing link. Get back either:

- a **25 to 30 second cinematic walkthrough video** of the property, ready for Instagram
  or to send to an owner (about **$2** in KIE credits, generated on KIE Veo 3.1 and
  stitched on your own machine with ffmpeg), or
- an **on-brand Instagram carousel**: 7 to 10 slides built from the listing's real photos,
  in your own colours, fonts and logo (read from your website), with a real 5-star guest
  review and every claim checked against your listing. **Free**, nothing is generated.

No subscription, no Descript, no watermark.

Built by Ryan Lefebvre / **Solnest AI**. Free to use.

---

## Install (about 5 minutes)

You need [Claude Code](https://claude.com/claude-code). Open it and paste this:

> Install the Solnest Cinematic Director from https://github.com/Solnest-AI/solnest-cinematic-director-cc. Follow the "Claude: install steps" section of its README exactly.

Claude does the rest and tells you if anything is missing.

### What you need

| Thing | What it does | Cost |
|---|---|---|
| **Claude Code** (desktop app is fine) | Does every step for you, including the setup | Paid Claude plan |
| **uv** | Runs the skill's Python tools; Claude installs it if it is missing | Free |
| **KIE API key** ([kie.ai](https://kie.ai/api-key)), videos only | Generates the video clips | Pay as you go, $5 minimum, about $2 per video |
| Firecrawl MCP (optional) | Reads non-Airbnb listing pages for videos | Free plan is fine |

You never type a command. Claude installs what the skill needs the first time (about 200 MB,
most of it the headless browser that reads listings, plus a bundled ffmpeg for videos).

Your KIE key goes in a file called `.env` inside the skill folder, one line:
`KIE_API_KEY=your_key`. **Never paste a key into the chat.**

---

## Use it

```
make me a Solnest video for https://www.airbnb.com/rooms/...
```

It asks what the video is for (Instagram = vertical 9:16, owner or website = 16:9), then:

1. pulls every photo from the listing,
2. looks at them and picks 5 or 6 beats (it does not trust the listing's room labels),
3. crops each photo on purpose,
4. writes one prompt per beat describing the real room plus one slow camera move,
5. shows you the cost, then generates the clips in parallel (2 to 3 minutes),
6. adds a closing shot that continues the last clip seamlessly,
7. stitches everything into one MP4 in `listing-walkthroughs/<property>/final/`.

### Carousels

```
make me a carousel for https://www.airbnb.com/rooms/...
```

It asks for your website and what the last slide should say, then:

1. pulls every photo at full size, the listing text and the guest reviews (no API key),
2. reads your colours, fonts and logo from your website,
3. looks at the photos and plans 8 or 9 slides: cover, the thing that sets you apart,
   amenities, details, bedrooms, a real guest quote, location, and a closing slide,
4. checks every word against your listing and every quote against the real review
   before rendering anything,
5. renders the slides, measuring text contrast on the actual pixels,
6. shows you a preview and the caption. Say yes, or tell it what to change.

Your photos are never AI-edited unless you ask. If you do, it uses the one editor that
added nothing in testing (Seedream 5.0 Pro, about $0.07 a photo), shows you the before
and after, and waits for your yes.

## The recipe, and why

Every rule came from a failed test first.

- **One anchor per clip.** Give an AI video model a start AND an end photo and it
  dissolves into the end photo and invents what is in between. We saw it on Veo, Kling
  and PixVerse. One start frame per clip, always.
- **Describe the real room.** Motion-only prompts let the model repaint the space.
- **One slow camera move toward something in the frame.** More moves is where walls
  start to bend.
- **Plain crossfades between beats.** Generated "transition" clips lost to a free 0.6
  second crossfade every time.
- **Look at the photos.** On one farm listing the scraped room labels were all wrong.
- **Veo 3.1 on KIE.** $0.325 flat per clip, 1080p, and 28% cheaper than Kling for the
  same shots.

## What it costs

| Video | Credits | Dollars |
|---|---|---|
| 6 beats + closing shot (30s) | 455 | about $2.28 |
| 5 beats + closing shot (26s) | 390 | about $1.95 |
| Redo one bad beat | 65 | $0.33 |

Both shapes (vertical and wide) means two runs. The framing is baked into each clip.

## Music

None ships with it. A music track in a public repo is a licensing call that belongs to
you. Add your own licensed track with `--music`, or post the silent cut and pick a sound
in Instagram. Details in
[assets/README-music.md](skill/solnest-cinematic-director/assets/README-music.md).

---

## Claude: install steps

The user will not run commands. You run every step with your Bash tool (Git Bash on
Windows). Stop and tell the user plainly, in one sentence, if a step fails.

1. **uv.** Check `uv --version`. If it is missing, install it yourself: macOS/Linux
   `curl -LsSf https://astral.sh/uv/install.sh | sh`; Windows
   `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
   It is not on PATH until the app restarts, so call it by the full path the installer
   prints (usually `~/.local/bin/uv`).
2. **Clone** this repo somewhere permanent, for example `~/solnest-cinematic-director-cc`.
3. **Put the skill where Claude Code finds it.**
   - macOS / Linux: run `./install.sh` from the repo folder (it symlinks
     `skill/solnest-cinematic-director` into `~/.claude/skills/`, then runs the doctor).
   - Windows: copy the folder `skill/solnest-cinematic-director` to
     `~/.claude/skills/solnest-cinematic-director` (copy, not a symlink).
4. **Run the doctor:** `uv run <skills folder>/solnest-cinematic-director/scripts/doctor.py --video`.
   It installs the Python packages, a bundled ffmpeg and the headless browser by itself,
   then checks the KIE key and balance. It must end with `READY` (videos need 455 credits).
5. **KIE key, only if the doctor says `[needs you]`.** It has created
   `<skills folder>/solnest-cinematic-director/.env`. Open it for the user (macOS
   `open -e "<path>"`, Windows `notepad "$(cygpath -w "<path>")"`), ask them to paste their
   key after `KIE_API_KEY=` and save, then run the doctor again. Never ask for the key in
   chat. Never print it. If they used the STR Secrets Connections kit, the doctor already
   finds the key the kit saved.
6. Tell the user to **restart Claude Code**, then say
   `make me a Solnest video for <listing url>` or `make me a carousel for <listing url>`.

## Update

`git pull` in the repo folder (macOS/Linux, symlinked). On Windows, pull, then copy the
skill folder over the installed one again. Your `.env` is not in the repo, so re-copy it
if you replaced the folder.

## For developers

```bash
uv run --with pillow python -m unittest discover -s tests -v
```

Offline tests, no network and no credits. The video scripts are Python standard library
plus ffmpeg; the carousel scripts add Playwright and Pillow (their tests skip without
Pillow). Everything prints ASCII only so it cannot crash a Windows console.

---

*Free from **Solnest AI**. We help business owners put AI to work so they can work on the
business, not in it. [solnestai.com](https://solnestai.com) |
IG [@Ryan_Le5](https://instagram.com/Ryan_Le5) + [@SolnestAi](https://instagram.com/SolnestAi)*
