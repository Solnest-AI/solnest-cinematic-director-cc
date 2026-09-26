"""Offline tests for the carousel builder, listing pull and brand pull. No network.
Run:  python3 -m unittest discover -s tests -v
Needs Pillow (the carousel half's only non-browser dependency); skipped without it.
"""
import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "skill" / "solnest-cinematic-director" / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False
if HAVE_PIL:
    import carousel  # noqa: E402  (a broken import must fail loudly, not skip)

# Real review text from Azure Palms (Airbnb 1734384025235879146), as scraped 2026-09-26.
CARLITA = ("I can’t recommend this place highly enough. The responsiveness was insanely good and "
           "their place was gorgeous and so well appointed and easy and clean. The amenities in the "
           "building our first rate. It’s worth the price and more. I especially love the "
           "sauna/hot tub/cold plunge/pool. My husband and son were obsessed with the golf simulator. "
           "We had the best time and will stay again.")
REVIEWS = [
    {"author": "Carlita", "location": "Makawao, Hawaii", "when": "3 weeks ago", "rating": 5, "text": CARLITA},
    {"author": "Marcy", "location": None, "when": "August 2026", "rating": 5, "text": "Stunning views and very accommodating"},
    {"author": "Dan", "location": "Calgary, Canada", "when": "July 2026", "rating": 4, "text": "Great view, noisy construction."},
]
FACTS = ("Nine floors above Okanagan Lake, with a resort floor downstairs. Two golf simulators, "
         "sauna, cold plunge. Dryer – In unit. Dogs welcome.")


