#!/usr/bin/env python3
"""
Build the four section 25 prosecution guide pages from their markdown.

Usage:  python build/build-prosecution-pages.py [repo_root]

Reads  build/prosecution/{main,guilty,not-guilty,costs}.md
Writes resources/prosecution/index.html                       the main guide
       resources/prosecution/if-they-plead-guilty.html
       resources/prosecution/if-they-plead-not-guilty.html
       resources/prosecution/costs.html

The downloadable Word files are made separately by split-prosecution-docs.py and
live in resources/prosecution/downloads/. Any link to a .docx in the markdown gets
a download attribute and the file's size added, so the size is always right.

Look, header, footer and stylesheet are shared with the s21 guide pages
(build-guide-page.py). Published URLs never change (README section 10).
"""
import html
import importlib.util
import re
import sys
from pathlib import Path

import markdown

sys.dont_write_bytecode = True  # importing the s21 builder must not leave a __pycache__ in the repo
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("bgp", HERE / "build-guide-page.py")
bgp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bgp)

SITE = bgp.SITE
REVIEWED = "November 2026"

PAGES = [
    dict(
        md="main.md", out="index.html", path="/resources/prosecution/",
        nav="Main guide",
        title="Guide to Private Prosecutions under Section 25",
        eyebrow_tail="Section 25 prosecution",
        h1="Guide to Private Prosecutions under Section 25",
        sub="of the Landlord and Tenant Act 1985",
        stand="How to decide whether you have a case, apply to the magistrates' court for a summons, "
              "serve the papers on your landlord and prepare for the first hearing, with checklists and "
              "model documents you can download and adapt.",
        desc="A resident-written guide to privately prosecuting a landlord under section 25 of the Landlord "
             "and Tenant Act 1985 for failing to provide service charge information: summons, service, "
             "the first hearing, with downloadable checklists and model documents.",
    ),
    dict(
        md="guilty.md", out="if-they-plead-guilty.html", path="/resources/prosecution/if-they-plead-guilty.html",
        nav="If They Plead Guilty",
        title="If They Plead Guilty",
        eyebrow_tail="Section 25 prosecution",
        h1="If They Plead Guilty",
        sub="A companion to our Guide to Private Prosecutions under Section 25",
        stand="What happens if the landlord admits the offence at the first hearing: outlining the facts to the "
              "court, sentencing, applying for your costs and getting a formal record of the conviction.",
        desc="What a private prosecutor does if the landlord pleads guilty to a section 25 offence: outlining the "
             "facts, sentencing, costs and obtaining a Memorandum of Conviction.",
    ),
    dict(
        md="not-guilty.md", out="if-they-plead-not-guilty.html", path="/resources/prosecution/if-they-plead-not-guilty.html",
        nav="If They Plead Not Guilty",
        title="If They Plead Not Guilty",
        eyebrow_tail="Section 25 prosecution",
        h1="If They Plead Not Guilty",
        sub="Your working document for the plea hearing and case management",
        stand="A working booklet to print and bring to the first hearing. It helps you record what is disputed, "
              "what is agreed, who needs to give evidence and every deadline the court sets, and includes "
              "model directions you can hand to the court.",
        desc="A printable working booklet for a private prosecutor at the plea hearing of a section 25 case when "
             "the landlord pleads not guilty, with model proposed trial directions.",
    ),
    dict(
        md="costs.md", out="costs.html", path="/resources/prosecution/costs.html",
        nav="Prosecution costs",
        title="Prosecution costs",
        eyebrow_tail="Section 25 prosecution",
        h1="Prosecution costs",
        sub="Claiming back what the prosecution cost you",
        stand="How to claim back what the prosecution cost you if the landlord is convicted: your out-of-pocket "
              "expenses and, if the court allows it, your time. Includes a model costs schedule.",
        desc="How a private prosecutor claims costs after a section 25 conviction: expenses, time, proportionality "
             "and the risk of a costs order if the prosecution fails, with a model costs schedule.",
    ),
]

