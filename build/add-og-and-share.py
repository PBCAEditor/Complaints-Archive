#!/usr/bin/env python3
"""
Add Open Graph / Twitter card / canonical tags to every page, and a
cookieless share row to each article.

Usage:  python3 add-og-and-share.py [repo_root]

Idempotent: re-running skips pages that already carry the markers.

No third-party scripts, no cookies, no browser storage. Share buttons are
plain <a href> links to each platform's share URL; nothing is contacted
until the reader clicks. The copy-link button uses the clipboard API,
which stores nothing on the device.
"""
import html
import re
import sys
from pathlib import Path

SITE = "https://peabodytrust.co.uk"
SITE_NAME = "Peabody Complaints Archive"
DEFAULT_IMG = "images/share-default.jpg"

# Articles that have their own header image; others fall back to DEFAULT_IMG.
POST_IMAGES = {
    "staircase-goes-nowhere.html": "images/staircase-header.jpg",
    "peabody-convicted.html": "images/conviction-header.jpg",
    "leasehold-market-risk.html": "images/leasehold-header.jpg",
    "service-charge-maze.html": "images/service-charge-header.jpg",
    "three-closed-doors.html": "images/three-doors-header.jpg",
}

OG_MARKER = 'property="og:title"'
SHARE_MARKER = 'class="share"'

SHARE_CSS = """
    /* Share row - plain links, no third-party scripts, no cookies */
    .share {
      margin: 30px 0 4px;
      padding: 18px 0 0;
      border-top: 1px solid var(--rule);
      font: 15px/1.6 system-ui, -apple-system, Arial, sans-serif;
    }
    .share .share-label {
      display: block; margin: 0 0 10px;
      font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase;
      color: #666;
    }
    .share ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px; }
    .share li { margin: 0; }
    .share a, .share button {
      display: inline-block;
      padding: 7px 14px;
      border: 1px solid var(--accent);
      border-radius: 4px;
      color: var(--accent);
      background: transparent;
      text-decoration: none;
      font: inherit;
      cursor: pointer;
    }
    .share a:hover, .share button:hover { background: var(--accent); color: #fff; }
"""

SHARE_HTML = """
    <div class="share">
      <span class="share-label">Share this article</span>
      <ul>
        <li><a href="https://www.facebook.com/sharer/sharer.php?u={url_enc}"
               target="_blank" rel="noopener noreferrer">Facebook</a></li>
        <li><a href="https://wa.me/?text={title_enc}%20{url_enc}"
               target="_blank" rel="noopener noreferrer">WhatsApp</a></li>
        <li><a href="https://www.linkedin.com/sharing/share-offsite/?url={url_enc}"
               target="_blank" rel="noopener noreferrer">LinkedIn</a></li>
        <li><button type="button" class="copy-link" data-url="{url}">Copy link</button></li>
      </ul>
    </div>
"""

COPY_JS = """
  <script>
    document.querySelectorAll('.copy-link').forEach(function (b) {
      b.addEventListener('click', function () {
        var url = b.getAttribute('data-url');
        var done = function () {
          var t = b.textContent;
          b.textContent = 'Link copied';
          setTimeout(function () { b.textContent = t; }, 1800);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done, function () { window.prompt('Copy this link:', url); });
        } else {
          window.prompt('Copy this link:', url);
        }
      });
    });
  </script>
"""


def pct(s):
    """Percent-encode for use inside a URL query string."""
    out = []
    safe = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~"
    for byte in s.encode("utf-8"):
        c = chr(byte)
        out.append(c if c in safe else "%%%02X" % byte)
    return "".join(out)


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
        depth_prefix = "../" if rel != "index.html" else ""

        # --- gather metadata already on the page ---
        raw_title = re.search(r"<title>(.*?)</title>", s, re.S).group(1).strip()
        desc_m = re.search(r'<meta name="description" content="(.*?)">', s, re.S)
        desc = desc_m.group(1).strip() if desc_m else ""

        # og:title drops the trailing site name; the homepage keeps its own
        og_title = re.split(r"\s*&middot;\s*", raw_title)[0].strip()

        url = f"{SITE}/" if rel == "index.html" else f"{SITE}/{rel}"
        img_rel = POST_IMAGES.get(path.name, DEFAULT_IMG) if is_post else DEFAULT_IMG
        img_abs = f"{SITE}/{img_rel}"

        changed = []

        # --- 1. Open Graph / Twitter / canonical ---
        if OG_MARKER not in s:
            tags = (
                f'  <link rel="canonical" href="{url}">\n'
                f'  <meta property="og:type" content="{"article" if is_post else "website"}">\n'
                f'  <meta property="og:site_name" content="{SITE_NAME}">\n'
                f'  <meta property="og:locale" content="en_GB">\n'
                f'  <meta property="og:title" content="{og_title}">\n'
                f'  <meta property="og:description" content="{desc}">\n'
                f'  <meta property="og:url" content="{url}">\n'
                f'  <meta property="og:image" content="{img_abs}">\n'
                f'  <meta property="og:image:width" content="1200">\n'
                f'  <meta property="og:image:height" content="{675 if img_rel != DEFAULT_IMG else 630}">\n'
                f'  <meta name="twitter:card" content="summary_large_image">\n'
                f'  <meta name="twitter:title" content="{og_title}">\n'
                f'  <meta name="twitter:description" content="{desc}">\n'
                f'  <meta name="twitter:image" content="{img_abs}">\n'
            )
            anchor = "  <style>"
            assert s.count(anchor) == 1, f"style anchor not unique in {rel}"
            s = s.replace(anchor, tags + anchor, 1)
            changed.append("og")

        # --- 2. Share row (articles only) ---
        if is_post and SHARE_MARKER not in s:
            css_anchor = "  </style>"
            assert s.count(css_anchor) == 1, f"</style> not unique in {rel}"
            s = s.replace(css_anchor, SHARE_CSS + css_anchor, 1)

            block = SHARE_HTML.format(
                url=html.escape(url, quote=True),
                url_enc=pct(url),
                title_enc=pct(html.unescape(og_title)),
            )
            backlink = '    <p class="backlink">'
            assert s.count(backlink) == 1, f"backlink not unique in {rel}"
            s = s.replace(backlink, block + "\n" + backlink, 1)

            body_end = "</body>"
            assert s.count(body_end) == 1, f"</body> not unique in {rel}"
            s = s.replace(body_end, COPY_JS + body_end, 1)
            changed.append("share")

        if changed:
            path.write_text(s, encoding="utf-8")
            print(f"  {rel:38s} + {', '.join(changed)}")
        else:
            print(f"  {rel:38s}   (already done, skipped)")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
