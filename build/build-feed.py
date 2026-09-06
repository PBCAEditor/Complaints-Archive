#!/usr/bin/env python3
"""
Generate feed.xml (Atom 1.0) for the Peabody Complaints Archive.

Usage:  python3 build-feed.py [repo_root]

Reads each article in <repo_root>/posts/, takes its title, description and
publication date, and writes <repo_root>/feed.xml sorted newest first.

Note on dates: Atom requires a full timestamp, so articles whose byline
gives only a month are dated the 1st of that month in the feed. The article
page itself still shows only the month, so nothing more precise is claimed
to readers.
"""
import html
import re
import sys
from pathlib import Path

SITE = "https://peabodytrust.co.uk"
SITE_NAME = "Peabody Complaints Archive"
SUBTITLE = "Service charges, disclosure and accountability in social housing."
AUTHOR = "David Wood"

# ISO date per article; YYYY-MM means month-precision on the page itself.
POST_DATES = {
    "what-does-peabody-have-to-hide.html": "2026-09-05",
    "worst-housing-association.html": "2026-09-04",
    "shared-ownership-incentives.html": "2026-08-25",
    "who-signed-the-letter.html": "2026-08-20",
    "staircase-goes-nowhere.html": "2026-08-20",
    "peabody-convicted.html": "2026-08-16",
    "leasehold-market-risk.html": "2026-08",
    "open-letter-honours.html": "2026-06-15",
    "hclg-written-evidence.html": "2026-04",
    "service-charge-maze.html": "2026-04-02",
    "three-closed-doors.html": "2026-06",
}


# Articles substantively updated since publication. The feed's <updated> uses
# this so readers' feed software sees the revision; <published> keeps the
# original date.
POST_UPDATED = {
    "peabody-convicted.html": "2026-09-04",
    "three-closed-doors.html": "2026-09-01",
}


def full_ts(iso):
    return (iso if len(iso) == 10 else iso + "-01") + "T00:00:00Z"


def build(root: Path):
    entries = []
    for path in sorted((root / "posts").glob("*.html")):
        s = path.read_text(encoding="utf-8")
        iso = POST_DATES.get(path.name)
        if not iso:
            print(f"  ! no date recorded, skipped: {path.name}")
            continue

        title = re.search(r'<meta property="og:title" content="(.*?)">', s).group(1)
        desc = re.search(r'<meta property="og:description" content="(.*?)">', s).group(1)
        url = f"{SITE}/posts/{path.name}"

        entries.append(
            {
                "sort": full_ts(iso),
                "title": html.escape(html.unescape(title), quote=False),
                "summary": html.escape(html.unescape(desc), quote=False),
                "url": url,
                "ts": full_ts(iso),
                "updated": full_ts(POST_UPDATED.get(path.name, iso)),
            }
        )

    entries.sort(key=lambda e: e["sort"], reverse=True)
    updated = max((e["updated"] for e in entries), default="1970-01-01T00:00:00Z")

    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="en-GB">',
        f"  <title>{SITE_NAME}</title>",
        f"  <subtitle>{SUBTITLE}</subtitle>",
        f'  <link href="{SITE}/feed.xml" rel="self" type="application/atom+xml"/>',
        f'  <link href="{SITE}/" rel="alternate" type="text/html"/>',
        f"  <id>{SITE}/</id>",
        f"  <updated>{updated}</updated>",
        f"  <author><name>{AUTHOR}</name></author>",
        "  <rights>This site is independent of Peabody Trust and is not "
        "affiliated with, endorsed by, or operated by Peabody Trust.</rights>",
    ]
    for e in entries:
        out += [
            "  <entry>",
            f'    <title>{e["title"]}</title>',
            f'    <link href="{e["url"]}" rel="alternate" type="text/html"/>',
            f'    <id>{e["url"]}</id>',
            f'    <published>{e["ts"]}</published>',
            f'    <updated>{e["updated"]}</updated>',
            f'    <summary type="text">{e["summary"]}</summary>',
            "  </entry>",
        ]
    out.append("</feed>")

    dest = root / "feed.xml"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nwrote {dest} - {len(entries)} entries, {dest.stat().st_size} bytes")
    for e in entries:
        print(f'  {e["ts"][:10]}  {e["title"][:60]}')


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