RELATED_NOTE = (
    '<section class="final-warning" aria-labelledby="warning-heading">'
    '<h2 id="warning-heading">Before you rely on this</h2>'
    "<p><strong>This is not legal advice.</strong> These guides are written by residents, not lawyers. They are "
    "based on one prosecution, brought in the London magistrates' courts in 2026. Other courts may handle things "
    "differently, and court procedures and forms change. Check anything important against the current law and "
    "court rules, and take legal advice if you are unsure, especially before you apply for a summons, if your "
    "landlord disputes the case, or if it is going to trial. See also "
    '<a href="/resources/#before-you-use-these-guides">Before you use these guides</a>.</p>'
    "<p>A private prosecution is a serious step. You take on the duties of a prosecutor, and in some "
    "circumstances a court can order a prosecutor to pay the defendant's costs. The "
    '<a href="/resources/prosecution/">main guide</a> and <a href="/resources/prosecution/costs.html">Prosecution '
    "costs</a> explain how to avoid that.</p>"
    "<p>The Leasehold Advisory Service (LEASE) gives free legal advice on leasehold law, including service "
    'charges: <a href="https://www.lease-advice.org" target="_blank" rel="noopener noreferrer">lease-advice.org</a>. '
    "For court procedure, speak to a solicitor. We cannot advise on individual cases.</p>"
    "</section>"
)


HUB_TITLE = "Service charge information and private prosecution: the guides"
HUB_DESC = ("If you pay a variable service charge, the law lets you ask your landlord for a summary of the costs "
            "behind it. If it fails to comply without a reasonable excuse, you can prosecute it yourself. "
            "Resident-written guides, with model documents you can adapt.")

# (title, url or None, description, use-when line, extra links)
HUB_GUIDES = [
    ("Requesting service charge information", "/resources/requesting/",
     "Start here. How to ask your landlord for a summary of service charge costs (section 21) and to inspect the "
     "supporting accounts and receipts (section 22), with model request letters and how to work out the deadline. "
     "You can read it yourself or give it to an AI assistant; it includes instructions telling the assistant how "
     "to help you.",
     "Use it when you want information about your service charge, or when you may want to prosecute later and "
     "need a valid request to start from.",
     [("Read the full guide", "/resources/guide.html")]),
    ("Guide to Private Prosecutions under Section 25", "/resources/prosecution/",
     "The main guide. How to decide whether you have a case, apply to the magistrates' court for a summons, serve "
     "the papers on your landlord and prepare for the first hearing. It includes checklists and model documents: "
     "a completed summons application, a certificate of service, the Initial Details of the Prosecution Case, a "
     "witness statement and a written argument.",
     "Use it when you made a valid request, the deadline has passed and the landlord has not complied. Check the "
     "six-month time limit first.", []),
    ("If They Plead Guilty", "/resources/prosecution/if-they-plead-guilty.html",
     "What happens if the landlord admits the offence at the first hearing: outlining the facts to the court, "
     "sentencing, applying for your costs and getting a formal record of the conviction.",
     "Use it before your first hearing, because the court may sentence on the day.", []),
    ("If They Plead Not Guilty", "/resources/prosecution/if-they-plead-not-guilty.html",
     "A working booklet to print and bring to the first hearing. If the landlord denies the offence, the court "
     "will usually move straight on to planning the trial. The booklet helps you record what is disputed, what is "
     "agreed, who needs to give evidence and every deadline the court sets. It also includes model directions you "
     "can hand to the court.",
     "Use it at your first hearing, whichever way you expect the plea to go.", []),
    ("Prosecution costs", "/resources/prosecution/costs.html",
     "How to claim back what the prosecution cost you if the landlord is convicted: your out-of-pocket expenses "
     "and, if the court allows it, your time. Includes a model costs schedule.",
     "Use it from the start, so you keep a log of your time and spending, and again before the first hearing to "
     "prepare your claim.", []),
    ("Preparing for Trial (under construction)", None,
     "Disclosure, evidence, witnesses and the trial itself. Until it is published, take legal advice if your case "
     "is heading for trial.", None, []),
]


