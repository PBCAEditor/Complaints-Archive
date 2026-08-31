#!/usr/bin/env python3
"""
Build the Support & resources pages from the guide markdown.

Usage:  python3 build-guide-page.py [repo_root]

Produces, from <repo_root>/resources/s21-guide.md:
  /resources/index.html   landing page: two-column hero, verification stamp,
                          assistant prompt, how-to steps, closing warning.
  /resources/guide.html   the full guide with a sticky sidebar contents list.

Both link /resources/style.css, which is shared by this section only. The rest
of the site keeps its inline per-page CSS: this section is a tool rather than a
blog and is allowed to look different.

The markdown stays at /resources/s21-guide.md. That address is inside the
assistant prompt and must not move.

Rendered at build time. No third-party fonts, scripts or CDNs; the only external
request either page makes is the GoatCounter snippet.
"""
import html
import re
import sys
from pathlib import Path

import markdown

SITE = "https://peabodytrust.co.uk"
GUIDE_TEXT_URL = f"{SITE}/resources/s21-guide.txt"
GUIDE_PAGE_URL = f"{SITE}/resources/guide.html"
LANDING_URL = f"{SITE}/resources/"
GUIDE_URL = f"{SITE}/resources/guide.html"

ASSISTANT_PROMPT = f"""Please open and read this document:
{GUIDE_TEXT_URL}

It is a resident-written guide to requesting service charge information under sections 21, 22 and 23 of the Landlord and Tenant Act 1985. I am giving it to you as reference material.

When you have read it, tell me the version number and legal verification date shown at the top, then ask me which stage I am at.

If you cannot open it, tell me that you cannot and rely on the shorter text below instead. In that case, also tell me I can read the full guide at {GUIDE_PAGE_URL}

Below this message is a shorter version of the same guide. (If I have attached it as a file instead, please read that.) I am giving it to you as reference material for this conversation."""


HEAD = """<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} &middot; Peabody Complaints Archive</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{url}">
<link rel="stylesheet" href="/resources/style.css">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="alternate" type="application/atom+xml" title="Peabody Complaints Archive - new articles" href="/feed.xml">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Peabody Complaints Archive">
<meta property="og:locale" content="en_GB">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://peabodytrust.co.uk/images/share-default.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="https://peabodytrust.co.uk/images/share-default.jpg">
<script data-goatcounter="https://pbcaeditor.goatcounter.com/count"
        async src="//gc.zgo.at/count.js"></script>
</head>
<body>

<a class="skip-link" href="#content">Skip to content</a>

<div class="disclaimer">
  This site is not affiliated with, endorsed by, or operated by Peabody Trust. It is written and run by residents.
</div>

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="/">Peabody Complaints Archive <span>/ Support &amp; resources</span></a>
    <span class="vchip">Beta &middot; verified {verified}</span>
  </div>
</header>

<nav class="site" aria-label="Site">
  <div class="wrap">
    <a href="/">Home</a>
    <a href="/resources/"{res_current}>Support &amp; resources</a>
    <a href="/pages/about.html">About</a>
    <a href="/pages/editorial-policy.html">Editorial policy</a>
    <a href="/pages/corrections.html">Corrections &amp; right of reply</a>
    <a href="/pages/contact.html">Contact</a>
  </div>
</nav>

<main id="content">
"""

FOOT = """</main>

<footer class="site">
  <div class="wrap">
    <p>Written and run by residents. Independent of Peabody Trust.</p>
    <p><a href="/pages/privacy.html">Privacy</a> &middot; <a href="/pages/terms.html">Terms</a> &middot; <a href="/pages/disclaimer.html">Legal disclaimer</a> &middot; <a href="/pages/corrections.html">Corrections &amp; right of reply</a></p>
  </div>
</footer>
"""

COPY_JS = """
<script>
(function () {
  var btn = document.getElementById('copyBtn');
  var echo = document.getElementById('copyEcho');
  var src = document.getElementById('promptText');
  var gsrc = document.getElementById('guideSource');
  if (!btn || !src || !gsrc) return;
  btn.addEventListener('click', function () {
    var text = src.textContent.trim() + '\\n\\n----- GUIDE TEXT BEGINS -----\\n\\n' + gsrc.textContent.trim();
    function ok() {
      echo.textContent = 'Prompt and guide copied';
      btn.textContent = 'Copied';
      setTimeout(function () {
        btn.textContent = btn.dataset.label;
        echo.textContent = '';
      }, 2600);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(ok, function () {
        echo.textContent = 'Could not copy. Download the plain text instead.';
      });
    } else {
      echo.textContent = 'Could not copy. Download the plain text instead.';
    }
  });
})();
</script>
"""

