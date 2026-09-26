#!/usr/bin/env python3
"""Carousel builder for the Solnest Cinematic Director.

Turns plan.json (written by Claude after LOOKING at the photos) into 1080x1350 Instagram
slides. Every rule here came out of the 2026-09-26 trials (Apres Arcade, Azure Palms) and
a Codex + Grok review; see CAROUSEL.md for the why.

Gates, all run BEFORE the browser starts (exit 2, nothing rendered):
  * plan shape      known templates, required fields, at most 10 slides
  * brand           hex colours, bundled fonts only
  * facts           every claim on every slide and in the caption must appear in the
                    listing text (case/quote/whitespace-insensitive)
  * reviews         a quote must be a verbatim excerpt of ONE scraped 5-star review, by
                    that reviewer; no reviews = no review slide
  * voice           no em/en dashes, hashtags or emoji in slides or caption
Then, while rendering (exit 1, run folder marked -FAILED):
  * contrast        text colour vs the darkest/brightest 2% of the pixels actually painted
                    behind it, >= 4.5:1, busy photos refuse text without an overlay.
                    Preference: clean > light gradient > solid panel.
  * fonts           bundled fonts must be loaded before any screenshot.

Usage:
  python3 carousel.py plan.json            gates, render, preview, report
  python3 carousel.py plan.json --check    gates only (free, instant)

Needs: pip install playwright pillow ; python -m playwright install chromium
Console output is ASCII only so a Windows console can never crash on it.
"""
import argparse
import html
import json
import pathlib
import re
import sys
import time
import unicodedata

from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = SKILL_DIR / "fonts"
W, H, M = 1080, 1350, 96
MIN_RATIO = 4.5
BUSY_EDGE = 14.0        # mean edge strength (0-255) above which "no overlay" is refused
MAX_SLIDES = 10
MAX_QUOTE = 200         # characters; one or two sentences fit the review slide
MIN_QUOTE = 12

FONTS = {  # bundled, SIL OFL (fonts/OFL.txt)
    "Cormorant Garamond": {"kind": "display", "roman": "CormorantGaramond.ttf",
                           "italic": "CormorantGaramond-Italic.ttf", "weights": "300 700"},
    "Playfair Display": {"kind": "display", "roman": "PlayfairDisplay.ttf",
                         "italic": "PlayfairDisplay-Italic.ttf", "weights": "400 900"},
    "Montserrat": {"kind": "text", "roman": "Montserrat.ttf", "weights": "100 900"},
    "Inter": {"kind": "text", "roman": "Inter.ttf", "weights": "100 900"},
}

# template -> required fields ("claims" is required on every template except review)
TEMPLATES = {
    "cover": ("photo", "title"),
    "room": ("photo", "title"),
    "photo": ("photo", "label"),
    "split": ("photo", "title", "body"),
    "diptych": ("photos", "title"),
    "list": ("title", "rows"),
    "review": ("quote", "by"),
    "last": ("photo", "cta"),
}
PHOTO_TEMPLATES = ("cover", "room", "photo", "last")
TEXT_FIELDS = ("label", "title", "body", "line", "cta")
BRAND_KEYS = ("name", "ink", "paper", "accent", "on_photo", "display_font", "text_font")
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class PlanError(ValueError):
    pass


def out(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"), flush=True)


# --- text helpers ---------------------------------------------------------------

_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"',
                        "–": "-", "—": "-", " ": " "})


def norm(s):
    """Compare text the way a reader would: same letters, any quotes/spacing/case."""
    s = unicodedata.normalize("NFKC", str(s or "")).translate(_TRANS)
    return re.sub(r"\s+", " ", s).strip().lower()


def esc(s):
    return html.escape(str(s), quote=False).replace("\n", "<br>")


def sid(s, i):
    return s.get("id") or f"{i:02d}"


# --- plan + brand ---------------------------------------------------------------

