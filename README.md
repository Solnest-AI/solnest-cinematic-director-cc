# Solnest Cinematic Director (Claude Code edition)

Paste a listing link. Get back a 25 to 30 second cinematic walkthrough video of the
property, ready for Instagram or to send to an owner.

About **$2 per video** in KIE credits. No subscription, no Descript, no watermark. The
clips are generated on KIE (Veo 3.1) and stitched on your own machine with ffmpeg.

Built by Ryan Lefebvre / **Solnest AI**. Free to use.

---

## Install (2 minutes, nothing to type in a terminal)

You need the [Claude Code](https://claude.com/claude-code) desktop app. Open it and
paste this:

> Install the Solnest Content Studio. Follow the instructions at https://raw.githubusercontent.com/Solnest-AI/solnest-cinematic-director-cc/main/INSTALL.md exactly.

Claude runs one installer for your computer (Mac or Windows). It puts the skill in
`~/.claude/skills/`, finds or installs Python, downloads ffmpeg into the skill's own
folder when your machine has none (no admin rights, nothing added to your PATH), picks up
your KIE key from the STR Secrets Connections kit if you ran it, checks your balance, and
prints a checklist. Then you restart Claude Code. Re-run the same line any time to update.

### What you need

| Thing | What it does | Cost |
|---|---|---|
| **KIE API key** ([kie.ai](https://kie.ai/api-key)) | Generates the video clips | Pay as you go, $5 minimum, about $2 per video |
| **ffmpeg** | Joins the clips on your machine | Free. Downloaded for you |
| **Python 3.9+** | Runs the helper scripts (no packages) | Free. Found or installed for you |
| Firecrawl MCP (optional) | Reads non-Airbnb listing pages | Free plan is fine |

Your KIE key lives in a file called `.env` inside the skill folder, one line:
`KIE_API_KEY=your_key`. If you set up the STR Secrets Connections kit, the installer
copies it from there. **Never paste a key into the chat.**

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

## How the install works (for the curious)

- `install.ps1` (Windows) and `install.sh` (Mac/Linux) copy `skill/solnest-cinematic-director`
  into `~/.claude/skills/`, find a Python 3.9+ (a real one, never the Microsoft Store stub;
  on a Mac never the Xcode stub), or install one through [uv](https://astral.sh/uv), then
  hand over to `scripts/setup.py`.
- `setup.py` reuses ffmpeg if the machine has it, otherwise downloads it into the skill's
  `bin/` folder from the first mirror that works (gyan.dev, BtbN and ffmpeg-static on
  GitHub for Windows; ffmpeg-static on GitHub and martin-riedl.de for Mac, Apple Silicon
  and Intel). It writes a launcher, `bin/py`, so every command in the skill runs through
  the same Python on every machine. It looks for the KIE key in the skill's `.env`, in the
  environment, and in the STR Secrets Connections kit (through the `kie` server registered
  in `~/.claude.json`, or the kit folder on the Desktop, Documents or Downloads), and copies
  it into the skill's `.env`. Then it checks the balance: 455 credits is one video.
- Nothing is installed system-wide and nothing needs admin rights.

## Update

Paste the install line again. It replaces the scripts and keeps your `.env` and ffmpeg.

## For developers

```bash
python3 -m unittest discover -s tests -v      # offline: no network, no credits
./install.sh                                  # install from this clone (Windows: .\install.ps1)
```

The scripts are Python standard library plus ffmpeg, and print ASCII only so they cannot
crash a Windows console.

---

*Free from **Solnest AI**. We help business owners put AI to work so they can work on the
business, not in it. [solnestai.com](https://solnestai.com) |
IG [@Ryan_Le5](https://instagram.com/Ryan_Le5) + [@SolnestAi](https://instagram.com/SolnestAi)*
