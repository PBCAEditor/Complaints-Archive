#!/usr/bin/env python3
"""
Pre-publication check for the Peabody Complaints Archive.

Usage:
    python3 check-site.py [repo_root]        check the whole site
    python3 check-site.py --draft FILE       check one draft before it is published

Two jobs:

1. Draft mode checks a piece of writing against the site's hard rules
   (briefing section 9): the building name, postcodes, uncensored tribunal
   references, flat numbers, street addresses, Peabody staff names,
   monetisation language, browser storage, and a few things that are easy to
   miss such as unexpanded placeholders. It is NOT a fact-checker.

2. Site mode checks every page for the things that quietly rot: missing
   titles, descriptions, canonicals, H1s, alt text, the disclaimer banner,
   the analytics snippet; plus broken internal links, duplicate element ids,
   malformed JSON-LD, and articles missing from the sitemap, feed or search
   index.

Exit code is 1 if anything BLOCK-level is found, so it can gate a commit.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("This script needs beautifulsoup4:  pip install beautifulsoup4")

SITE = "https://peabodytrust.co.uk"

# ---------------------------------------------------------------- draft rules

DRAFT_RULES = [
    ("Building name (S9.2)", r"goldpence", "BLOCK", 0),
    ("Postcode (S9.2)", r"\b[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}\b", "BLOCK", 0),
    ("Postcode district (S9.2)", r"\b(?:London\s+)?E1\b(?!\d)", "BLOCK", 0),
    ("Uncensored tribunal ref (S9.2)", r"LON/00[A-Z]{2}/[A-Z]{3}/\d{4}/\d{4}", "BLOCK", 0),
    ("Flat/apartment number (S9.2)", r"\b(?:flat|apartment|apt)\s*\.?\s*\d{3}\b", "BLOCK", re.I),
    ("Street address (S9.2)", r"\b\d+[a-z]?\s+[A-Z][a-z]+\s+(?:Street|St|Road|Rd|Lane|Avenue|Ave|Way|Court|Close|Place|Row|Gardens)\b", "BLOCK", 0),
    ("Peabody staff name (S9.3)", r"\b(?:Alex Costello|Nicole St John|Sandra Williams|Russell Plenge|Katie Bond|Ben Siegert|Aisha Saleem|Amy Leveridge|Fola Lawal|Fiona Pickering|Tracy Packer|Katherine Egbuka|Paula Speller|Rohan Gordon|Uche Ibeabueke|Vatel Ntankeu|Sameeullah|Matt Ashton|Gemma Valentine|Scott Lawrence|Victoria Gray|Tamara Fisch|Mei Wang|Martin Watson|Igor Karpov|Emmanuel Adu-Baah)\b", "CHECK", re.I),
    ("Monetisation (S9.4)", r"\b(?:advertise here|sponsored|buy now|donate|for sale|purchase this domain)\b", "CHECK", re.I),
    ("Browser storage (S9.6)", r"localStorage|sessionStorage|document\.cookie|indexedDB", "BLOCK", 0),
    ("'No response' claim (S9.7)", r"no response (?:has been )?(?:was )?received|had not responded|did not respond|declined to comment", "CHECK", re.I),
    ("Unexpanded placeholder", r"\b(?:TBC|TODO|TK|XXX|\[insert|\[name\]|check tenure)", "CHECK", re.I),
    ("Local file path", r"(?:/Users/|C:\\\\|/home/)", "CHECK", 0),
]


# Internal shorthand that must not appear in published copy without explanation.
# This is a watchlist, not a general abbreviation checker: a generic rule flagged
# 31 false positives across the site (CEO, CBE, UNISON, template placeholders,
# capitalised headings) and would have trained everyone to ignore the output.
#
# PCA is deliberately absent. It is the publisher's own name, and the masthead
# and byline carry it in full on every page.
#
# Add a term here when internal shorthand starts leaking into drafts.
INTERNAL_SHORTHAND = {
    # "XYZ": "what it stands for",
}


def unexpanded_initialisms(text, lines):
    """Flag internal shorthand used without being expanded on first use."""
    out = []
    for word in sorted(INTERNAL_SHORTHAND):
        if not re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", text):
            continue
        if f"({word})" in text:
            continue
        ln = next((i for i, l in enumerate(lines, 1) if word in l), 1)
        out.append(("CHECK", f"'{word}' used without being expanded on first use",
                    ln, word, lines[ln - 1].strip()[:110] if ln <= len(lines) else ""))
    return out


def check_draft(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    findings = []

    for sev, label, ln, hit, ctx in unexpanded_initialisms(text, lines):
        findings.append((sev, label, ln, hit, ctx))
    for label, pattern, sev, flags in DRAFT_RULES:
        for i, line in enumerate(lines, 1):
            for m in re.finditer(pattern, line, flags):
                findings.append((sev, label, i, m.group(0), line.strip()[:110]))

    print(f"Checked: {path}\n{len(lines)} lines, {len(text.split())} words\n")
    if not findings:
        print("No rule hits.")
    for sev, label, ln, hit, ctx in sorted(findings, key=lambda f: (f[0] != "BLOCK", f[2])):
        print(f"[{sev}] {label}  line {ln}\n        matched: {hit!r}\n        context: {ctx}\n")
    return any(f[0] == "BLOCK" for f in findings)


# ----------------------------------------------------------------- site rules

def html_files(root):
    out = []
    for pattern in ("index.html", "404.html", "pages/*.html", "posts/*.html",
                    "resources/*.html"):
        out += sorted(root.glob(pattern))
    return [f for f in out if not f.name.startswith("google")]


def check_site(root: Path):
    problems = []

    def bad(sev, page, msg):
        problems.append((sev, str(page), msg))

    files = html_files(root)
    all_paths = {str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file()}

    for f in files:
        rel = f.relative_to(root).as_posix()
        raw = f.read_text(encoding="utf-8")
        soup = BeautifulSoup(raw, "html.parser")
        is_404 = f.name == "404.html"

        if not soup.find("title"):
            bad("BLOCK", rel, "no <title>")
        if not soup.find("meta", attrs={"name": "description"}):
            bad("BLOCK", rel, "no meta description")
        if not is_404 and not soup.find("link", rel="canonical"):
            bad("BLOCK", rel, "no canonical link")
        if not is_404 and not soup.find("meta", property="og:title"):
            bad("CHECK", rel, "no Open Graph tags")

        h1s = soup.find_all("h1")
        if len(h1s) == 0:
            bad("BLOCK", rel, "no <h1>")
        elif len(h1s) > 1:
            bad("BLOCK", rel, f"{len(h1s)} <h1> elements: " +
                ", ".join(h.get_text(strip=True)[:40] for h in h1s))

        page_text = soup.get_text(" ")
        for _, label, _, _, _ in unexpanded_initialisms(page_text, page_text.splitlines()):
            bad("CHECK", rel, label)
        if "not affiliated" not in raw.lower():
            bad("BLOCK", rel, "disclaimer banner missing (S9 rule 1)")
        if "goatcounter" not in raw:
            bad("BLOCK", rel, "GoatCounter snippet missing")
        if re.search(r"localStorage|sessionStorage|document\.cookie", raw):
            bad("BLOCK", rel, "browser storage used (S9 rule 6)")

        for img in soup.find_all("img"):
            if img.get("alt") is None:
                bad("BLOCK", rel, f"img without alt: {img.get('src')}")

        ids = [e["id"] for e in soup.find_all(id=True)]
        for dupe, n in Counter(ids).items():
            if n > 1:
                bad("BLOCK", rel, f"duplicate id '{dupe}' x{n}")

        ld = soup.find("script", type="application/ld+json")
        if ld:
            try:
                json.loads(ld.string or "")
            except Exception as e:
                bad("BLOCK", rel, f"malformed JSON-LD: {e}")

        # third-party loads: analytics is the only one allowed
        for tag in soup.find_all(["script", "link", "img"]):
            url = tag.get("src") or tag.get("href") or ""
            if url.startswith(("http://", "https://", "//")):
                host = urlparse("https:" + url if url.startswith("//") else url).netloc
                if host and "peabodytrust.co.uk" not in host and host != "gc.zgo.at":
                    bad("BLOCK", rel, f"third-party resource loaded from {host}")

        # internal links resolve
        for a in soup.find_all("a", href=True):
            href = a["href"].split("#")[0]
            if not href or href.startswith(("http", "mailto:", "tel:")):
                continue
            target = (href.lstrip("/") if href.startswith("/")
                      else os.path.normpath(os.path.join(f.parent.relative_to(root).as_posix(), href)))
            target = unquote(target).rstrip("/")
            if not target:
                continue
            if target not in all_paths and f"{target}/index.html" not in all_paths \
                    and not (root / target).exists():
                bad("BLOCK", rel, f"broken internal link: {a['href']}")

    # ---- articles present in sitemap, feed and search index
    posts = sorted(p.name for p in (root / "posts").glob("*.html"))
    sm = (root / "sitemap.xml").read_text(encoding="utf-8") if (root / "sitemap.xml").exists() else ""
    fd = (root / "feed.xml").read_text(encoding="utf-8") if (root / "feed.xml").exists() else ""
    try:
        idx = {e["url"].split("/")[-1] for e in json.loads((root / "search-index.json").read_text(encoding="utf-8"))}
    except Exception:
        idx = set()

    for name in posts:
        if f"posts/{name}" not in sm:
            bad("BLOCK", "sitemap.xml", f"article missing: {name}")
        if f"posts/{name}" not in fd:
            bad("BLOCK", "feed.xml", f"article missing: {name}")
        if name not in idx:
            bad("BLOCK", "search-index.json", f"article missing: {name}")

    # ---- stray generated data in the wrong folder
    for stray in (root / "images").glob("*.json"):
        bad("BLOCK", stray.relative_to(root).as_posix(), "generated data in images/ (wrong folder)")

    # ---- guide version markers agree across the three guide files
    gm = root / "resources" / "s21-guide.md"
    if gm.exists():
        md = gm.read_text(encoding="utf-8")
        m = re.search(r"\*\*Version ([\d.]+[LS]?) \(beta\)\..*?Check code ([A-Z0-9]+)\.\*\*", md, re.S)
        if m:
            ver, code = m.groups()
            for other in ("resources/guide.html", "resources/s21-guide.txt"):
                op = root / other
                if op.exists():
                    t = op.read_text(encoding="utf-8")
                    if ver not in t or code not in t:
                        bad("BLOCK", other, f"guide version/check code out of step (expected {ver} / {code})")

    print(f"Checked {len(files)} pages, {len(posts)} articles.\n")
    if not problems:
        print("No problems found.")
        return False
    for sev, page, msg in sorted(problems, key=lambda p: (p[0] != "BLOCK", p[1])):
        print(f"[{sev}] {page}\n        {msg}")
    print(f"\n{sum(1 for p in problems if p[0] == 'BLOCK')} blocking, "
          f"{sum(1 for p in problems if p[0] != 'BLOCK')} to check.")
    return any(p[0] == "BLOCK" for p in problems)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--draft":
        failed = check_draft(args[1])
    else:
        failed = check_site(Path(args[0] if args else "."))
    sys.exit(1 if failed else 0)
