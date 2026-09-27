#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["imageio-ffmpeg>=0.5", "pillow>=10"]
# ///
"""Look at every clip before assembling: the start, middle and end frame of each clip in
one row, three clips per sheet. Warping and invented rooms show up late in a camera move,
so the end frame matters most.

Usage:
  uv run SCRIPTS/clipcheck.py clips
Writes clips/_check_1.jpg, clips/_check_2.jpg, ... and prints their paths. LOOK at them.
"""
import argparse
import pathlib
import sys
import tempfile

from PIL import Image, ImageDraw

from media import MediaError, probe, run, tool

TW, TH = 240, 427


def frames(clip, tmp):
    secs = probe(clip)["secs"] or 6.0
    out = []
    for k, t in enumerate((0.3, secs / 2, max(0.0, secs - 0.3))):
        f = tmp / f"{clip.stem}_{k}.jpg"
        run([tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(clip),
             "-frames:v", "1", "-q:v", "3", str(f)])
        out.append(f)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clips_dir")
    a = ap.parse_args(argv)
    d = pathlib.Path(a.clips_dir)
    clips = sorted(p for p in d.glob("*.mp4"))
    if not clips:
        print(f"ERROR: no .mp4 clips in {d}")
        return 1
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        rows = [(c.stem, frames(c, tmp)) for c in clips]
    except MediaError as e:
        print(f"ERROR: {e}")
        return 1
    written = []
    for n in range(0, len(rows), 3):
        group = rows[n:n + 3]
        sheet = Image.new("RGB", (3 * TW + 20, len(group) * (TH + 30)), "white")
        draw = ImageDraw.Draw(sheet)
        for r, (name, fs) in enumerate(group):
            y = r * (TH + 30)
            draw.text((6, y + 8), f"{name}   start / middle / end", fill="black")
            for c, f in enumerate(fs):
                im = Image.open(f).convert("RGB")
                im.thumbnail((TW, TH))
                sheet.paste(im, (c * (TW + 10), y + 28))
        path = d / f"_check_{n // 3 + 1}.jpg"
        sheet.save(path, quality=85)
        written.append(path)
    for p in written:
        print(f"OK  {p}")
    print("LOOK at each sheet: warped walls, melting furniture or an invented room means redo that beat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