GUIDE_COPY_JS = """
<script>
(function () {
  var btn = document.getElementById('copyGuideBtn');
  var echo = document.getElementById('copyGuideEcho');
  var doc = document.querySelector('article.doc');
  if (!btn || !doc) return;
  function guideText() {
    var clone = doc.cloneNode(true);
    var drop = clone.querySelectorAll('.final-warning');
    for (var i = 0; i < drop.length; i++) { drop[i].parentNode.removeChild(drop[i]); }
    return (clone.innerText || clone.textContent).replace(/\\n{3,}/g, '\\n\\n').trim();
  }
  function done(msg) {
    echo.textContent = msg;
    btn.textContent = 'Copied';
    setTimeout(function () {
      btn.textContent = btn.dataset.label;
      echo.textContent = '';
    }, 2600);
  }
  btn.addEventListener('click', function () {
    var text = guideText();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        function () { done('Guide copied. Now paste it into your assistant.'); },
        function () { echo.textContent = 'Could not copy. Use Download plain text instead.'; });
    } else {
      echo.textContent = 'Could not copy. Use Download plain text instead.';
    }
  });
})();
</script>
"""

WARNING = """
    <section class="final-warning" aria-labelledby="warning-heading">
      <h2 id="warning-heading">Before you rely on any of this</h2>

      <p><strong>This is not legal advice.</strong> It is information, written by residents rather than lawyers, and it cannot take account of your lease, your tenancy, your landlord, or anything unusual about your situation. Every lease is different. Nothing here creates a professional relationship of any kind, and no responsibility is accepted for what you do with it.</p>

      <p><strong>AI assistants get things wrong, confidently.</strong> This guide is designed to make an assistant more accurate. It cannot make one reliable. AI is a useful tool but you should verify what it says.</p>

      <p>The specific things to watch for:</p>
      <ul>
        <li>Claiming to have read a document, a statute or a web page it has not opened.</li>
        <li>Inventing citations, case names, section numbers or web addresses that look entirely plausible.</li>
        <li>Getting date arithmetic wrong, which matters here because your deadline depends on it.</li>
        <li>Quoting the wrong version of section 21. The live legislation.gov.uk page for it shows a version that is not in force, and assistants fall into this repeatedly.</li>
        <li>Dropping required wording from a letter because it reads like boilerplate.</li>
        <li>Stating an uncertain interpretation as though it were settled law.</li>
      </ul>

      <p><strong>Check everything that matters yourself.</strong> Open the legislation and confirm the provision is still in force. Check every date and figure against your own lease, demands and statements. Compare any letter you are given against the model wording in the guide before you send it. If an assistant cannot quote the version number exactly, it has not read this guide and you should not act on what it tells you.</p>

      <p><strong>Where to get help that is not AI-generated.</strong> The Social Housing Action Campaign publishes a substantial library of resident guides, written by people, at <a href="https://shaction.org/resources/" target="_blank" rel="noopener noreferrer">shaction.org/resources</a>. That includes <em>Guide and Templates: Requesting Service Charge Information</em>, the 2026 SHAC guide this page is based on. If you would rather not involve an AI assistant at all, use that document instead. It covers the same ground and no model sits between you and it.</p>

      <p>For advice on your own circumstances, the Leasehold Advisory Service (LEASE) gives free initial advice to leaseholders, and a solicitor or advice agency can advise where the facts are unusual or the consequences are significant. Where the law is unclear or the stakes are high, take advice before you act.</p>
    </section>
"""


def strip_front_matter(md):
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4:].lstrip("\n")
    return md


def slug(text, seen):
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    s = re.sub(r"\s+", "-", s)[:60] or "section"
    n, out = 2, s
    while out in seen:
        out, n = f"{s}-{n}", n + 1
    seen.add(out)
    return out


