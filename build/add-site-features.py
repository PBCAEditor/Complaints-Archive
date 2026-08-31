#!/usr/bin/env python3
"""
Add the remaining site-wide features to every page.

Usage:  python3 add-site-features.py [repo_root]

Adds, where missing:
  * favicon + apple-touch-icon link tags            (all pages)
  * RSS/Atom feed autodiscovery link                (all pages)
  * print stylesheet                                (all pages)
  * skip-to-content link + :focus-visible styles    (all pages)
  * <time datetime> on the byline                   (articles)
  * article:published_time / article:modified_time  (articles)
  * JSON-LD Article structured data                 (articles)

Idempotent: re-running skips anything already present.
Run add-og-and-share.py FIRST on any new page (this script assumes the
Open Graph block is already in place).
"""
import json
import re
import sys
from pathlib import Path

SITE = "https://peabodytrust.co.uk"
SITE_NAME = "Peabody Complaints Archive"
AUTHOR = "David Wood"

# Publication dates. Where the byline gives only a month, the ISO value is
# month-precision (YYYY-MM) so nothing more exact is asserted than the
# article itself claims.
POST_DATES = {
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

POST_IMAGES = {
    "staircase-goes-nowhere.html": "images/staircase-header.jpg",
    "peabody-convicted.html": "images/conviction-header.jpg",
    "leasehold-market-risk.html": "images/leasehold-header.jpg",
    "service-charge-maze.html": "images/service-charge-header.jpg",
    "three-closed-doors.html": "images/three-doors-header.jpg",
}
DEFAULT_IMG = "images/share-default.jpg"

HEAD_LINKS = """  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <link rel="icon" href="/favicon.ico" sizes="32x32">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="alternate" type="application/atom+xml" title="{site} - new articles" href="/feed.xml">
"""

SKIP_AND_PRINT_CSS = """
    /* Skip link and visible focus */
    .skip-link {
      position: absolute; left: -9999px; top: 0;
      background: var(--accent); color: #fff;
      padding: 10px 16px; z-index: 100;
      font: 15px/1.4 system-ui, -apple-system, Arial, sans-serif;
      text-decoration: none;
    }
    .skip-link:focus { left: 0; }
    a:focus-visible, button:focus-visible, input:focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }

    /* Print: strip site furniture, keep the evidence */
    @media print {
      body { background: #fff; color: #000; font-size: 11.5pt; }
      .wrap { max-width: none; padding: 0; }
      nav.site, .share, .backlink, .skip-link,
      .search-wrap, #search-status, #search-results { display: none !important; }
      .disclaimer {
        background: none !important; color: #000 !important;
        border: 1pt solid #000; padding: 6pt 8pt; margin: 0 0 12pt;
        font-size: 9.5pt;
      }
      header.site { border: 0; padding: 0 0 6pt; }
      header.site h1, header.site h1 a { color: #000 !important; font-size: 13pt; }
      footer.site { border-top: 1pt solid #000; font-size: 9pt; color: #000; }
      a { color: #000; text-decoration: underline; }
      article.post a[href^="http"]::after { content: " (" attr(href) ")"; font-size: 8.5pt; }
      img.post-header-image { display: none; }
      .pullquote { border-color: #000; }
      h1, h2, h3 { page-break-after: avoid; }
      p, blockquote, li { orphans: 3; widows: 3; }
      article.post { page-break-before: avoid; }
    }
"""


def build(root: Path):
    files = (
        [root / "index.html"]
        + sorted((root / "pages").glob("*.html"))
        + sorted((root / "posts").glob("*.html"))
    )

    for path in files:
        s = path.read_text(encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        is_post = rel.startswith("posts/")
        changed = []

        # --- head links: favicon + feed ---
        if 'rel="icon"' not in s:
            anchor = '  <link rel="canonical"'
            assert anchor in s, f"run add-og-and-share.py on {rel} first"
            s = s.replace(anchor, HEAD_LINKS.format(site=SITE_NAME) + anchor, 1)
            changed.append("head-links")

        # --- skip link + focus + print CSS ---
        if ".skip-link" not in s:
            css_anchor = "  </style>"
            assert s.count(css_anchor) == 1, f"</style> not unique in {rel}"
            s = s.replace(css_anchor, SKIP_AND_PRINT_CSS + css_anchor, 1)

            body_anchor = "<body>\n"
            assert s.count(body_anchor) == 1, f"<body> not unique in {rel}"
            s = s.replace(
                body_anchor,
                body_anchor + '\n  <a class="skip-link" href="#content">Skip to content</a>\n',
                1,
            )

            # give the main content region the anchor target
            if is_post:
                s = s.replace('<article class="post">', '<article class="post" id="content">', 1)
            else:
                assert s.count("<main>") == 1, f"<main> not unique in {rel}"
                s = s.replace("<main>", '<main id="content">', 1)
            changed.append("skip+print")

        # --- article-only: dates and structured data ---
        if is_post and "application/ld+json" not in s:
            iso = POST_DATES.get(path.name)
            assert iso, f"no publication date recorded for {path.name}"

            # machine-readable byline
            m = re.search(r'(<p class="byline">)(.*?)(</p>)', s, re.S)
            assert m, f"no byline in {rel}"
            label = m.group(2)
            dm = re.search(r"&middot;\s*(.*)$", label.strip(), re.S)
            if dm and "<time" not in label:
                phrase = dm.group(1).strip()
                new_label = label.replace(
                    phrase, f'<time datetime="{iso}">{phrase}</time>', 1
                )
                s = s[: m.start(2)] + new_label + s[m.end(2) :]

            og_anchor = '  <meta property="og:image"'
            assert og_anchor in s, f"og block missing in {rel}"
            s = s.replace(
                og_anchor,
                f'  <meta property="article:published_time" content="{iso}">\n'
                f'  <meta property="article:author" content="{AUTHOR}">\n' + og_anchor,
                1,
            )

            title = re.search(r'<meta property="og:title" content="(.*?)">', s).group(1)
            desc = re.search(r'<meta property="og:description" content="(.*?)">', s).group(1)
            img = POST_IMAGES.get(path.name, DEFAULT_IMG)
            ld = {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": title,
                "description": desc,
                "datePublished": iso,
                "author": {"@type": "Person", "name": AUTHOR},
                "publisher": {"@type": "Organization", "name": SITE_NAME},
                "image": f"{SITE}/{img}",
                "mainEntityOfPage": {
                    "@type": "WebPage",
                    "@id": f"{SITE}/{rel}",
                },
                "isAccessibleForFree": True,
                "inLanguage": "en-GB",
            }
            block = (
                '  <script type="application/ld+json">\n'
                + json.dumps(ld, indent=2, ensure_ascii=False)
                + "\n  </script>\n"
            )
            head_end = "</head>"
            assert s.count(head_end) == 1, f"</head> not unique in {rel}"
            s = s.replace(head_end, block + head_end, 1)
            changed.append("dates+jsonld")

        if changed:
            path.write_text(s, encoding="utf-8")
            print(f"  {rel:38s} + {', '.join(changed)}")
        else:
            print(f"  {rel:38s}   (already done, skipped)")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
