#!/usr/bin/env python3
"""
Add an "In this article" contents box to long articles, a sign-up box to the end
of every article, and "Email updates" and "RSS feed" links to every footer.

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

# Sign-up page for the email list (Buttondown). A plain link: the browser makes
# no request to Buttondown unless the reader clicks it.
EMAIL_URL = "https://buttondown.com/pbcaeditor"
EMAIL_LINK = f'<a href="{EMAIL_URL}" target="_blank" rel="noopener noreferrer">Email updates</a>'

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

# Sign-up box at the end of every article (between the article and the share row).
# The homepage has its own hand-written copy of this box in index.html.
SIGNUP_CSS = """    section.emailupdates {
      margin: 30px 0 0; padding: 16px 20px 14px;
      border: 1px solid var(--rule); border-left: 4px solid var(--accent);
      background: #f6f2ea;
      font: 16px/1.55 system-ui, -apple-system, Arial, sans-serif;
    }
    section.emailupdates h2 { font: 600 17px/1.4 system-ui, -apple-system, Arial, sans-serif; margin: 0 0 6px; }
    section.emailupdates p { margin: 0 0 10px; }
    section.emailupdates p:last-child { margin-bottom: 0; }
    section.emailupdates form.signup { margin: 0 0 10px; }
    section.emailupdates form.signup label { display: block; font-weight: 600; font-size: 14px; margin: 0 0 4px; }
    section.emailupdates .signup-row { display: flex; gap: 8px; flex-wrap: wrap; }
    section.emailupdates input[type="email"] {
      flex: 1 1 220px; min-width: 0; padding: 9px 12px;
      font: 16px/1.4 system-ui, -apple-system, Arial, sans-serif;
      border: 1px solid #b9b9b9; border-radius: 5px; background: #fff; color: var(--ink);
    }
    section.emailupdates button {
      padding: 9px 18px; font: 600 16px/1.4 system-ui, -apple-system, Arial, sans-serif;
      background: var(--accent); color: #fff; border: 0; border-radius: 5px; cursor: pointer;
    }
    section.emailupdates button:hover { text-decoration: underline; }
    @media print { section.emailupdates { display: none !important; } }
"""

SIGNUP_BOX = f"""    <section class="emailupdates" aria-labelledby="email-updates-heading">
      <h2 id="email-updates-heading">New articles by email</h2>
      <p>Get a short email when a new article is published. Sign-up is run by Buttondown, a US email service: when you press Subscribe, your address is sent to Buttondown, which emails you to confirm it. Every email has an unsubscribe link, and your address is used for nothing else. See the <a href="../pages/privacy.html#email-updates">privacy notice</a>.</p>
      <form class="signup" action="https://buttondown.com/api/emails/embed-subscribe/pbcaeditor" method="post" target="_blank">
        <label for="signup-email">Your email address</label>
        <span class="signup-row">
          <input type="email" name="email" id="signup-email" required autocomplete="email" placeholder="you@example.com">
          <button type="submit">Subscribe</button>
        </span>
      </form>
      <p>Or follow the <a href="../feed.xml">RSS feed</a> in a feed reader.</p>
    </section>
"""


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
            s = re.sub(r'\n?      <(?:nav|details) class="contents".*?</(?:nav|details)>\n+', "\n", s, flags=re.S)

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

        box = ('      <details class="contents">\n'
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
        if CSS not in s:
            s = s.replace(css_anchor, CSS + css_anchor, 1)
        pm = '      article.post a[href^="http"]::after'
        if pm in s and PRINT_CSS not in s:
            s = s.replace(pm, PRINT_CSS + pm, 1)

        path.write_text(s, encoding="utf-8")
        print(f"  {rel:44s} + contents box ({len(items)} sections)")

    # sign-up box at the end of every article (newline style kept per file)
    m_added = 0
    for path in sorted((root / "posts").glob("*.html")):
        with open(path, encoding="utf-8", newline="") as fh:
            s = fh.read()
        if 'class="emailupdates"' in s:
            continue
        nl = "\r\n" if "\r\n" in s else "\n"
        end_art, end_css = "    </article>" + nl, "  </style>"
        if s.count(end_art) != 1 or s.count(end_css) != 1:
            print(f"  WARNING {path.name}: could not place the sign-up box")
            continue
        s = s.replace(end_art, end_art + nl + SIGNUP_BOX.replace("\n", nl), 1)
        s = s.replace(end_css, SIGNUP_CSS.replace("\n", nl) + end_css, 1)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(s)
        m_added += 1
    print(f"\nsign-up box added to {m_added} articles")

    # "Email updates" and "RSS feed" links in every footer. Files are read and
    # written with newline="" so each file keeps its own line endings.
    files = ([root / "index.html", root / "404.html"]
             + sorted((root / "pages").glob("*.html"))
             + sorted((root / "posts").glob("*.html"))
             + sorted((root / "evidence").glob("*.html"))
             + sorted((root / "resources").rglob("*.html")))
    n = 0
    for path in files:
        with open(path, encoding="utf-8", newline="") as fh:
            s = fh.read()
        if "Email updates</a>" in s:
            continue
        rss = re.search(r'<a href="[^"]*feed\.xml">RSS feed</a>', s)
        if rss:
            s = s[:rss.start()] + EMAIL_LINK + " &middot; " + s[rss.start():]
        else:
            m = re.search(r'(<footer class="site">.*?)(<a href="[^"]*privacy\.html">Privacy</a>)', s, re.S)
            if not m:
                continue
            rel = path.relative_to(root).parts
            if rel[0] in ("resources", "evidence") or path.name == "404.html":
                feed = "/feed.xml"
            elif path.name == "index.html":
                feed = "./feed.xml"
            else:
                feed = "../feed.xml"
            s = (s[:m.start(2)] + EMAIL_LINK + f' &middot; <a href="{feed}">RSS feed</a> &middot; '
                 + s[m.start(2):])
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(s)
        n += 1
    print(f"\nemail and feed links added to {n} footers")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