def build(root: Path):
    md_path = root / "resources" / "s21-guide.md"
    body_md = strip_front_matter(md_path.read_text(encoding="utf-8"))

    ver = re.search(
        r"\*\*Version ([\d.]+[LS]?) \(beta\)\. Legal sources last verified (.+?)\. Check code ([A-Z0-9]+)\.\*\*",
        body_md,
    )
    assert ver, "could not read version / date / check code from the guide markdown"
    check_code = ver.group(3)
    version, verified = ver.group(1), ver.group(2).strip()
    short_date = re.sub(r"(\d+) (\w{3})\w* (\d{4})", r"\1 \2 \3", verified)

    rendered = markdown.markdown(
        body_md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
        output_format="html5",
    )
    seen, toc = set(), []

    def add_id(m):
        lvl, attrs, text = m.group(1), m.group(2), m.group(3)
        plain = re.sub(r"<[^>]+>", "", text)
        sid = slug(plain, seen)
        if lvl == "2":
            toc.append((sid, plain))
        return f'<h{lvl} id="{sid}"{attrs}>{text}</h{lvl}>'

    rendered = re.sub(r"<h([1-4])([^>]*)>(.*?)</h\1>", add_id, rendered, flags=re.S)
    # the page supplies its own H1, so remove the document's duplicate top-level title
    rendered = re.sub(r"\s*<h1[^>]*>.*?</h1>\s*", "\n", rendered, count=1, flags=re.S)
    toc_html = "\n".join(
        f'          <li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in toc
    )

    txt_header = (
        "Requesting Service Charge Information under ss.21-23 LTA 1985\n"
        "Peabody Complaints Archive - independent and resident-run\n"
        f"Plain-text copy. Human-readable page: {GUIDE_PAGE_URL}\n"
        "\n" + "-" * 70 + "\n\n"
    )
    txt_kb = round((len(txt_header) + len(body_md)) / 1024)
    compact_path = root / "resources" / "s21-guide-compact.md"
    compact = compact_path.read_text(encoding="utf-8")
    if compact.startswith("---"):
        e = compact.find("\n---", 3)
        if e != -1:
            compact = compact[e + 4:].lstrip("\n")
    guide_plain = html.escape(compact)
    compact_kb = round(len(compact) / 1024)

    def head(title, desc, url, current=""):
        return HEAD.format(title=title, desc=desc, url=url,
                           verified=short_date, res_current=current)

    landing = head(
        "Requesting Service Charge Information under ss.21-23 LTA 1985",
        "A guide for residents in England and Wales requesting service charge information "
        "under sections 21, 22 and 23 of the Landlord and Tenant Act 1985. Written to be "
        "used with an AI assistant.",
        LANDING_URL, ' aria-current="page"',
    ) + f'''
  <section class="hero">
    <div class="wrap hero-grid">
      <div>
        <p class="eyebrow">Landlord and Tenant Act 1985, ss.21&ndash;23</p>
        <h1>Ask your landlord what they <em>actually spent</em></h1>
        <p class="standfirst">If your service charge goes up and down with your landlord's costs, you can require a written summary of those costs, and then inspect the invoices and receipts behind it. This guide covers making the request, working out the deadline, and checking whether what comes back is good enough.</p>
        <p class="standfirst">It is written to be handed to an AI assistant, which drafts and checks alongside you. You can also just read it.</p>
        <div class="btn-row">
          <a class="btn btn-primary" href="/resources/guide.html">Read the full guide</a>
          <a class="btn" href="/resources/s21-guide.txt" download="s21-guide.txt">Download plain text <small>{txt_kb} KB</small></a>
        </div>
      </div>

      <aside class="stamp" aria-label="Guide version and verification date">
        <div class="stamp-head">
          <strong>Version check</strong>
          <span class="stamp-beta">Beta</span>
        </div>
        <img class="stamp-img" src="/images/guide-verification.png" alt="Version check. Version numbers and check codes for both the full guide and the short version, shown as an image so they cannot be copied from this page's text. The full guide is version 0.2.5.4.3.7L, the short version 0.2.5.4.3.7S; each carries its own check code at the end of the document. Legal sources last verified 29 August 2026.">
        <dl>
          <dt>Jurisdiction</dt><dd>England &amp; Wales</dd>
          <dt>Based on</dt><dd>SHAC guide, 2026</dd>
          <dt>Publisher</dt><dd>Peabody Complaints Archive, resident-run</dd>
        </dl>
        <p class="stamp-note">The versions, codes and date are an image on purpose. The version number is deliberately long and arbitrary, so it cannot be guessed or rounded off. An assistant that has genuinely opened the guide can reproduce it exactly; one that has only seen this page in a search result cannot. Using a screen reader? Both values are in the first lines of <a href="/resources/guide.html">the guide</a>.</p>
      </aside>
    </div>
  </section>

  <section class="guide-section">
    <div class="wrap">
      <p class="eyebrow">Start here</p>
      <h2 class="block-title">Use it with an AI assistant</h2>
      <p style="max-width:var(--measure);color:var(--ink-soft);margin:0 0 .4rem">One prompt, one button. It asks your assistant to open the full guide, and carries a shorter version of the guide with it in case it cannot.</p>
    </div>

    <div class="wrap route-grid">

      <div class="route-prompt">
        <div class="btn-row">
          <button class="btn btn-primary" id="copyBtn" data-label="Copy the prompt">Copy the prompt</button>
          <span class="eyebrow" id="copyEcho" aria-live="polite"></span>
        </div>
        <div class="promptbox">
          <div class="promptbox-head"><span class="eyebrow">Assistant prompt</span><span class="eyebrow">short version appended on copy</span></div>
          <pre id="promptText">{html.escape(ASSISTANT_PROMPT)}</pre>
        </div>
        <script type="text/plain" id="guideSource">{guide_plain}</script>
      </div>

      <div class="route-steps">
        <p class="eyebrow">How to use it</p>
        <ol class="steps">
          <li>Select <strong>Copy the prompt</strong>. A short version of the guide is copied with it, so it works whether or not your assistant can open web pages.</li>
          <li>Open your AI assistant and start a new conversation.</li>
          <li>Paste and send. It is a long message, which is expected.</li>
          <li>Check that it quotes back a <strong>version number</strong> and a <strong>check code</strong> from the block above. Compare both character by character.</li>
          <li>Either pair is a pass. Codes ending in <strong>L</strong> mean it opened the full guide. Codes for the <strong>short version</strong> mean it is working from the abridged copy pasted with your prompt, so check the full guide yourself if your situation is unusual.</li>
          <li>If neither pair comes back, or a code is shortened or altered, it has not read the guide properly. Do not rely on what it tells you.</li>
          <li>Say whether you are preparing a request, waiting for a response, or reviewing something your landlord has sent.</li>
        </ol>
        <p class="route-note">The version number sits at the top of each guide and the check code at the very end, so quoting both shows the assistant received the whole document rather than the first part of it. The two documents carry different markers, which is how you can tell which one it read. Prefer a file? <a href="/resources/s21-guide.txt" download="s21-guide.txt">Download the full guide as plain text</a> and attach it instead.</p>
      </div>

    </div>

    <div class="wrap wrap-narrow">
{WARNING}
    </div>
  </section>

{FOOT}{COPY_JS}
</body>
</html>
'''

    guide_page = head(
        "The guide: requesting service charge information under ss.21-23 LTA 1985",
        f"The full text of the resident guide to requesting service charge information "
        f"under sections 21, 22 and 23 of the Landlord and Tenant Act 1985. "
        f"Version {version}, last verified {verified}.",
        GUIDE_URL,
    ) + f'''
  <section class="hero">
    <div class="wrap">
      <p class="eyebrow"><a href="/resources/">Support &amp; resources</a> &middot; The guide</p>
      <h1>Requesting service charge information</h1>
      <p class="standfirst">The complete guide to sections 21 to 23 of the Landlord and Tenant Act 1985. To use it with an AI assistant, start from the <a href="/resources/">Support &amp; resources page</a>, which has the prompt and the verification block.</p>
      <div class="btn-row">
        <button class="btn btn-primary" id="copyGuideBtn" data-label="Copy the whole guide">Copy the whole guide</button>
        <a class="btn" href="/resources/s21-guide.txt" download="s21-guide.txt">Download plain text <small>{txt_kb} KB</small></a>
        <a class="btn" href="/resources/">Back to Support &amp; resources</a>
        <span class="eyebrow" id="copyGuideEcho" aria-live="polite"></span>
      </div>
    </div>
  </section>

  <section class="guide-section">
    <div class="wrap guide-layout">
      <nav class="toc" aria-label="Guide contents">
        <h2 class="toc-title">Contents</h2>
        <ol>
{toc_html}
        </ol>
      </nav>

      <article class="doc">
{rendered}
{WARNING}
      </article>
    </div>
  </section>

{FOOT}{GUIDE_COPY_JS}
</body>
</html>
'''

    # plain-text copy: no YAML front matter, so Jekyll leaves it alone even if
    # .nojekyll is missing or misnamed. This is the file an assistant can be
    # given directly, and the one people download to attach to a conversation.
    (root / "resources" / "s21-guide.txt").write_text(txt_header + body_md, encoding="utf-8")

    (root / "resources" / "index.html").write_text(landing, encoding="utf-8")
    (root / "resources" / "guide.html").write_text(guide_page, encoding="utf-8")
    print(f"  resources/index.html  {len(landing)/1024:5.1f} KB  landing")
    print(f"  resources/guide.html  {len(guide_page)/1024:5.1f} KB  full guide, {len(toc)} sections")
    print(f"  version {version}, verified {verified}")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
