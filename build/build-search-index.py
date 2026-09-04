#!/usr/bin/env python3
"""
Regenerate search-index.json for the Peabody Complaints Archive.

Usage:  python3 build-search-index.py [repo_root]

Reads every article in <repo_root>/posts/, extracts the text of the
<article class="post"> container, and writes <repo_root>/search-index.json
in the format the homepage search box expects:

    [{"url", "title", "date", "text" (lowercased), "excerpt"}, ...]

Article order matches the order listed in ORDER below, which is the order
the articles appear on the homepage. Add new articles there.
"""
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ORDER = [
    "worst-housing-association.html",
    "shared-ownership-incentives.html",
    "who-signed-the-letter.html",
    "staircase-goes-nowhere.html",
    "peabody-convicted.html",
    "leasehold-market-risk.html",
    "open-letter-honours.html",
    "hclg-written-evidence.html",
    "service-charge-maze.html",
    "three-closed-doors.html",
]

EXCERPT_CHARS = 400


def text_of(node):
    """Collapse a node's visible text to single-spaced plain text."""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def build(root: Path):
    posts_dir = root / "posts"
    names = ORDER + sorted(
        p.name for p in posts_dir.glob("*.html") if p.name not in ORDER
    )

    entries = []
    for name in names:
        path = posts_dir / name
        if not path.exists():
            print(f"  ! skipped (missing): {name}")
            continue

        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        article = soup.find("article", class_="post") or soup.find("article")
        if article is None:
            print(f"  ! skipped (no <article>): {name}")
            continue

        h1 = article.find("h1")
        title = text_of(h1) if h1 else path.stem

        byline_el = article.find(class_="byline")
        byline = text_of(byline_el) if byline_el else ""
        # "By David Wood - Published 16 August 2026" -> "Published 16 August 2026"
        date = byline.split("\u00b7", 1)[1].strip() if "\u00b7" in byline else byline

        full = text_of(article)

        entries.append(
            {
                "url": f"posts/{name}",
                "title": title,
                "date": date,
                "text": full.lower(),
                "excerpt": full[:EXCERPT_CHARS],
            }
        )
        print(f"  indexed: {name} ({len(full)} chars)")

    out = root / "search-index.json"
    out.write_text(
        json.dumps(entries, ensure_ascii=False, indent=None), encoding="utf-8"
    )
    print(f"\nwrote {out} - {len(entries)} articles, {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