def load_plan(path):
    path = pathlib.Path(path)
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PlanError(f"cannot read {path}: {e}")
    errs = []
    for k in ("facts", "brand", "caption"):
        if not plan.get(k):
            errs.append(f"plan: missing '{k}'")
    slides = plan.get("slides") or []
    if not slides:
        errs.append("plan: no slides")
    if len(slides) > MAX_SLIDES:
        errs.append(f"plan: {len(slides)} slides, at most {MAX_SLIDES}")
    seen = set()
    for i, s in enumerate(slides, 1):
        s["id"] = sid(s, i)
        tag = f"slide {s['id']}"
        if s["id"] in seen:
            errs.append(f"{tag}: duplicate id")
        seen.add(s["id"])
        t = s.get("t")
        if t not in TEMPLATES:
            errs.append(f"{tag}: unknown template '{t}' (use one of {', '.join(TEMPLATES)})")
            continue
        for f in TEMPLATES[t]:
            if not s.get(f):
                errs.append(f"{tag} ({t}): missing '{f}'")
        if t != "review" and not isinstance(s.get("claims"), list):
            errs.append(f"{tag} ({t}): needs a 'claims' list (the facts behind its words; [] if none)")
        if t == "diptych" and (not isinstance(s.get("photos"), list) or len(s["photos"]) != 2
                               or not all(isinstance(p, dict) and p.get("photo") for p in s["photos"])):
            errs.append(f"{tag} (diptych): 'photos' must be two {{\"photo\": id}} entries")
        if t == "list":
            rows = s.get("rows") or []
            if not (2 <= len(rows) <= 6) or not all(isinstance(r, list) and len(r) == 2 for r in rows):
                errs.append(f"{tag} (list): 'rows' must be 2 to 6 [left, right] pairs")
    if errs:
        raise PlanError("\n".join(errs))
    plan.setdefault("look", "house")
    plan.setdefault("caption_claims", [])
    return plan


def check_brand(B):
    errs = [f"brand: missing '{k}'" for k in BRAND_KEYS if not B.get(k)]
    for k in ("ink", "paper", "accent", "on_photo"):
        if B.get(k) and not HEX.match(str(B[k])):
            errs.append(f"brand: {k} must be a #RRGGBB colour, got '{B[k]}'")
    for k, kind in (("display_font", "display"), ("text_font", "text")):
        f = B.get(k)
        if f and (f not in FONTS or FONTS[f]["kind"] != kind):
            ok = ", ".join(n for n, v in FONTS.items() if v["kind"] == kind)
            errs.append(f"brand: {k} '{f}' is not bundled; pick the closest of: {ok}")
    return errs


def usable_logo(path):
    """The logo as a cropped RGBA image, or None if it has no real transparency
    (a logo on a white box looks cheap; the last slide then uses a wordmark)."""
    try:
        im = Image.open(path)
    except (OSError, ValueError):
        return None
    im = im.convert("RGBA")
    a = im.split()[3]
    if a.getextrema()[0] == 255:
        return None
    box = a.getbbox()
    return im.crop(box) if box else None


# --- gates ----------------------------------------------------------------------

def check_facts(plan, facts_text):
    f = norm(facts_text)
    missing = {}
    for i, s in enumerate(plan["slides"], 1):
        miss = [c for c in s.get("claims", []) if norm(c) not in f]
        if miss:
            missing[sid(s, i)] = miss
    cmiss = [c for c in plan.get("caption_claims", []) if norm(c) not in f]
    if cmiss:
        missing["caption"] = cmiss
    return missing


def check_review(slide, reviews):
    """None if the quote is a verbatim excerpt of a 5-star review by that reviewer."""
    who = slide.get("by", "")
    mine = [r for r in reviews or [] if norm(r.get("author")) == norm(who)]
    if not mine:
        return f"no review by '{who}' in the scraped reviews (no reviews = no review slide)"
    five = [r for r in mine if r.get("rating") == 5]
    if not five:
        return f"the review by '{who}' is not a 5-star review; only 5-star reviews go on a slide"
    q = norm(slide.get("quote", "")).strip(" \"'")
    if len(q) > MAX_QUOTE:
        return f"quote is too long ({len(q)} chars, max {MAX_QUOTE}); use one or two sentences"
    if len(q) < MIN_QUOTE:
        return "quote is too short"
    if not any(q in norm(r.get("text")) for r in five):
        return (f"quote is not a verbatim excerpt of {who}'s review. Copy one run of their "
                "words exactly (their spelling too); do not tidy, shorten inside, or join sentences")
    return None


