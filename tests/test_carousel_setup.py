"""Offline tests for the carousel half of setup (uv, launchers, doctor) and the docs that
drive it. No network, no uv, no browser: subprocess is mocked.
Run:  python3 -m unittest discover -s tests -v
"""
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skill" / "solnest-cinematic-director"
SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SCRIPTS))

import browser  # noqa: E402
import setup  # noqa: E402


def done(rc=0, out="", err=""):
    return subprocess.CompletedProcess([], rc, out, err)


class UvLaunchers(unittest.TestCase):
    def test_sh_and_cmd_launchers_point_at_uv(self):
        with tempfile.TemporaryDirectory() as t, mock.patch.object(setup, "BIN_DIR", pathlib.Path(t)):
            uv = pathlib.Path(t) / "tools" / "uv"
            setup.write_uv_launchers(uv)
            sh = (pathlib.Path(t) / "uv").read_bytes()
            cmd = (pathlib.Path(t) / "uv.cmd").read_bytes()
        self.assertTrue(sh.startswith(b"#!/bin/sh\n"))
        self.assertNotIn(b"\r\n", sh)  # Git Bash chokes on CRLF in a shebang script
        self.assertIn(f'U="{uv.as_posix()}"'.encode(), sh)
        self.assertIn(b"\r\n", cmd)
        self.assertIn(f'set "U={uv}"'.encode(), cmd)
        self.assertNotIn(b"\\\\", cmd)  # the Python escapes rendered as single backslashes

    def test_sh_launcher_is_executable(self):
        if os.name == "nt":
            self.skipTest("no exec bit on Windows")
        with tempfile.TemporaryDirectory() as t, mock.patch.object(setup, "BIN_DIR", pathlib.Path(t)):
            sh = setup.write_uv_launchers(pathlib.Path("/opt/uv"))
            self.assertTrue(os.access(sh, os.X_OK))


class EnsureCarousel(unittest.TestCase):
    def run_it(self, uv="/fake/uv", installed=None, result=None, offline=False, raises=None):
        calls = []

        def fake_run(cmd, **kw):
            if cmd[0] == "xattr":  # make_executable clears the Mac quarantine flag
                return done(0)
            calls.append(cmd)
            if raises:
                raise raises
            return result or done(0, "[ok] READY\n")

        with tempfile.TemporaryDirectory() as t, \
                mock.patch.object(setup, "BIN_DIR", pathlib.Path(t)), \
                mock.patch.object(setup, "find_uv", return_value=pathlib.Path(uv) if uv else None), \
                mock.patch.object(setup, "install_uv", return_value=installed) as inst, \
                mock.patch.object(setup.subprocess, "run", side_effect=fake_run):
            ok, text = setup.ensure_carousel(offline=offline)
            wrote = (pathlib.Path(t) / "uv").exists()
        return ok, text, calls, inst, wrote

    def test_ready(self):
        ok, text, calls, inst, wrote = self.run_it()
        self.assertTrue(ok)
        self.assertIn("headless browser", text)
        inst.assert_not_called()
        self.assertTrue(wrote)
        self.assertEqual(calls[0][1], "run")
        self.assertTrue(calls[0][2].endswith("doctor.py"))

    def test_installs_uv_when_missing(self):
        ok, _, _, inst, wrote = self.run_it(uv=None, installed=pathlib.Path("/home/x/.local/bin/uv"))
        self.assertTrue(ok)
        inst.assert_called_once()
        self.assertTrue(wrote)

    def test_uv_cannot_be_installed(self):
        ok, text, calls, _, wrote = self.run_it(uv=None, installed=None)
        self.assertFalse(ok)
        self.assertIn("uv could not be installed", text)
        self.assertEqual(calls, [])
        self.assertFalse(wrote)

    def test_offline_skips_the_browser_and_never_installs(self):
        ok, text, calls, inst, _ = self.run_it(uv=None, offline=True)
        self.assertFalse(ok)
        inst.assert_not_called()
        ok, text, calls, inst, _ = self.run_it(offline=True)
        self.assertTrue(ok)
        self.assertIn("offline", text)
        self.assertEqual(calls, [])

    def test_doctor_failure_reports_the_first_failed_line(self):
        out = "[ok] Python 3.13\n[failed] headless browser: net::ERR_NAME_NOT_RESOLVED\n[failed] not ready\n"
        ok, text, *_ = self.run_it(result=done(2, out))
        self.assertFalse(ok)
        self.assertTrue(text.startswith("headless browser: net::ERR_NAME_NOT_RESOLVED"))
        self.assertIn("run this setup again", text)

    def test_doctor_crash_without_failed_lines_reports_the_last_line(self):
        ok, text, *_ = self.run_it(result=done(1, "", "Traceback...\nerror: Failed to download playwright\n"))
        self.assertFalse(ok)
        self.assertIn("Failed to download playwright", text)

    def test_timeout_is_a_plain_message(self):
        ok, text, *_ = self.run_it(raises=subprocess.TimeoutExpired("uv", 1200))
        self.assertFalse(ok)
        self.assertIn("TimeoutExpired", text)


