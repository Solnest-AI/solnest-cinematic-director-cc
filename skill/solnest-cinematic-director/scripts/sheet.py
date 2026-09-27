#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["imageio-ffmpeg>=0.5"]
# ///
"""Contact sheet: many photos in one image, so you can see every room at once.

Scraped room labels are unreliable (on one test listing EVERY label was wrong). Look
at the pictures. Tiles are laid out left to right, top to bottom, in the order given;
the script prints the tile number for each file.

Usage:
  python3 sheet.py OUT.jpg photo1.jpg photo2.jpg ... [--cols 4] [--tile 480]
"""
import argparse
import sys

from media import MediaError, run, tool


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("photos", nargs="+")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--tile", type=int, default=480, help="tile width in pixels")
    a = ap.parse_args(argv)

    n = len(a.photos)
    cols = max(1, min(a.cols, n))
    tw, th = a.tile, a.tile * 2 // 3
    cmd = [tool("ffmpeg"), "-y", "-v", "error"]
    for p in a.photos:
        cmd += ["-i", p]
    parts = []
    for i in range(n):
        parts.append(f"[{i}:v]scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                     f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[t{i}]")
    if n == 1:
        graph = parts[0].replace("[t0]", "[out]")
    else:
        layout = "|".join(f"{(i % cols) * tw}_{(i // cols) * th}" for i in range(n))
        inputs = "".join(f"[t{i}]" for i in range(n))
        graph = ";".join(parts) + f";{inputs}xstack=inputs={n}:layout={layout}:fill=black[out]"
    cmd += ["-filter_complex", graph, "-map", "[out]", "-frames:v", "1", "-q:v", "3", a.out]
    try:
        run(cmd)
    except MediaError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"OK  {a.out}  ({n} tiles, {cols} per row)")
    for i, p in enumerate(a.photos, 1):
        print(f"  tile {i:2d}: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
