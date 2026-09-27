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
class DisplayedWords(unittest.TestCase):
    """Codex P1: the gate must check what the slide SAYS, not only the claims list."""
    def plan(self, title, claims, caption="Nice place.", cta=None):
        s = {"t": "room", "photo": "01", "title": title, "claims": claims}
        if cta:
            s = {"t": "last", "photo": "01", "cta": cta, "line": title, "claims": claims}
        return {"slides": [s], "caption": caption, "caption_claims": []}

    def test_invented_number_fails_even_with_empty_claims(self):
        errs = carousel.check_numbers(self.plan("Private hot tub. Sleeps 20.", []), "Sleeps 2. Two golf simulators.")
        self.assertTrue(any("20" in e for e in errs))

    def test_number_words_and_digits_match_both_ways(self):
        facts = "Nine floors above the lake. 4 guests. Two queen beds. 2.5 baths."
        p = self.plan("Nine floors, sleeps four, 2 queens, 2.5 baths", ["nine floors"])
        self.assertEqual(carousel.check_numbers(p, facts), [])

    def test_caption_numbers_checked(self):
        errs = carousel.check_numbers(self.plan("Hi", [], caption="Sleeps 14 easily."), "Sleeps 12.")
        self.assertTrue(any("caption" in e and "14" in e for e in errs))

    def test_host_cta_numbers_are_exempt(self):
        p = self.plan("Kelowna", ["kelowna"], caption="Book 3 nights, save 10%.", cta="Book 3 nights, save 10%")
        self.assertEqual(carousel.check_numbers(p, "Kelowna."), [])

    def test_negated_fact_does_not_back_a_claim(self):
        miss = carousel.check_facts(self.plan("A hot tub", ["hot tub"]), "Pool. No hot tub. Sauna.")
        self.assertEqual(miss, {"01": ["hot tub"]})

    def test_claim_found_once_negated_once_plain_still_passes(self):
        facts = "No hot tub in the unit. The building has a shared hot tub."
        self.assertEqual(carousel.check_facts(self.plan("Hot tub", ["hot tub"]), facts), {})

    def test_words_must_come_from_this_slides_claims(self):
        errs = carousel.check_coverage(self.plan("Private hot tub", ["pool"]))
        self.assertTrue(errs and "private" in errs[0] and "tub" in errs[0], errs)

    def test_style_words_and_units_need_no_claim(self):
        p = {"slides": [{"t": "diptych", "label": "Inside", "title": "The details", "claims": [],
                         "photos": [{"photo": "01"}, {"photo": "02"}]},
                        {"t": "list", "title": "Close at hand", "rows": [["Pandosy", "5 min"], ["Downtown", "10 min"]],
                         "claims": ["Pandosy Village, about 5 minutes", "Downtown Kelowna, about 10 minutes"]}],
             "caption": "x", "caption_claims": []}
        self.assertEqual(carousel.check_coverage(p), [])

    def test_declared_style_words_pass_but_are_reported(self):
        p = self.plan("Out back", ["hot tub"], caption="")
        self.assertTrue(carousel.check_coverage(p))
        p["style_words"] = ["back"]
        self.assertEqual(carousel.check_coverage(p), [])

    def test_caption_words_backed_by_caption_or_slide_claims(self):
        p = self.plan("Two golf simulators", ["two golf simulators"], caption="Two golf simulators and a private beach.")
        errs = carousel.check_coverage(p)
        self.assertTrue(any("caption" in e and "beach" in e and "private" in e for e in errs), errs)
        self.assertFalse(any("golf" in e for e in errs))

    def test_recombined_words_fail(self):
        errs = carousel.check_coverage(self.plan("Private pool", ["Private balcony", "shared pool"], caption=""))
        self.assertTrue(errs and "private pool" in errs[0], errs)

    def test_units_and_travel_mode_must_be_cited(self):
        errs = carousel.check_coverage(self.plan("Pool 5 min walk", ["Pool is 5 hours drive away"], caption=""))
        self.assertTrue(errs and "min" in errs[0] and "walk" in errs[0], errs)

    def test_negative_claim_cannot_back_positive_copy(self):
        errs = carousel.check_coverage(self.plan("Hot tub", ["No hot tub"], caption=""))
        self.assertTrue(errs and "negative" in errs[0], errs)
        self.assertEqual(carousel.check_coverage(self.plan("No stairs", ["no stairs"], caption="")), [])

    def test_review_label_is_checked(self):
        p = {"slides": [{"t": "review", "label": "Private hot tub", "quote": "We enjoyed our stay.", "by": "Alex"}],
             "caption": "", "caption_claims": []}
        errs = carousel.check_coverage(p)
        self.assertTrue(errs and "private" in errs[0], errs)
        p["slides"][0]["label"] = "Guest review"
        self.assertEqual(carousel.check_coverage(p), [])

    def test_two_letter_amenities_need_a_claim_but_region_codes_do_not(self):
        errs = carousel.check_coverage(self.plan("AC and TV", ["Pool"], caption=""))
        self.assertTrue(errs and "ac" in errs[0] and "tv" in errs[0], errs)
        self.assertEqual(carousel.check_coverage(self.plan("Kelowna, BC", ["Kelowna"], caption="")), [])

    def test_words_on_different_lines_never_pair(self):
        p = {"slides": [{"t": "split", "photo": "01", "label": "The resort floor", "title": "An indoor putting green",
                         "body": "Shared with the building.", "claims": ["resort floor", "indoor putting green",
                                                                        "Shared with the building"]}],
             "caption": "", "caption_claims": []}
        self.assertEqual(carousel.check_coverage(p), [])

    def test_honest_paraphrases_still_pass(self):
        ok = [("Log beams and a stone fireplace", ["Vaulted log-beam ceilings + stone fireplace"]),
              ("A private hot tub", ["Private forest-edge hot tub"]),
              ("Two queens, two full baths", ["Two queen beds", "two full baths"]),
              ("Four bedrooms and a bunk room", ["4 real bedrooms plus a basement bunk room"])]
        for title, claims in ok:
            self.assertEqual(carousel.check_coverage(self.plan(title, claims, caption="")), [], title)

    def test_negation_after_the_phrase(self):
        miss = carousel.check_facts(self.plan("Hot tub", ["hot tub"]), "Hot tub is not available this season.")
        self.assertEqual(miss, {"01": ["hot tub"]})

    def test_negation_does_not_cross_lines(self):
        self.assertEqual(carousel.check_facts(self.plan("Hot tub", ["hot tub"]), "No smoking\nHot tub\nSauna"), {})

    def test_compound_numbers_and_thousands(self):
        facts = "Twenty-four guests. 1,000 square feet."
        p = self.plan("24 guests, 1000 square feet", ["guests"])
        self.assertEqual(carousel.check_numbers(p, facts), [])
        p = self.plan("Twenty-four guests", ["guests"])
        self.assertEqual(carousel.check_numbers(p, "24 guests"), [])

    def test_hashtag_after_punctuation_caught(self):
        for cap in ("Book now,#beach", "Book now&#beach"):
            p = self.plan("Hi", [], caption=cap)
            self.assertTrue(any("hashtag" in h for h in carousel.check_voice(p)), cap)


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

    def test_factual_templates_need_at_least_one_claim(self):
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(self.base([{"t": "room", "photo": "01", "title": "Hi", "claims": []}])))
        self.assertIn("at least one claim", str(cm.exception))

    def test_unknown_look_rejected(self):
        p = self.base([{"t": "photo", "photo": "01", "label": "x", "claims": []}])
        p["look"] = "original"
        with self.assertRaises(carousel.PlanError) as cm:
            carousel.load_plan(self.write(p))
        self.assertIn("look", str(cm.exception))

    def test_good_plan_loads_and_numbers_slides(self):
        p = carousel.load_plan(self.write(self.base([
            {"t": "cover", "photo": "01", "title": "Nine floors", "claims": ["nine floors"]},
            {"t": "review", "quote": "Stunning views", "by": "Marcy", "claims": []}])))
        self.assertEqual([s["id"] for s in p["slides"]], ["01", "02"])
        self.assertEqual(p.get("look"), "house")