def attribution(review):
    loc = review.get("location")
    return f"{review['author']}, {loc}" if loc else review["author"]


_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def check_voice(plan):
    """Brand voice on OUR words. Review quotes are the guest's words and are exempt."""
    hits = []

    def scan(where, text):
        text = str(text or "")
        if "—" in text:
            hits.append(f"{where}: em dash")
        if "–" in text:
            hits.append(f"{where}: en dash")
        if re.search(r"(^|\s)#\w", text):
            hits.append(f"{where}: hashtag")
        if _EMOJI.search(text):
            hits.append(f"{where}: emoji")

    for i, s in enumerate(plan["slides"], 1):
        for f in TEXT_FIELDS:
            scan(f"slide {sid(s, i)} {f}", s.get(f))
        for k, v in s.get("rows") or []:
            scan(f"slide {sid(s, i)} rows", f"{k} {v}")
    scan("caption", plan.get("caption"))
    return hits


# --- colour ---------------------------------------------------------------------

def hexrgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgba(h, a):
    r, g, b = hexrgb(h)
    return f"rgba({r},{g},{b},{a})"


def rel_lum(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a, b):
    la, lb = sorted((rel_lum(a), rel_lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def measure(bg2x, rect, rgb):
    """Worst-case contrast of `rgb` against the painted background under `rect` (CSS px
    on a 2x screenshot), plus how busy that background is."""
    x, y, w, h = rect
    pad = 6
    box = tuple(int(v * 2) for v in (max(0, x - pad), max(0, y - pad), min(W, x + w + pad), min(H, y + h + pad)))
    reg = bg2x.crop(box).resize((max(1, (box[2] - box[0]) // 2), max(1, (box[3] - box[1]) // 2)), Image.BOX)
    px = sorted(getattr(reg, "get_flattened_data", reg.getdata)(), key=rel_lum)
    lo, hi = px[int(len(px) * 0.02)], px[int(len(px) * 0.98) - 1]
    worst = hi if rel_lum(rgb) > 0.5 else lo
    edge = ImageStat.Stat(reg.convert("L").filter(ImageFilter.FIND_EDGES)).mean[0]
    return round(ratio(rgb, worst), 2), round(edge, 1)


def pick_text_on(bg2x, rect, candidates):
    """First candidate colour that passes on this background, else the best one."""
    best = None
    for c in candidates:
        r, e = measure(bg2x, rect, hexrgb(c))
        if r >= MIN_RATIO:
            return c, r, e
        if best is None or r > best[1]:
            best = (c, r, e)
    return best


# --- photos ---------------------------------------------------------------------

def crop_to(im, fx, fy, aspect):
    iw, ih = im.size
    if iw / ih > aspect:
        ch, cw = ih, int(ih * aspect)
    else:
        cw, ch = iw, int(iw / aspect)
    x = int(min(max(fx * iw - cw / 2, 0), iw - cw))
    y = int(min(max(fy * ih - ch / 2, 0), ih - ch))
    return im.crop((x, y, x + cw, y + ch))


def levels(im, night):
    """Capped levels stretch. Remaps tones only; moves no pixel."""
    hist = im.convert("L").histogram()
    tot = sum(hist)

    def pct(p):
        c = 0
        for i, h in enumerate(hist):
            c += h
            if c >= p * tot:
                return i
        return 255
    lo, hi = pct(0.004), pct(0.998 if night else 0.996)
    top, bot = (250, 4) if night else (247, 6)
    scale = min((top - bot) / max(1, hi - lo), 1.25)
    lut = [max(0, min(255, int((v - lo) * scale + bot))) for v in range(256)]
    return im.point(lut * 3)


def house_look(im, night):
    """One grade across the set so it reads as one shoot: soft S-curve, lifted blacks,
    rolled highlights, saturation 0.88 (0.95 at night), a touch of warmth by day."""
    def curve(v):
        x = v / 255
        x = x * 0.75 + (3 * x * x - 2 * x * x * x) * 0.25
        return int(round(10 + x * (244 - 10)))
    im = im.point([curve(v) for v in range(256)] * 3)
    im = ImageEnhance.Color(im).enhance(0.95 if night else 0.88)
    if not night:
        r, g, b = im.split()
        r = r.point(lambda v: min(255, int(v * 1.02)))
        b = b.point(lambda v: int(v * 0.97))
        im = Image.merge("RGB", (r, g, b))
    return im


def photo_path(pdir, plan, pid, source=None):
    pid = str(pid)
    if "/" in pid or "\\" in pid or "." in pid:
        return pdir / pid
    base = pdir / plan.get("photos", "source")
    return base / "fixed" / f"{pid}.png" if source == "fixed" else base / "full" / f"{pid}.jpg"


def prep_photo(src, spec, aspect, dest, look):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im = crop_to(im, *spec.get("focal", (0.5, 0.5)), aspect)
    tw = W * 2
    th = int(round(tw / aspect))
    soft = im.size[0] < tw * 0.6
    im = im.resize((tw, th), Image.LANCZOS)
    im = levels(im, spec.get("night", False))
    if look == "house":
        im = house_look(im, spec.get("night", False))
    im.save(dest, quality=94)
    return soft


# --- HTML -----------------------------------------------------------------------

def font_css(B):
    rules = []
    for fam in dict.fromkeys((B["display_font"], B["text_font"])):
        spec = FONTS[fam]
        for style, key in (("normal", "roman"), ("italic", "italic")):
            if spec.get(key):
                uri = (FONT_DIR / spec[key]).as_uri()
                rules.append(f"@font-face{{font-family:'{fam}';src:url('{uri}') format('truetype');"
                             f"font-weight:{spec['weights']};font-style:{style}}}")
    return "\n".join(rules)


def page(inner, B, bg, hide_text):
    vis = ".t{visibility:hidden}" if hide_text else ""
    d, t = B["display_font"], B["text_font"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{font_css(B)}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:{bg}}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden}}
.bgimg{{position:absolute;left:0;top:0;width:100%;height:100%;object-fit:cover}}
.label{{font-family:'{t}',sans-serif;font-weight:600;font-size:26px;letter-spacing:.18em;text-transform:uppercase;line-height:1.3}}
.title{{font-family:'{d}',serif;font-weight:600;line-height:1.04;text-wrap:balance}}
.body{{font-family:'{t}',sans-serif;font-weight:500;font-size:34px;line-height:1.45}}
.wordmark{{font-family:'{d}',serif;font-weight:600;font-size:46px;letter-spacing:.16em;text-transform:uppercase}}
.block{{position:absolute;left:{M}px;right:{M}px}}
{vis}</style></head><body><div class="slide">{inner}</div></body></html>"""


def fonts_ok_js(B, italic):
    d, t = B["display_font"], B["text_font"]
    loads = [f"600 72px '{d}'", f"600 26px '{t}'"] + ([f"italic 500 60px '{d}'"] if italic else [])
    load = "".join(f"await document.fonts.load({json.dumps(x)});" for x in loads)
    checks = " && ".join(f"document.fonts.check({json.dumps(x)})" for x in loads)
    return (f"(async () => {{ {load} await document.fonts.ready; return {checks} && "
            f"[...document.fonts].filter(f => f.status === 'loaded').length >= {len(loads)}; }})()")


def scrim(alpha, anchor):
    if alpha <= 0:
        return ""
    side = "top" if anchor in ("top", "mid") else "bottom"
    to = "bottom" if side == "top" else "top"
    return (f'<div style="position:absolute;left:0;right:0;{side}:0;height:46%;'
            f'background:linear-gradient(to {to},rgba(0,0,0,{alpha}) 0%,rgba(0,0,0,{alpha}) 45%,rgba(0,0,0,0) 100%)"></div>')


def pos(anchor):
    return {"top": f"top:{M + 10}px", "mid": "top:330px"}.get(anchor, f"bottom:{M}px")


def photo_slide(s, B, img, anchor, color, mode, alpha, hide, logo):
    t = s["t"]
    panel = ""
    if mode == "panel":
        side = pos(anchor).split(":")[0]
        panel = (f'<div id="panel" style="position:absolute;left:{M - 36}px;{side}:{M - 30}px;'
                 f'background:{B["paper"]};opacity:.96"></div>')
    label = f'<div class="label t" style="margin-bottom:{30 if t == "cover" else 20}px">{esc(s["label"])}</div>' if s.get("label") else ""
    if t == "cover":
        text = label + f'<div class="title t" style="font-size:104px;max-width:860px">{esc(s["title"])}</div>'
    elif t == "room":
        text = label + f'<div class="title t" style="font-size:74px;max-width:860px">{esc(s["title"])}</div>'
    elif t == "photo":
        text = f'<div class="label t">{esc(s["label"])}</div>'
    else:  # last
        tone = "light" if color != B["ink"] else "dark"
        mark = (f'<img class="t" src="logo_{tone}.png" style="width:320px;max-height:180px;object-fit:contain;'
                f'object-position:left;display:block;margin-bottom:38px">' if logo
                else f'<div class="wordmark t" style="margin-bottom:34px">{esc(B["name"])}</div>')
        line = f'<div class="label t" style="margin-bottom:18px">{esc(s["line"])}</div>' if s.get("line") else ""
        text = mark + line + f'<div class="title t" style="font-size:62px">{esc(s["cta"])}</div>'
    return page(f'<img class="bgimg" src="{img}">{scrim(alpha, anchor) if mode == "scrim" else ""}{panel}'
                f'<div class="block" id="blk" style="{pos(anchor)};color:{color}">{text}</div>', B, B["paper"], hide)


def split_slide(s, B, img, fg, hide):
    label = f'<div class="label t" style="margin-bottom:22px">{esc(s["label"])}</div>' if s.get("label") else ""
    inner = (f'<div style="display:flex;flex-direction:column;width:{W}px;height:{H}px">'
             f'<div id="blk" style="padding:{M}px {M}px 44px {M}px;color:{fg};background:{B["paper"]}">{label}'
             f'<div class="title t" style="font-size:64px;margin-bottom:20px">{esc(s["title"])}</div>'
             f'<div class="body t" style="max-width:860px">{esc(s["body"])}</div></div>'
             f'<div style="flex:1;min-height:0"><img src="{img}" style="width:100%;height:100%;object-fit:cover;display:block"></div></div>')
    return page(inner, B, B["paper"], hide)


def diptych_slide(s, B, imgs, fg, hide):
    """Staggered editorial pair: left panel under the title, right panel dropped lower."""
    gw = (W - 2 * M - 28) // 2
    ph = int(gw * 4 / 3)
    label = f'<div class="label t" style="margin-bottom:22px">{esc(s["label"])}</div>' if s.get("label") else ""
    inner = (f'<div class="block" id="blk" style="top:{M}px;color:{fg}">{label}'
             f'<div class="title t" style="font-size:74px">{esc(s["title"])}</div></div>'
             f'<img src="{imgs[0]}" style="position:absolute;left:{M}px;top:350px;width:{gw}px;height:{ph}px;object-fit:cover">'
             f'<img src="{imgs[1]}" style="position:absolute;left:{M + gw + 28}px;top:{H - M - ph}px;width:{gw}px;height:{ph}px;object-fit:cover">')
    return page(inner, B, B["paper"], hide)


def list_slide(s, B, fg, hide):
    """Label pinned top-left; title + rows centred as one group, on the brand accent."""
    line = rgba(fg, .35)
    rows = "".join(
        f'<div class="t" style="display:flex;justify-content:space-between;align-items:baseline;'
        f'padding:28px 0;border-top:1px solid {line}">'
        f'<span class="title" style="font-size:58px;line-height:1">{esc(k)}</span>'
        f'<span class="label" style="font-size:26px">{esc(v)}</span></div>' for k, v in s["rows"])
    label = f'<div class="block" style="top:{M}px;color:{fg}"><div class="label t">{esc(s["label"])}</div></div>' if s.get("label") else ""
    inner = (f'{label}<div class="block" id="blk" style="top:50%;transform:translateY(-44%);color:{fg}">'
             f'<div class="title t" style="font-size:80px;margin-bottom:70px">{esc(s["title"])}</div>'
             f'<div style="border-bottom:1px solid {line}">{rows}</div></div>')
    return page(inner, B, B["accent"], hide)


STAR = ('<svg width="26" height="26" viewBox="0 0 24 24" style="margin-right:12px" aria-hidden="true">'
        '<path fill="currentColor" d="M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.3 5.8 20.9l1.6-7L2 9.2l7.1-.6z"/></svg>')


def review_slide(s, B, fg, hide):
    """A real 5-star guest quote, verbatim, on the brand accent."""
    n = len(s["quote"])
    size = 66 if n <= 110 else 58 if n <= 150 else 52
    label = esc(s.get("label") or "Guest review")
    inner = (f'<div class="block" style="top:{M}px;color:{fg}"><div class="label t">{label}</div></div>'
             f'<div class="block" id="blk" style="top:50%;transform:translateY(-50%);color:{fg}">'
             f'<div class="t" style="display:flex;margin-bottom:40px">{STAR * 5}</div>'
             f'<div class="title t" style="font-size:{size}px;font-weight:500;font-style:italic;line-height:1.16;'
             f'margin-bottom:44px">“{esc(s["quote"])}”</div>'
             f'<div class="label t" style="font-size:24px">{esc(s["_by"])}</div></div>')
    return page(inner, B, B["accent"], hide)


RECT_JS = """(() => { const b = document.getElementById('blk');
  let x0=1e9,y0=1e9,x1=0,y1=0; const add = r => { if (!r.width || !r.height) return;
    x0=Math.min(x0,r.left); y0=Math.min(y0,r.top); x1=Math.max(x1,r.right); y1=Math.max(y1,r.bottom); };
  const tw = document.createTreeWalker(b, NodeFilter.SHOW_TEXT); let n;
  while ((n = tw.nextNode())) { if (!n.textContent.trim()) continue;
    const rg = document.createRange(); rg.selectNodeContents(n); for (const r of rg.getClientRects()) add(r); }
  for (const el of b.querySelectorAll('img,svg')) add(el.getBoundingClientRect());
  return [x0, y0, x1-x0, y1-y0]; })()"""

PANEL_JS = """((r) => { const p = document.getElementById('panel'); if (!p) return false;
  const pad = 36; p.style.left = (r[0]-pad)+'px'; p.style.top = (r[1]-pad)+'px';
  p.style.bottom = 'auto'; p.style.width = (r[2]+2*pad)+'px'; p.style.height = (r[3]+2*pad)+'px'; return true; })"""


# --- render ---------------------------------------------------------------------

class Renderer:
    def __init__(self, pw, work, fonts_js):
        self.br = pw.chromium.launch()
        self.pg = self.br.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        self.work, self.fonts_js, self.n = work, fonts_js, 0

    def shot(self, html_text, panel_fit=False):
        self.n += 1
        f = self.work / f"_r{self.n}.html"
        f.write_text(html_text, encoding="utf-8")
        self.pg.goto(f.as_uri(), wait_until="load")
        if not self.pg.evaluate(self.fonts_js):
            raise RuntimeError("fonts did not load; refusing to render with fallback fonts")
        rect = self.pg.evaluate(RECT_JS)
        if panel_fit:
            self.pg.evaluate(PANEL_JS, rect)
        png = self.work / f"_r{self.n}.png"
        self.pg.screenshot(path=str(png))
        return rect, Image.open(png).convert("RGB")

    def close(self):
        self.br.close()


def choose_photo_layout(R, s, B, img, logo):
    light, dark = hexrgb(B["on_photo"]), hexrgb(B["ink"])
    default = ["top", "mid", "bottom"] if s["t"] == "cover" else ["bottom", "top"]
    order = ([s["prefer"]] if s.get("prefer") else []) + [a for a in default if a != s.get("prefer")]
    tried = []
    for a in order:  # 1) no overlay, either text colour, calm background only
        for col, hexc in ((light, B["on_photo"]), (dark, B["ink"])):
            rect, bg = R.shot(photo_slide(s, B, img, a, hexc, "clean", 0, True, logo))
            r, e = measure(bg, rect, col)
            tried.append((a, "clean", hexc, r, e))
            if r >= MIN_RATIO and e <= BUSY_EDGE:
                return a, hexc, "clean", 0, r, e, len(tried)
    for alpha in ((0.25, 0.4, 0.6) if s["t"] == "last" else (0.25, 0.4)):  # 2) light gradient
        for a in order:
            rect, bg = R.shot(photo_slide(s, B, img, a, B["on_photo"], "scrim", alpha, True, logo))
            r, e = measure(bg, rect, light)
            tried.append((a, f"scrim{alpha}", B["on_photo"], r, e))
            if r >= MIN_RATIO:
                return a, B["on_photo"], "scrim", alpha, r, e, len(tried)
    a = order[0]  # 3) solid paper panel, ink text
    rect, bg = R.shot(photo_slide(s, B, img, a, B["ink"], "panel", 0, True, logo), panel_fit=True)
    r, e = measure(bg, rect, dark)
    return a, B["ink"], "panel", 0, r, e, len(tried) + 1


def gate(plan, pdir):
    """Everything that can fail before a browser starts. Returns (problems, context)."""
    problems = []
    try:
        B = json.loads((pdir / plan["brand"]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"brand: cannot read {plan['brand']}: {e}"], None
    problems += check_brand(B)
    try:
        facts = (pdir / plan["facts"]).read_text(encoding="utf-8")
    except OSError as e:
        return problems + [f"facts: cannot read {plan['facts']}: {e}"], None
    reviews = []
    if plan.get("reviews") and (pdir / plan["reviews"]).exists():
        reviews = json.loads((pdir / plan["reviews"]).read_text(encoding="utf-8"))
    for k, v in check_facts(plan, facts).items():
        problems.append(f"facts: {k}: not in the listing text: {v}")
    for s in plan["slides"]:
        if s["t"] == "review":
            err = check_review(s, reviews)
            if err:
                problems.append(f"review: slide {s['id']}: {err}")
            else:
                match = next(r for r in reviews if norm(r.get("author")) == norm(s["by"]) and r.get("rating") == 5
                             and norm(s["quote"]).strip(" \"'") in norm(r.get("text")))
                s["_by"] = attribution(match)
    problems += [f"voice: {h}" for h in check_voice(plan)]
    for s in plan["slides"]:
        specs = s["photos"] if s["t"] == "diptych" else ([s] if s.get("photo") else [])
        for p in specs:
            f = photo_path(pdir, plan, p["photo"], p.get("source", s.get("source")))
            if not f.exists():
                problems.append(f"photo: slide {s['id']}: {f} not found")
    logo = None
    if B.get("logo"):
        logo = usable_logo((pdir / plan["brand"]).parent / B["logo"])
        if logo is None:
            out(f"note: logo {B['logo']} has no transparent background; using a wordmark instead")
    return problems, {"B": B, "logo": logo}


def build(plan_path, check_only=False):
    plan_path = pathlib.Path(plan_path).resolve()
    pdir = plan_path.parent
    try:
        plan = load_plan(plan_path)
    except PlanError as e:
        out(f"PLAN INVALID:\n{e}")
        return 2
    problems, ctx = gate(plan, pdir)
    if problems:
        out("CHECKS FAILED (nothing rendered):")
        for p in problems:
            out(f"  - {p}")
        return 2
    if check_only:
        out(f"CHECKS PASSED: {len(plan['slides'])} slides, facts, reviews, voice, photos, brand")
        return 0
    B, logo = ctx["B"], ctx["logo"]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    work = pdir / "runs" / f".tmp-{stamp}"
    work.mkdir(parents=True)
    if logo:
        for tone, col in (("light", B["on_photo"]), ("dark", B["ink"])):
            lg = Image.new("RGBA", logo.size, hexrgb(col) + (255,))
            lg.putalpha(logo.split()[3])
            lg.save(work / f"logo_{tone}.png")

    from playwright.sync_api import sync_playwright
    italic = any(s["t"] == "review" for s in plan["slides"])
    look = plan.get("look", "house")
    report, ok_all = [], True
    with sync_playwright() as pw:
        R = Renderer(pw, work, fonts_ok_js(B, italic))
        try:
            for n, s in enumerate(plan["slides"], 1):
                t = s["t"]
                rep = {"slide": n, "id": s["id"], "template": t,
                       "words": " / ".join(str(s[f]) for f in ("label", "title", "cta", "quote") if s.get(f))}
                if t in PHOTO_TEMPLATES:
                    img = f"photo_{n:02d}.jpg"
                    src = photo_path(pdir, plan, s["photo"], s.get("source"))
                    rep["photo"] = str(src.relative_to(pdir)) if src.is_relative_to(pdir) else str(src)
                    rep["soft"] = prep_photo(src, s, W / H, work / img, look)
                    a, col, mode, alpha, r, e, tries = choose_photo_layout(R, s, B, img, logo)
                    rep.update(anchor=a, text=col, mode=mode, overlay=alpha, contrast=r, edge=e, tries=tries)
                    _, final = R.shot(photo_slide(s, B, img, a, col, mode, alpha, False, logo), panel_fit=(mode == "panel"))
                elif t == "split":
                    img = f"photo_{n:02d}.jpg"
                    src = photo_path(pdir, plan, s["photo"], s.get("source"))
                    rep["photo"] = s["photo"]
                    rep["soft"] = prep_photo(src, s, W / (H * 0.66), work / img, look)
                    rect, bg = R.shot(split_slide(s, B, img, B["ink"], True))
                    col, r, e = pick_text_on(bg, rect, [B["ink"], B["on_photo"]])
                    rep.update(text=col, contrast=r)
                    _, final = R.shot(split_slide(s, B, img, col, False))
                elif t == "diptych":
                    imgs = []
                    for k, p in enumerate(s["photos"]):
                        name = f"photo_{n:02d}_{k}.jpg"
                        prep_photo(photo_path(pdir, plan, p["photo"], p.get("source")), p, 3 / 4, work / name, look)
                        imgs.append(name)
                    rect, bg = R.shot(diptych_slide(s, B, imgs, B["ink"], True))
                    col, r, e = pick_text_on(bg, rect, [B["ink"], B["on_photo"]])
                    rep.update(text=col, contrast=r, photos=[p["photo"] for p in s["photos"]])
                    _, final = R.shot(diptych_slide(s, B, imgs, col, False))
                else:  # list, review: flat brand accent, text colour picked by measurement
                    fn = list_slide if t == "list" else review_slide
                    rect, bg = R.shot(fn(s, B, B["ink"], True))
                    col, r, e = pick_text_on(bg, rect, [B["ink"], B["on_photo"]])
                    rep.update(text=col, contrast=r)
                    _, final = R.shot(fn(s, B, col, False))
                rep["passed"] = rep["contrast"] >= MIN_RATIO
                ok_all &= rep["passed"]
                final.resize((W, H), Image.LANCZOS).save(work / f"slide_{n:02d}.jpg", quality=92)
                report.append(rep)
                out(json.dumps(rep))
        finally:
            R.close()

    (work / "caption.txt").write_text(plan["caption"].strip() + "\n", encoding="utf-8")
    fs = sorted(work.glob("slide_*.jpg"))  # preview from the EXPORTED files
    tw, th, cols = 360, 450, 4
    rows = (len(fs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw + (cols - 1) * 10, rows * th + (rows - 1) * 10), "white")
    for i, p in enumerate(fs):
        sheet.paste(Image.open(p).resize((tw, th), Image.LANCZOS), ((i % cols) * (tw + 10), (i // cols) * (th + 10)))
    sheet.save(work / "preview.jpg", quality=90)
    for p in list(work.glob("_r*")) + list(work.glob("photo_*")) + list(work.glob("logo_*")):
        p.unlink()
    (work / "report.json").write_text(json.dumps({"plan": plan_path.name, "passed": ok_all, "slides": report},
                                                 indent=1, ensure_ascii=False), encoding="utf-8")
    final_dir = pdir / "runs" / f"{plan_path.stem}-{stamp}{'' if ok_all else '-FAILED'}"
    work.rename(final_dir)
    soft = [r["slide"] for r in report if r.get("soft")]
    if soft:
        out(f"note: slides {soft} use photos under 1300px wide; they may look soft")
    out(("PASSED" if ok_all else "FAILED (contrast; see report.json)") + f" -> {final_dir}")
    return 0 if ok_all else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan")
    ap.add_argument("--check", action="store_true", help="run the gates only; render nothing")
    a = ap.parse_args(argv)
    return build(a.plan, a.check)


if __name__ == "__main__":
    sys.exit(main())
