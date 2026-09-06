#!/usr/bin/env python3
"""
Add an "In this article" contents box to long articles, and a visible feed
subscription link to every footer.

Usage:  python3 add-contents-box.py [repo_root]

Idempotent: skips anything already done. Articles below the section threshold
are left alone, because a contents list of three items is clutter rather than
navigation.
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

MIN_SECTIONS = 5   # below this, a contents box is noise

CSS = """    article.post details.contents {
      margin: 26px 0 30px; padding: 14px 0;
      border-top: 2px solid var(--accent); border-bottom: 1px solid var(--rule);
    }
    article.post details.contents summary {
      cursor: pointer; list-style: revert;
      font: 600 13px/1.3 system-ui, -apple-system, Arial, sans-serif;
      letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
    }
    article.post details.contents ol {
      margin: 12px 0 0; padding-left: 20px;
      font: 16px/1.7 system-ui, -apple-system, Arial, sans-serif;
    }
    article.post details.contents li { margin-bottom: 2px; }
    article.post details.contents a { text-decoration: none; }
    article.post details.contents a:hover { text-decoration: underline; }
    @media (min-width: 46rem) {
      article.post details.contents > summary { list-style: none; }
      article.post details.contents > summary::-webkit-details-marker { display: none; }
    }
"""

PRINT_CSS = "      article.post details.contents { display: none; }\n"


def slug(text, seen):
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"\s+", "-", s)[:60] or "section"
    n, out = 2, s
    while out in seen:
        out, n = f"{s}-{n}", n + 1
    seen.add(out)
    return out


def build(root: Path):
    for path in sorted((root / "posts").glob("*.html")):
        s = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()

        # remove any existing box so it is rebuilt from the current headings
        had = 'class="contents"' in s
        if had:
            s = re.sub(r'\n?      <(?:nav|details) class="contents".*?</(?:nav|details)>\n', "\n", s, flags=re.S)

        soup = BeautifulSoup(s, "html.parser")
        article = soup.find("article", class_="post")
        # only headings in the body, not those inside an appendix or notes block
        heads = [h for h in article.find_all("h2")
                 if not h.find_parent(class_=["appendix", "notes", "proposals", "further"])]
        if len(heads) < MIN_SECTIONS:
            print(f"  {rel:44s} ({len(heads)} sections, skipped)")
            continue

        # give each heading an id, in the source rather than the parsed tree,
        # so nothing else about the file changes
        seen, items = set(), []
        for h in heads:
            text = h.get_text(" ", strip=True)
            sid = slug(text, seen)
            items.append((sid, text))
            old = str(h)
            if "id=" not in old:
                new = old.replace("<h2", f'<h2 id="{sid}"', 1)
                assert s.count(old) == 1, f"heading not unique in {rel}: {text[:40]}"
                s = s.replace(old, new, 1)

        box = ('      <details class="contents" open>\n'
               '        <summary>In this article</summary>\n        <ol>\n'
               + "\n".join(f'          <li><a href="#{i}">{t}</a></li>' for i, t in items)
               + "\n        </ol>\n      </details>\n\n")

        # order: title, byline, update, header image, standfirst, contents, body
        img = re.search(r'(      <img src="\.\./images/[^"]+"[^>]*class="post-header-image">\n)', s)
        sf = re.search(r'(      <p class="standfirst">.*?</p>\n)', s, re.S)
        if img and sf and img.start(1) > sf.start(1):
            # image currently sits after the standfirst: move it above
            image_html = img.group(1)
            s = s[:img.start(1)] + s[img.end(1):]
            sf = re.search(r'(      <p class="standfirst">.*?</p>\n)', s, re.S)
            s = s[:sf.start(1)] + image_html + s[sf.start(1):]
            sf = re.search(r'(      <p class="standfirst">.*?</p>\n)', s, re.S)

        sf = re.search(r'(      <p class="standfirst[^"]*">.*?</p>\n)', s, re.S)
        anchor = sf or img \
            or re.search(r'(      <p class="updated">.*?</p>\n)', s, re.S) \
            or re.search(r'(      <p class="byline">.*?</p>\n)', s, re.S)
        s = s[:anchor.end(1)] + box + s[anchor.end(1):]

        css_anchor = "  </style>"
        assert s.count(css_anchor) == 1
        s = s.replace(css_anchor, CSS + css_anchor, 1)
        pm = '      article.post a[href^="http"]::after'
        if pm in s:
            s = s.replace(pm, PRINT_CSS + pm, 1)

        path.write_text(s, encoding="utf-8")
        print(f"  {rel:44s} + contents box ({len(items)} sections)")

    # visible feed link in every footer
    files = ([root / "index.html", root / "404.html"]
             + sorted((root / "pages").glob("*.html"))
             + sorted((root / "posts").glob("*.html")))
    n = 0
    for path in files:
        s = path.read_text(encoding="utf-8")
        if "Subscribe to new articles" in s:
            continue
        m = re.search(r'(<footer class="site">.*?)(<a href="([^"]*)privacy\.html">Privacy</a>)', s, re.S)
        if not m:
            continue
        prefix = m.group(3)
        feed = "./feed.xml" if path.name in ("index.html",) else (
            "/feed.xml" if path.name == "404.html" else "../feed.xml")
        s = s.replace(m.group(2), f'<a href="{feed}">Subscribe to new articles</a> &middot; ' + m.group(2), 1)
        path.write_text(s, encoding="utf-8")
        n += 1
    print(f"\nfeed link added to {n} footers")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
