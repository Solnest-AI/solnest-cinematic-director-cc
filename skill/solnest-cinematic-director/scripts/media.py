#!/usr/bin/env python3
"""Shared ffmpeg helpers for the Solnest Cinematic Director.

ffmpeg comes from the machine if it has one, otherwise from the imageio-ffmpeg package
that `uv run` installs for each video script (declared in the script header), so the host
never installs anything. ffprobe is optional: without it, video info is read from ffmpeg.
Output is ASCII only so a Windows console can never crash on it."""
import json
import re
import shutil
import subprocess
import sys

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}

INSTALL_HINT = ("Run this script with `uv run SCRIPTS/<script>.py` so its bundled ffmpeg "
                "(imageio-ffmpeg) is installed automatically, or run `uv run SCRIPTS/doctor.py --video`.")


class MediaError(RuntimeError):
    pass


def _bundled_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # not installed, or no binary for this platform
        return None


def tool(name):
    path = shutil.which(name)
    if path:
        return path
    if name == "ffmpeg":
        path = _bundled_ffmpeg()
        if path:
            return path
    raise MediaError(f"{name} not found. {INSTALL_HINT}")


def parse_ffmpeg_info(stderr):
    """{'w','h','secs'} from the banner `ffmpeg -i FILE` prints (used when there is no ffprobe)."""
    v = re.search(r"Stream #\S+.*?Video:.*?, (\d{2,5})x(\d{2,5})", stderr)
    if not v:
        raise MediaError("no picture stream found")
    d = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    secs = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    return {"w": int(v.group(1)), "h": int(v.group(2)), "secs": round(secs, 3)}


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").strip().splitlines()[-12:])
        raise MediaError(f"{cmd[0]} failed:\n{tail}")
    return r


def probe(path):
    """Return {'w','h','secs'} for an image or video."""
    if not shutil.which("ffprobe"):
        r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-i", str(path)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        try:
            return parse_ffmpeg_info(r.stderr or "")
        except MediaError:
            raise MediaError(f"no picture stream in {path}")
    r = run([tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-show_entries", "format=duration",
             "-of", "json", str(path)])
    d = json.loads(r.stdout)
    if not d.get("streams"):
        raise MediaError(f"no picture stream in {path}")
    s = d["streams"][0]
    secs = d.get("format", {}).get("duration")
    return {"w": int(s["width"]), "h": int(s["height"]),
            "secs": float(secs) if secs not in (None, "N/A") else 0.0}


def last_frame(video, out_jpg):
    """Extract the true final frame of a clip (used to seed the closing shot)."""
    run([tool("ffmpeg"), "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(out_jpg)])
    return out_jpg


if __name__ == "__main__":
    try:
        print("ffmpeg :", tool("ffmpeg"))
        print("ffprobe:", shutil.which("ffprobe") or "(not needed: read from ffmpeg)")
    except MediaError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