def build_hub(root: Path):
    """The /resources/ landing page: all the guides, with the 'before you use' notice."""
    url = SITE + "/resources/"
    head = bgp.HEAD.format(title=html.escape(HUB_TITLE), desc=html.escape(HUB_DESC, quote=True), url=url,
                           verified="", res_current=' aria-current="page"')
    head = head.replace('<span class="vchip">Beta &middot; verified </span>',
                        f'<span class="vchip">Reviewed {REVIEWED}</span>')
    cards = []
    for title, href, desc, when, extra in HUB_GUIDES:
        h = (f'<a href="{href}">{html.escape(title)}</a>' if href else html.escape(title))
        links = "".join(f' <a class="btn" href="{u}">{html.escape(t)}</a>' for t, u in extra)
        cards.append(
            '      <article class="guide-card">\n'
            f'        <h2>{h}</h2>\n'
            f'        <p>{html.escape(desc)}</p>\n'
            + (f'        <p class="use-when">{html.escape(when)}</p>\n' if when else "")
            + (f'        <p>{links.strip()}</p>\n' if links else "")
            + '      </article>')
    page = head + f'''
  <section class="hero">
    <div class="wrap wrap-narrow">
      <p class="eyebrow">Support &amp; resources</p>
      <h1>{html.escape(HUB_TITLE)}</h1>
      <p class="standfirst">If you pay a variable service charge, the law lets you ask your landlord for a summary of the costs behind it, and to inspect the accounts and receipts. If the landlord fails to comply without a reasonable excuse, it commits a criminal offence, and you can prosecute it yourself in the magistrates' court. These guides take you through both steps, from writing the request to the first hearing in court.</p>
      <p class="standfirst">They are based on a real case. In August 2026 Peabody Trust pleaded guilty to a section 25 offence after a resident prosecuted it (<a href="/posts/peabody-convicted.html">read about the case</a>). The guides set out what that case taught us, with model documents you can adapt.</p>
      <p>Written by residents, not lawyers. Please read <a href="#before-you-use-these-guides">&ldquo;Before you use these guides&rdquo;</a> at the foot of this page.</p>
      <div class="caution" style="font-size:.95rem"><strong>The law is changing.</strong> In England, the section 22 right to inspect accounts and receipts, and prosecutions for breaching it, end on 1 April 2027. The section 21 right and its offence continue until 1 November 2027 for private landlords and 1 November 2028 for housing associations. Each guide explains what this means for you.</div>
    </div>
  </section>

  <section class="guide-section">
    <div class="wrap wrap-narrow">
{chr(10).join(cards)}

      <section class="final-warning" id="before-you-use-these-guides" aria-labelledby="before-heading">
        <h2 id="before-heading">Before you use these guides</h2>
        <p>These guides are written by residents, not lawyers. They are information, not legal advice.</p>
        <p>They are based on one prosecution, brought in the London magistrates' courts in 2026. Other courts may handle things differently, court procedures and forms change, and your landlord, your lease and your circumstances may not match ours. Check when each guide was last reviewed, and check anything important against the current law and court rules.</p>
        <p>Take legal advice if you are unsure about anything, especially before you apply for a summons, if your landlord disputes the case, or if it is going to trial. The Leasehold Advisory Service (LEASE) gives free legal advice on leasehold law, including service charges (<a href="https://www.lease-advice.org" target="_blank" rel="noopener noreferrer">lease-advice.org</a>). For court procedure, speak to a solicitor.</p>
        <p>A private prosecution is a serious step. You take on the duties of a prosecutor, and in some circumstances a court can order a prosecutor to pay the defendant's costs. The <a href="/resources/prosecution/">main guide</a> explains how to avoid that.</p>
        <p>We cannot advise on individual cases. If you find an error in any guide, please tell us at <a href="mailto:PBCAEditor@gmail.com">PBCAEditor@gmail.com</a>.</p>
      </section>
    </div>
  </section>

{bgp.FOOT}
</body>
</html>
'''
    (root / "resources" / "index.html").write_text(page, encoding="utf-8")
    print(f"  resources/index.html{'':27s} {len(page)/1024:5.1f} KB  hub")