def review_slide(quote, by="Carlita"):
    return {"t": "review", "quote": quote, "by": by, "claims": []}


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class ReviewGate(unittest.TestCase):
    def test_verbatim_excerpt_passes_even_with_straight_quotes(self):
        q = "I can't recommend this place highly enough."
        self.assertIsNone(carousel.check_review(review_slide(q), REVIEWS))

    def test_excerpt_spanning_sentences_passes(self):
        q = "My husband and son were obsessed with the golf simulator. We had the best time and will stay again."
        self.assertIsNone(carousel.check_review(review_slide(q), REVIEWS))

    def test_tidied_quote_fails(self):
        q = "The amenities in the building are first rate."  # guest wrote "our first rate"
        self.assertIn("verbatim", carousel.check_review(review_slide(q), REVIEWS))

    def test_merged_sentences_fail(self):
        q = "I can't recommend this place highly enough. We had the best time and will stay again."
        self.assertIn("verbatim", carousel.check_review(review_slide(q), REVIEWS))

    def test_four_star_review_is_refused(self):
        err = carousel.check_review(review_slide("Great view", by="Dan"), REVIEWS)
        self.assertIn("5-star", err)

    def test_unknown_author_is_refused(self):
        self.assertIn("no review", carousel.check_review(review_slide("Stunning views", by="Bob"), REVIEWS))

    def test_no_reviews_at_all(self):
        self.assertIn("no review", carousel.check_review(review_slide("Stunning views", by="Marcy"), []))

    def test_overlong_quote_is_refused(self):
        self.assertIn("too long", carousel.check_review(review_slide(CARLITA), REVIEWS))

    def test_attribution_uses_location_only_when_it_is_a_place(self):
        self.assertEqual(carousel.attribution(REVIEWS[0]), "Carlita, Makawao, Hawaii")
        self.assertEqual(carousel.attribution(REVIEWS[1]), "Marcy")


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class FactsAndVoice(unittest.TestCase):
    def plan(self, **slide):
        s = {"t": "room", "photo": "01", "title": "Two golf simulators", "claims": ["two golf simulators"]}
        s.update(slide)
        return {"slides": [s], "caption": "Nine floors above the lake.", "caption_claims": ["nine floors above"]}

    def test_claims_found_case_insensitive(self):
        self.assertEqual(carousel.check_facts(self.plan(), FACTS), {})

    def test_missing_claim_reported_per_slide(self):
        miss = carousel.check_facts(self.plan(claims=["hot tub on the balcony"]), FACTS)
        self.assertEqual(miss, {"01": ["hot tub on the balcony"]})

    def test_caption_claims_checked(self):
        p = self.plan()
        p["caption_claims"] = ["private beach"]
        self.assertEqual(carousel.check_facts(p, FACTS), {"caption": ["private beach"]})

    def test_en_dash_in_facts_still_matches_a_hyphen_claim(self):
        self.assertEqual(carousel.check_facts(self.plan(claims=["dryer - in unit"]), FACTS), {})

    def test_voice_catches_dashes_hashtags_emoji(self):
        p = self.plan(title="Golf — all year")
        p["caption"] = "Book now #kelowna \U0001F31E"
        hits = " ".join(carousel.check_voice(p))
        self.assertIn("em dash", hits)
        self.assertIn("hashtag", hits)
        self.assertIn("emoji", hits)

    def test_middle_dot_and_apostrophe_are_fine(self):
        p = self.plan(title="Kelowna · Sleeps 4")
        p["caption"] = "It's nine floors up."
        self.assertEqual(carousel.check_voice(p), [])


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class PlanValidation(unittest.TestCase):
    def write(self, plan):
        d = pathlib.Path(tempfile.mkdtemp())
        (d / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        return d / "plan.json"

    def base(self, slides):
        return {"facts": "facts.txt", "brand": "brand.json", "slides": slides, "caption": "x", "caption_claims": []}

    def test_unknown_template(self):
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(self.base([{"t": "hero", "photo": "01", "claims": []}])))
        self.assertIn("unknown template", str(cm.exception))

    def test_too_many_slides(self):
        slides = [{"t": "photo", "photo": "01", "label": "x", "claims": []}] * 11
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(self.base(slides)))
        self.assertIn("at most 10", str(cm.exception))

    def test_missing_required_field(self):
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(self.base([{"t": "room", "photo": "01", "claims": []}])))
        self.assertIn("title", str(cm.exception))

    def test_claims_key_required_on_text_slides(self):
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(self.base([{"t": "room", "photo": "01", "title": "Hi"}])))
        self.assertIn("claims", str(cm.exception))

    def test_good_plan_loads_and_numbers_slides(self):
        p = carousel.load_plan(self.write(self.base([
            {"t": "cover", "photo": "01", "title": "Nine floors", "claims": []},
            {"t": "review", "quote": "Stunning views", "by": "Marcy", "claims": []}])))
        self.assertEqual([s["id"] for s in p["slides"]], ["01", "02"])
        self.assertEqual(p.get("look"), "house")


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class Contrast(unittest.TestCase):
    def test_measure_uses_the_worst_pixels(self):
        im = Image.new("RGB", (2160, 2700), (255, 255, 255))
        im.paste((0, 0, 0), (0, 0, 1080, 2700))  # left half black
        r, _ = carousel.measure(im, (100, 100, 800, 200), (255, 255, 255))
        self.assertLess(r, 1.5)  # white text over a half-white patch fails

    def test_pick_text_on_light_and_dark_accents(self):
        ink, light = "#1B1B19", "#F7F5F0"
        sage = Image.new("RGB", (2160, 2700), (0x8A, 0x8C, 0x6D))
        navy = Image.new("RGB", (2160, 2700), (0x14, 0x21, 0x3D))
        rect = (96, 400, 800, 300)
        self.assertEqual(carousel.pick_text_on(sage, rect, [ink, light])[0], ink)
        self.assertEqual(carousel.pick_text_on(navy, rect, [ink, light])[0], light)

    def test_pick_text_on_reports_failure_when_nothing_passes(self):
        grey = Image.new("RGB", (2160, 2700), (128, 128, 128))
        col, r, _ = carousel.pick_text_on(grey, (96, 400, 800, 300), ["#777777", "#999999"])
        self.assertLess(r, carousel.MIN_RATIO)

    def test_house_look_is_deterministic_and_keeps_size(self):
        im = Image.new("RGB", (64, 80), (120, 140, 160))
        a, b = carousel.house_look(im, False), carousel.house_look(im, False)
        self.assertEqual(a.size, (64, 80))
        self.assertEqual(a.tobytes(), b.tobytes())


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class Brand(unittest.TestCase):
    def test_brand_validation(self):
        good = {"name": "Solnest Stays", "ink": "#1B1B19", "paper": "#EEEDE8", "accent": "#8A8C6D",
                "on_photo": "#F7F5F0", "display_font": "Cormorant Garamond", "text_font": "Montserrat"}
        self.assertEqual(carousel.check_brand(good), [])
        bad = dict(good, accent="sage", display_font="Comic Sans")
        errs = " ".join(carousel.check_brand(bad))
        self.assertIn("accent", errs)
        self.assertIn("Comic Sans", errs)

    def test_logo_without_transparency_is_not_used(self):
        d = pathlib.Path(tempfile.mkdtemp())
        Image.new("RGB", (200, 80), "white").save(d / "logo.jpg")
        self.assertIsNone(carousel.usable_logo(d / "logo.jpg"))
        rgba = Image.new("RGBA", (200, 80), (0, 0, 0, 0))
        rgba.paste((0, 0, 0, 255), (20, 20, 180, 60))
        rgba.save(d / "logo.png")
        self.assertIsNotNone(carousel.usable_logo(d / "logo.png"))


if __name__ == "__main__":
    unittest.main()