class BrowserSelfHeal(unittest.TestCase):
    def test_installs_the_headless_shell_once_then_launches(self):
        pw = mock.Mock()
        pw.chromium.launch.side_effect = [Exception("Executable doesn't exist at /x/chrome"), "BROWSER"]
        with mock.patch.object(browser.subprocess, "run", return_value=done(0)) as run:
            self.assertEqual(browser.launch(pw), "BROWSER")
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[1:], ["-m", "playwright", "install", "chromium", "--only-shell"])

    def test_other_errors_are_not_swallowed(self):
        pw = mock.Mock()
        pw.chromium.launch.side_effect = Exception("Target page, context or browser has been closed")
        with mock.patch.object(browser.subprocess, "run") as run:
            with self.assertRaises(Exception):
                browser.launch(pw)
        run.assert_not_called()

    def test_failed_install_says_so(self):
        pw = mock.Mock()
        pw.chromium.launch.side_effect = Exception("Looks like Playwright was just installed")
        with mock.patch.object(browser.subprocess, "run", return_value=done(1, "", "403 Forbidden")):
            with self.assertRaises(RuntimeError) as e:
                browser.launch(pw)
        self.assertIn("403 Forbidden", str(e.exception))


class Docs(unittest.TestCase):
    """The docs ARE the program for Claude. These pin what broke or nearly broke."""

    def test_no_dollar_digit_in_skill_docs(self):
        # Claude Code replaces $0, $1, ... in a SKILL.md with the skill's arguments, so
        # "$2" turned into "a" in a live run. Prices are written "USD 2".
        for name in ("SKILL.md", "CAROUSEL.md"):
            text = (SKILL / name).read_text(encoding="utf-8")
            self.assertEqual(re.findall(r"\$\d", text), [], name)

    def test_carousel_commands_go_through_the_launcher(self):
        text = (SKILL / "CAROUSEL.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"(?m)^\s*uv run ")
        self.assertIn('"$UV" run "$SCRIPTS/carousel.py"', text)
        self.assertIn('UV="$SKILL/bin/uv"', text)

    def test_every_carousel_script_pins_the_same_playwright(self):
        pins = {}
        for name in ("carousel.py", "listing_pull.py", "brand_pull.py", "doctor.py"):
            head = (SCRIPTS / name).read_text(encoding="utf-8")[:400]
            m = re.search(r'"playwright==([\d.]+)"', head)
            self.assertIsNotNone(m, name)
            pins[name] = m.group(1)
        self.assertEqual(len(set(pins.values())), 1, pins)

    def test_readme_and_skill_share_the_installer_lines(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for line in ("irm https://raw.githubusercontent.com/Solnest-AI/solnest-cinematic-director-cc/main/install.ps1 | iex",
                     "curl -fsSL https://raw.githubusercontent.com/Solnest-AI/solnest-cinematic-director-cc/main/install.sh | bash"):
            self.assertIn(line, readme)
            self.assertIn(line, skill)
            self.assertIn(line, (ROOT / "INSTALL.md").read_text(encoding="utf-8"))

    def test_readme_opens_with_the_claude_setup_steps(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLess(readme.index('said "set this up"'), readme.index("## Use it"))

    def test_no_em_or_en_dash_in_host_facing_docs(self):
        for p in (ROOT / "README.md", ROOT / "INSTALL.md", SKILL / "CAROUSEL.md"):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("—", text, p.name)


if __name__ == "__main__":
    unittest.main()