def docx_links(root, rendered):
    """add download attribute and file size to links that point at a .docx"""
    def repl(m):
        href, text = m.group(1), m.group(2)
        f = root / href.lstrip("/")
        if not f.exists():
            raise SystemExit("missing download: " + href)
        kb = max(1, round(f.stat().st_size / 1024))
        return (f'<a href="{href}" download>{text}</a> '
                f'<span class="fsize">(Word, {kb} KB)</span>')
    return re.sub(r'<a href="(/resources/prosecution/downloads/[^"]+\.docx)">(.*?)</a>', repl, rendered)


def build(root: Path):
    src = root / "build" / "prosecution"
    for pg in PAGES:
        md_text = (src / pg["md"]).read_text(encoding="utf-8")
        rendered = markdown.markdown(
            md_text, extensions=["tables", "sane_lists", "attr_list"], output_format="html5")
        seen, toc = set(), []

        def add_id(m):
            lvl, attrs, text = m.group(1), m.group(2), m.group(3)
            plain = re.sub(r"<[^>]+>", "", text)
            sid = bgp.slug(plain, seen)
            if lvl == "2":
                toc.append((sid, plain))
            return f'<h{lvl} id="{sid}"{attrs}>{text}</h{lvl}>'

        rendered = re.sub(r"<h([1-4])([^>]*)>(.*?)</h\1>", add_id, rendered, flags=re.S)
        rendered = docx_links(root, rendered)
        toc_html = "\n".join(
            f'          <li><a href="#{sid}">{html.escape(t)}</a></li>' for sid, t in toc)

        url = SITE + pg["path"]
        head = bgp.HEAD.format(title=html.escape(pg["title"]), desc=html.escape(pg["desc"], quote=True),
                               url=url, verified="", res_current=' aria-current="page"')
        head = head.replace('<span class="vchip">Beta &middot; verified </span>',
                            f'<span class="vchip">Reviewed {REVIEWED}</span>')

        others = "\n".join(
            '        <li><a href="%s"%s>%s</a></li>' % (
                p["path"], ' aria-current="page"' if p is pg else "", html.escape(p["nav"]))
            for p in PAGES)

        page = head + f'''
  <section class="hero">
    <div class="wrap">
      <p class="eyebrow"><a href="/resources/">Support &amp; resources</a> &middot; {html.escape(pg["eyebrow_tail"])}</p>
      <h1>{html.escape(pg["h1"])}</h1>
      <p class="standfirst" style="margin-bottom:.4rem"><em>{html.escape(pg["sub"])}</em></p>
      <p class="standfirst">{html.escape(pg["stand"])}</p>
      <p class="eyebrow" style="margin-top:.9rem">Published by the Peabody Complaints Archive (independent, resident-run) &middot; England and Wales &middot; last reviewed {REVIEWED}</p>
      <div class="btn-row">
        <a class="btn" href="/resources/">Back to Support &amp; resources</a>
      </div>
    </div>
  </section>

  <section class="guide-section">
    <div class="wrap guide-layout">
      <nav class="toc" aria-label="Contents">
        <h2 class="toc-title">Contents</h2>
        <ol>
{toc_html}
        </ol>
        <h2 class="toc-title" style="margin-top:1.4rem">The guides</h2>
        <ol class="guide-list">
{others}
        </ol>
      </nav>

      <article class="doc">
{rendered}
{RELATED_NOTE}
      </article>
    </div>
  </section>

{bgp.FOOT}
</body>
</html>
'''
        out = root / "resources" / "prosecution" / pg["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(f"  resources/prosecution/{pg['out']:34s} {len(page)/1024:5.1f} KB  {len(toc)} sections")
    build_hub(root)


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
