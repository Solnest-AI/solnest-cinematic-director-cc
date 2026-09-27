"""The host never runs a command: every script runs through `uv run` with its own declared
dependencies, ffmpeg comes bundled when the machine has none, the headless browser installs
itself, and the KIE key is found where the STR Secrets Connections kit saved it.
Offline tests: no network, no browser, no credits.
Run:  python3 -m unittest discover -s tests -v
"""
import json
import pathlib
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill" / "solnest-cinematic-director"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kie  # noqa: E402
import media  # noqa: E402

FFMPEG_VIDEO = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clips/01_exterior.mp4':
  Duration: 00:00:06.04, start: 0.000000, bitrate: 30275 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1080x1920 [SAR 1:1 DAR 9:16], 30000 kb/s, 24 fps
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 192 kb/s
At least one output file must be specified"""
FFMPEG_IMAGE = """Input #0, image2, from 'source/31.jpg':
  Duration: 00:00:00.04, start: 0.000000, bitrate: 186113 kb/s
  Stream #0:0: Video: mjpeg (Baseline), yuvj420p(pc, bt470bg/unknown/unknown), 2560x1708 [SAR 1:1 DAR 640:427], 25 tbr, 25 tbn
At least one output file must be specified"""


class BundledFfmpeg(unittest.TestCase):
    def test_parse_video_info_without_ffprobe(self):
        self.assertEqual(media.parse_ffmpeg_info(FFMPEG_VIDEO), {"w": 1080, "h": 1920, "secs": 6.04})

    def test_parse_image_info_without_ffprobe(self):
        info = media.parse_ffmpeg_info(FFMPEG_IMAGE)
        self.assertEqual((info["w"], info["h"]), (2560, 1708))

    def test_no_picture_stream_is_an_error(self):
        with self.assertRaises(media.MediaError):
            media.parse_ffmpeg_info("Input #0, wav\n  Duration: 00:00:03.00\n  Stream #0:0: Audio: pcm_s16le")

    def test_ffmpeg_falls_back_to_the_bundled_binary(self):
        fake = types.ModuleType("imageio_ffmpeg")
        fake.get_ffmpeg_exe = lambda: "/bundled/ffmpeg"
        with mock.patch.object(media.shutil, "which", return_value=None), \
                mock.patch.dict(sys.modules, {"imageio_ffmpeg": fake}):
            self.assertEqual(media.tool("ffmpeg"), "/bundled/ffmpeg")

    def test_missing_everything_says_what_to_run(self):
        with mock.patch.object(media.shutil, "which", return_value=None), \
                mock.patch.dict(sys.modules, {"imageio_ffmpeg": None}):
            with self.assertRaises(media.MediaError) as cm:
                media.tool("ffmpeg")
        self.assertIn("uv run", str(cm.exception))


class KieKeyFromTheKit(unittest.TestCase):
    def home(self, cfg, env_text=None):
        h = pathlib.Path(tempfile.mkdtemp())
        if env_text is not None:
            (h / "kit").mkdir()
            (h / "kit" / ".env").write_text(env_text, encoding="utf-8")
        (h / ".claude.json").write_text(json.dumps(cfg), encoding="utf-8")
        return h

    def test_key_found_through_the_kie_mcp_env_path(self):
        h = self.home({}, "KIE_API_KEY=kie_from_kit\n")
        cfg = {"mcpServers": {"kie": {"env": {"KIE_ENV_PATH": str(h / "kit" / ".env")}}}}
        (h / ".claude.json").write_text(json.dumps(cfg), encoding="utf-8")
        with mock.patch.dict(kie.os.environ, {}, clear=True), \
                mock.patch.object(kie, "key_search_paths", return_value=[]), \
                mock.patch.object(kie.pathlib.Path, "home", return_value=h):
            key, where = kie.find_key()
        self.assertEqual(key, "kie_from_kit")
        self.assertIn(".env", where)

    def test_key_found_inline_in_a_project_scoped_server(self):
        h = self.home({"projects": {"/x": {"mcpServers": {"kie": {"env": {"KIE_API_KEY": "kie_inline"}}}}}})
        with mock.patch.dict(kie.os.environ, {}, clear=True), \
                mock.patch.object(kie, "key_search_paths", return_value=[]), \
                mock.patch.object(kie.pathlib.Path, "home", return_value=h):
            self.assertEqual(kie.find_key()[0], "kie_inline")

    def test_broken_claude_json_is_not_a_crash(self):
        h = pathlib.Path(tempfile.mkdtemp())
        (h / ".claude.json").write_text("{not json", encoding="utf-8")
        with mock.patch.dict(kie.os.environ, {}, clear=True), \
                mock.patch.object(kie, "key_search_paths", return_value=[]), \
                mock.patch.object(kie.pathlib.Path, "home", return_value=h):
            with self.assertRaises(kie.KieError):
                kie.find_key()


class SelfInstallingBrowser(unittest.TestCase):
    def test_missing_chromium_is_installed_then_launched_once(self):
        try:
            import browser
        except ImportError:  # pragma: no cover
            self.fail("scripts/browser.py is missing")
        calls = {"n": 0}

        class Chromium:
            def launch(self):
                calls["n"] += 1
                if calls["n"] == 1:
                    raise RuntimeError("BrowserType.launch: Executable doesn't exist at /x/chrome")
                return "browser"
        pw = types.SimpleNamespace(chromium=Chromium())
        ok = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch.object(browser.subprocess, "run", return_value=ok) as run:
            self.assertEqual(browser.launch(pw), "browser")
        self.assertIn("install", run.call_args[0][0])
        self.assertEqual(calls["n"], 2)

    def test_other_launch_errors_are_not_hidden(self):
        import browser

        class Chromium:
            def launch(self):
                raise RuntimeError("some other failure")
        with self.assertRaises(RuntimeError):
            browser.launch(types.SimpleNamespace(chromium=Chromium()))


class DocsNeverAskTheHostToRunCommands(unittest.TestCase):
    DOCS = [SKILL / "SKILL.md", SKILL / "CAROUSEL.md"]

    def test_scripts_are_run_with_uv(self):
        for d in self.DOCS:
            text = d.read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"python3? SCRIPTS/\S+", text), [], d.name)
            self.assertIn("uv run SCRIPTS/doctor.py", text, d.name)

    def test_entry_scripts_declare_their_dependencies(self):
        pins = set()
        for name in ("carousel.py", "listing_pull.py", "brand_pull.py", "doctor.py"):
            head = (SCRIPTS / name).read_text(encoding="utf-8")[:1200]
            self.assertIn("# /// script", head, name)
            pins |= set(re.findall(r'"playwright==([\d.]+)"', head))
        self.assertEqual(len(pins), 1, f"all scripts must pin the same Playwright: {pins}")
        for name in ("crop.py", "sheet.py", "assemble.py", "make_clips.py", "clipcheck.py"):
            head = (SCRIPTS / name).read_text(encoding="utf-8")[:1200]
            self.assertIn("imageio-ffmpeg", head, name)


if __name__ == "__main__":
    unittest.main()
