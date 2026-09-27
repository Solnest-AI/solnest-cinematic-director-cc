#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["playwright==1.60.0", "pillow>=10", "imageio-ffmpeg>=0.5"]
# ///
"""Check everything this skill needs and fix what can be fixed without the host.

The host never runs a command. Claude runs this once at the start of a session:
  uv run SCRIPTS/doctor.py            carousels: Python packages, headless browser, fonts
  uv run SCRIPTS/doctor.py --video    also ffmpeg, the KIE key and the KIE balance

`uv run` installs the Python packages from the header above on first use. This script
then installs the headless browser if it is missing (about 200 MB, one time, no admin).

Every line starts with [ok], [fixed], [needs you] or [failed].
Exit 0 = ready, 1 = the host has to do one thing (only ever: paste their KIE key into the
file this script created), 2 = something could not be fixed (the line says what).
Output is ASCII only so a Windows console can never crash on it.
"""
import argparse
import pathlib
import sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
VIDEO_MIN_CREDITS = 455  # 6 beats + closing shot


def say(tag, msg):
    print(f"[{tag}] {msg}".encode("ascii", "replace").decode("ascii"), flush=True)


def check_carousel():
    ok = True
    say("ok", f"Python {sys.version.split()[0]}")
    try:
        import PIL
        say("ok", f"Pillow {PIL.__version__}")
    except ImportError:
        say("failed", "Pillow is missing: run this with `uv run SCRIPTS/doctor.py`, not plain python")
        return False
    try:
        import importlib.metadata as md
        from playwright.sync_api import sync_playwright
        say("ok", f"Playwright {md.version('playwright')}")
    except ImportError:
        say("failed", "Playwright is missing: run this with `uv run SCRIPTS/doctor.py`, not plain python")
        return False
    try:
        import browser
        with sync_playwright() as pw:
            b = browser.launch(pw)
            b.close()
        say("ok", "headless browser starts")
    except Exception as e:
        say("failed", f"headless browser: {str(e).splitlines()[0][:200]}")
        ok = False
    try:
        from carousel import FONT_DIR, FONTS
        missing = [f for spec in FONTS.values() for k in ("roman", "italic") if (f := spec.get(k))
                   and not (FONT_DIR / f).exists()]
        if missing:
            say("failed", f"fonts missing from {FONT_DIR}: {missing} (re-copy the skill folder)")
            ok = False
        else:
            say("ok", "bundled fonts")
    except Exception as e:
        say("failed", f"carousel builder would not load: {e}")
        ok = False
    return ok


def check_video():
    import kie
    import media
    status = 0
    try:
        path = media.tool("ffmpeg")
        say("ok", f"ffmpeg ({'bundled' if 'imageio_ffmpeg' in path else 'installed on this machine'})")
    except media.MediaError as e:
        say("failed", str(e))
        status = 2
    try:
        _, where = kie.find_key()
        say("ok", f"KIE key found ({where})")
    except kie.KieError:
        env = SKILL_DIR / ".env"
        if not env.exists():
            env.write_text("# Paste your KIE key after the = sign (from https://kie.ai/api-key), then save.\n"
                           "KIE_API_KEY=\n", encoding="utf-8")
        say("needs you", f"no KIE key yet. Open this file for the host and have them paste their key "
                         f"after KIE_API_KEY= and save: {env}")
        return max(status, 1)
    try:
        bal = kie.credits()
        if bal < VIDEO_MIN_CREDITS:
            say("needs you", f"KIE balance {bal:.0f} credits; a full video needs {VIDEO_MIN_CREDITS}. "
                             "The host tops up at https://kie.ai (billing).")
            return max(status, 1)
        say("ok", f"KIE balance {bal:.0f} credits (about {int(bal // 65)} clips)")
    except kie.KieError as e:
        say("failed", f"KIE key did not work: {e}")
        return 2
    return status


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", action="store_true", help="also check ffmpeg, the KIE key and balance")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    status = 0 if check_carousel() else 2
    if a.video:
        status = max(status, check_video())
    say("ok" if status == 0 else ("needs you" if status == 1 else "failed"),
        {0: "READY", 1: "one thing needs the host (above)", 2: "not ready (see [failed] lines)"}[status])
    return status


if __name__ == "__main__":
    sys.exit(main())