@unittest.skipUnless(HAVE_PIL, "Pillow not installed")
class CallToAction(unittest.TestCase):
    """Every host has their own line: saved once in brand.json, overridable per plan."""
    def plan(self, cta=None, caption="Nine floors above the lake."):
        last = {"t": "last", "photo": "01", "claims": ["x"]}
        if cta:
            last["cta"] = cta
        return {"slides": [{"t": "room", "photo": "02", "title": "x", "claims": ["x"]}, last], "caption": caption}

    def test_plan_beats_brand_beats_default(self):
        B = {"cta": "Book direct at lakehouse.com", "handle": "@lakehouse"}
        self.assertEqual(carousel.resolve_cta(self.plan("DM us STAY"), B), ("DM us STAY", "plan"))
        self.assertEqual(carousel.resolve_cta(self.plan(), B), ("Book direct at lakehouse.com", "brand"))
        self.assertEqual(carousel.resolve_cta(self.plan(), {}), (carousel.DEFAULT_CTA, "default"))

    def test_resolved_cta_lands_on_the_last_slide(self):
        p = self.plan()
        carousel.resolve_cta(p, {"cta": "Book direct at lakehouse.com"})
        self.assertEqual(p["slides"][-1]["cta"], "Book direct at lakehouse.com")

    def test_caption_gets_cta_and_handle_once(self):
        B = {"handle": "@lakehouse"}
        cap = carousel.full_caption(self.plan(), B, "Book direct at lakehouse.com")
        self.assertTrue(cap.endswith("Book direct at lakehouse.com\n@lakehouse"), cap)
        again = carousel.full_caption(self.plan(caption=cap), B, "book direct at LAKEHOUSE.com")
        self.assertEqual(again.count("lakehouse.com"), 1)
        self.assertEqual(again.count("@lakehouse"), 1)

    def test_no_handle_no_handle_line(self):
        cap = carousel.full_caption(self.plan(), {}, "DM us STAY")
        self.assertTrue(cap.endswith("\n\nDM us STAY"), cap)

    def test_last_slide_needs_no_cta_in_the_plan(self):
        d = pathlib.Path(tempfile.mkdtemp())
        p = {"facts": "f", "brand": "b", "caption": "x",
             "slides": [{"t": "last", "photo": "01", "claims": ["x"]}]}
        (d / "plan.json").write_text(json.dumps(p), encoding="utf-8")
        self.assertEqual(carousel.load_plan(d / "plan.json")["slides"][0]["t"], "last")

    def test_brand_cta_is_voice_checked(self):
        good = {"name": "S", "ink": "#1B1B19", "paper": "#EEEDE8", "accent": "#8A8C6D", "on_photo": "#F7F5F0",
                "display_font": "Cormorant Garamond", "text_font": "Montserrat"}
        self.assertEqual(carousel.check_brand(dict(good, cta="Book direct at lakehouse.com")), [])
        errs = " ".join(carousel.check_brand(dict(good, cta="Book now \u2014 #lake")))
        self.assertIn("em dash", errs)
        self.assertIn("hashtag", errs)
        self.assertIn("too long", " ".join(carousel.check_brand(dict(good, cta="x" * 80))))


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

    def test_mid_tone_text_uses_the_worst_of_both_extremes(self):
        im = Image.new("RGB", (2160, 2700), (0, 0, 0))
        im.paste((0x77, 0x77, 0x77), (0, 0, 2160, 1350))   # top half grey, bottom half black
        r, _ = carousel.measure(im, (100, 500, 800, 350), (0x77, 0x77, 0x77))
        self.assertLess(r, 1.5)

    def test_small_bright_patch_behind_text_is_not_averaged_away(self):
        im = Image.new("RGB", (2160, 2700), (0, 0, 0))
        im.paste((255, 255, 255), (600, 600, 660, 660))    # 30x30 CSS px inside an 800x300 block
        r, _ = carousel.measure(im, [(100, 250, 800, 60), (100, 310, 800, 60)], (255, 255, 255))
        self.assertLess(r, carousel.MIN_RATIO)

    def test_bright_patch_in_a_tall_line_is_caught(self):
        im = Image.new("RGB", (2160, 2700), (0, 0, 0))
        im.paste((255, 255, 255), (700, 700, 730, 730))    # 15x15 CSS px under a 100px-tall line
        r, _ = carousel.measure(im, [(100, 300, 800, 100)], (255, 255, 255))
        self.assertLess(r, carousel.MIN_RATIO)

    def test_a_tiny_speck_is_tolerated(self):
        im = Image.new("RGB", (2160, 2700), (0, 0, 0))
        im.paste((255, 255, 255), (700, 700, 702, 702))    # 1x1 CSS px, JPEG-noise size
        r, _ = carousel.measure(im, [(100, 300, 800, 100)], (255, 255, 255))
        self.assertGreater(r, carousel.MIN_RATIO)

    def test_flat_photo_is_not_crushed_by_levels(self):
        im = Image.new("RGB", (80, 80), (100, 120, 140))
        out = carousel.levels(im, False).getpixel((0, 0))
        self.assertTrue(all(abs(a - b) <= 25 for a, b in zip(out, (100, 120, 140))), out)

    def test_look_none_leaves_pixels_alone(self):
        d = pathlib.Path(tempfile.mkdtemp())
        Image.new("RGB", (400, 500), (100, 120, 140)).save(d / "a.png")
        carousel.prep_photo(d / "a.png", {}, 0.8, d / "b.png", "none")
        px = Image.open(d / "b.png").convert("RGB").getpixel((300, 300))
        self.assertTrue(all(abs(a - b) <= 2 for a, b in zip(px, (100, 120, 140))), px)

    def test_same_family_fonts_need_one_face(self):
        B = {"display_font": "Inter", "text_font": "Inter"}
        self.assertIn(">= 1;", carousel.fonts_ok_js(B, italic=True))
        B = {"display_font": "Cormorant Garamond", "text_font": "Montserrat"}
        self.assertIn(">= 3;", carousel.fonts_ok_js(B, italic=True))

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
