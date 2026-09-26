"""Offline tests for the Cinematic Director scripts. No network, no credits.
Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "skill" / "solnest-cinematic-director" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import assemble  # noqa: E402
import crop  # noqa: E402
import kie  # noqa: E402
import make_clips  # noqa: E402


class CropBox(unittest.TestCase):
    def test_landscape_to_vertical_is_height_bound_and_even(self):
        cw, ch, cx, cy = crop.crop_box(2560, 1706, "9:16")
        self.assertEqual(ch, 1706)
        self.assertEqual(cw % 2, 0)
        self.assertAlmostEqual(cw / ch, 9 / 16, places=2)
        self.assertEqual(cy, 0)

    def test_x_is_clamped_inside_the_photo(self):
        cw, _, cx, _ = crop.crop_box(2560, 1706, "9:16", x=0.0)
        self.assertEqual(cx, 0)
        cw, _, cx, _ = crop.crop_box(2560, 1706, "9:16", x=1.0)
        self.assertEqual(cx, 2560 - cw)

    def test_zoom_tightens(self):
        a = crop.crop_box(2560, 1706, "9:16")
        b = crop.crop_box(2560, 1706, "9:16", zoom=1.25)
        self.assertLess(b[0], a[0])


class Timeline(unittest.TestCase):
    def test_langley_recipe_is_exactly_30s(self):
        used, offsets, total = assemble.timeline([6.0] * 6, 4.6, 0.6, ending_secs=4.0)
        self.assertEqual(used, [4.6] * 5 + [6.0])
        self.assertAlmostEqual(total, 30.0, places=3)
        self.assertAlmostEqual(offsets[0], 4.0, places=3)
        self.assertAlmostEqual(offsets[-1], 20.0, places=3)

    def test_five_beats_with_ending_is_26s(self):
        _, _, total = assemble.timeline([6.0] * 5, 4.6, 0.6, ending_secs=4.0)
        self.assertAlmostEqual(total, 26.0, places=3)

    def test_short_clip_is_not_trimmed_longer_than_it_is(self):
        used, _, _ = assemble.timeline([4.0, 6.0], 4.6, 0.6)
        self.assertEqual(used, [4.0, 6.0])

    def test_single_beat(self):
        used, offsets, total = assemble.timeline([6.0], 4.6, 0.6)
        self.assertEqual((used, offsets, total), ([6.0], [], 6.0))


class Plan(unittest.TestCase):
    def _plan(self, tmp, **over):
        d = pathlib.Path(tmp)
        (d / "a.jpg").write_bytes(b"x")
        (d / "b.jpg").write_bytes(b"x")
        p = {"aspect": "9:16", "duration": 6, "beats": [
            {"name": "01_living", "image": "a.jpg", "prompt": "L" * 80},
            {"name": "02_deck", "image": "b.jpg", "prompt": "D" * 80}]}
        p.update(over)
        (d / "plan.json").write_text(json.dumps(p))
        return d / "plan.json"

    def test_valid_plan_loads(self):
        with tempfile.TemporaryDirectory() as t:
            plan, base, aspect, dur, beats, ending = make_clips.load_plan(self._plan(t))
            self.assertEqual((aspect, dur, len(beats), ending), ("9:16", 6, 2, None))

    def test_rejects_bad_duration_aspect_and_reused_photo(self):
        with tempfile.TemporaryDirectory() as t:
            bad = self._plan(t, duration=5, aspect="4:3", beats=[
                {"name": "a", "image": "a.jpg", "prompt": "x" * 80},
                {"name": "b", "image": "a.jpg", "prompt": "x" * 80}])
            with self.assertRaises(ValueError) as cm:
                make_clips.load_plan(bad)
            msg = str(cm.exception)
            self.assertIn("duration", msg)
            self.assertIn("aspect", msg)
            self.assertIn("same photo", msg)

    def test_rejects_thin_prompt_and_missing_image(self):
        with tempfile.TemporaryDirectory() as t:
            bad = self._plan(t, beats=[{"name": "a", "image": "nope.jpg", "prompt": "push in"}])
            with self.assertRaises(ValueError) as cm:
                make_clips.load_plan(bad)
            self.assertIn("image not found", str(cm.exception))
            self.assertIn("prompt too short", str(cm.exception))

    def test_hold_suffix_keeps_architecture_rigid(self):
        self.assertIn("never warp", make_clips.HOLD)


class KeyLookup(unittest.TestCase):
    def test_env_var_wins_and_key_is_never_in_the_source_label(self):
        with mock.patch.dict(os.environ, {"KIE_API_KEY": "sk-test-123"}):
            key, where = kie.find_key()
        self.assertEqual(key, "sk-test-123")
        self.assertNotIn("sk-test", where)

    def test_missing_key_explains_where_to_put_it(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(kie, "key_search_paths", return_value=[pathlib.Path("/nonexistent/.env")]):
            with self.assertRaises(kie.KieError) as cm:
                kie.find_key()
        self.assertIn("KIE_API_KEY=", str(cm.exception))

    def test_http_200_with_error_code_is_a_failure(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = json.dumps(
            {"code": 401, "msg": "invalid key"}).encode()
        with mock.patch.object(kie, "headers", return_value={}), \
             mock.patch("urllib.request.urlopen", return_value=fake):
            with self.assertRaises(kie.KieError) as cm:
                kie.call("/chat/credit")
        self.assertIn("401", str(cm.exception))

    def test_result_url_shapes(self):
        self.assertEqual(kie.extract_urls({"resultJson": json.dumps({"resultUrls": ["a"]})}), ["a"])
        self.assertEqual(kie.extract_urls({"resultJson": {"data": {"origin_urls": ["b"]}}}), ["b"])
        self.assertEqual(kie.extract_urls({}), [])

    def test_veo_rejects_unsupported_duration(self):
        with self.assertRaises(kie.KieError):
            kie.veo_clip("u", "p", "/tmp/x.mp4", duration=5)


class AsciiOnlyOutput(unittest.TestCase):
    """Windows consoles crash on non-ASCII prints (found in the Listing Optimizer)."""
    def test_scripts_print_ascii_only(self):
        for f in SCRIPTS.glob("*.py"):
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "print(" in line:
                    self.assertTrue(line.isascii(), f"{f.name}:{n} prints non-ASCII")


if __name__ == "__main__":
    unittest.main()


class SkillText(unittest.TestCase):
    """Claude Code substitutes $0, $1, ... in SKILL.md with the invocation's arguments, so a
    price like "$2.28" or awk's "$0" turns into a random word when the skill is called with
    text. Keep every dollar-digit pair out of SKILL.md."""
    def test_no_dollar_digit_in_skill_md(self):
        import re
        text = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r".{0,30}\$\d.{0,10}", text), [])
