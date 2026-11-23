#!/usr/bin/env python3
"""
Regenerate images/guide-verification.png, the "Version check" image shown on
/resources/.

Usage:  python build/make-verification-image.py [repo_root]

The version numbers and check codes are read from the two markdown files, so the
image cannot disagree with the guide text. It is an image on purpose: an
assistant that never opened the guide cannot copy these values from the page's
text (README section 6).

Requires Pillow (pip install pillow). Fonts: uses Arial, Times New Roman and
Consolas from Windows if present, otherwise DejaVu or Liberation fonts. The
result looks very slightly different on each system, which does not matter.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BG, EDGE = (251, 251, 249), (211, 215, 207)
MAROON, INK, GREY = (110, 38, 57), (21, 24, 27), (118, 125, 132)
W, H = 480, 400

FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu",
             "/usr/share/fonts/truetype/liberation", "/usr/share/fonts/TTF"]


def font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    raise SystemExit("no usable font found for " + names[0])


SANS = ["arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"]
SANS_B = ["arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"]
SERIF_B = ["timesbd.ttf", "DejaVuSerif-Bold.ttf", "LiberationSerif-Bold.ttf"]
MONO_B = ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf"]


def read_values(root: Path):
    full = (root / "resources" / "s21-guide.md").read_text(encoding="utf-8")
    short = (root / "resources" / "s21-guide-compact.md").read_text(encoding="utf-8")
    m = re.search(r"\*\*Version ([\d.]+L) \(beta\)\. Legal sources last verified (.+?)\. Check code ([A-Z0-9]+)\.\*\*", full)
    n = re.search(r"\*\*Version ([\d.]+S) \(beta, short version\)\. Legal sources last verified (.+?)\.", short)
    e = re.search(r"END OF SHORT VERSION\. Check code: ([A-Z0-9]+)\. Version ([\d.]+S)\.", short)
    assert m and n and e, "could not read version and check codes from the markdown"
    assert m.group(2) == n.group(2), "the two guides give different verification dates"
    assert e.group(2) == n.group(1), "short guide: top and bottom versions differ"
    return dict(full_v=m.group(1), full_c=m.group(3), short_v=n.group(1), short_c=e.group(1), date=m.group(2).strip())


def main(root: Path):
    v = read_values(root)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W - 1, H - 1], outline=EDGE)

    head, label, mono = font(SANS_B, 17), font(SANS, 17), font(MONO_B, 29)
    big_serif, small = font(SERIF_B, 26), font(SANS, 16)

    def spaced(x, y, text, f, fill, gap=0.8):
        for ch in text:
            d.text((x, y), ch, font=f, fill=fill, anchor="ls")
            x += f.getlength(ch) + gap

    def block(top, title, ver, code):
        spaced(26, top + 11, title, head, MAROON)
        d.text((26, top + 39), "Version", font=label, fill=GREY, anchor="ls")
        d.text((150, top + 41), ver, font=mono, fill=INK, anchor="ls")
        d.text((26, top + 75), "Check code", font=label, fill=GREY, anchor="ls")
        d.text((150, top + 77), code, font=mono, fill=INK, anchor="ls")

    block(29, "FULL GUIDE", v["full_v"], v["full_c"])
    d.line([26, 128, 454, 128], fill=EDGE)
    block(153, "SHORT VERSION", v["short_v"], v["short_c"])
    d.line([26, 252, 454, 252], fill=EDGE)
    d.text((26, 288), "Legal sources last verified", font=small, fill=GREY, anchor="ls")
    d.text((26, 323), v["date"], font=big_serif, fill=INK, anchor="ls")

    out = root / "images" / "guide-verification.png"
    im.save(out, "PNG", optimize=True)  # no metadata is written
    print("wrote", out, v)


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
