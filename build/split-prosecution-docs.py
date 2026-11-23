#!/usr/bin/env python3
"""
Cut the editor's four master Word files for the section 25 prosecution guides
into the separate downloads that /resources/prosecution/ links to.

Usage:
  python build/split-prosecution-docs.py --main M.docx --costs C.docx \
        --guilty G.docx --notguilty N.docx [repo_root]

Reads (outside the repo, in the editor's own folder):
  M  the main guide, with the checklists and the model documents as appendices
  C  the costs guide, ending in the model costs schedule
  G  the guilty-plea guide (not split: its text is the web page)
  N  the not-guilty booklet, ending in the model proposed directions

Writes to <repo_root>/resources/prosecution/downloads/:
  s25-checklists.docx                 checklists 1 to 6
  s25-model-sp001-wording.docx        wording for boxes of the real form (built here)
  s25-model-certificate-of-service.docx
  s25-model-idpc.docx
  s25-model-witness-statement.docx
  s25-model-written-argument.docx
  s25-model-costs-schedule.docx
  s25-model-proposed-directions.docx
  s25-not-guilty-booklet.docx         the whole booklet

Every file gets clean document properties (no personal name) and the fictional
address and date fixes below. Pieces are located by their text, not by position,
so edits to the masters do not break the split. Requires python-docx.

The example documents use an invented address with no postcode on purpose:
check-site.py blocks anything shaped like a street address or postcode
(README section 10).
"""
import argparse
import copy
import re
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

# (regex, replacement). Regexes on purpose: the fictional address in the masters
# is shaped like a real one, and this file is public.
FIXES = [
    (r"Flat \d+, \w+ Court, \d+ \w+ Street, London [A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}",
     "Flat 12, Meadow Court, Mill Lane, Anytown [postcode]"),
    (r"Riverside Court, \d+ \w+ Street, London [A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}",
     "Meadow Court, Mill Lane, Anytown [postcode]"),
    (r"\d+ High Street, London [A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}",
     "Example House, High Street, Anytown [postcode]"),
    (r"Riverside Court", "Meadow Court"),
]
# the model IDPC is served on 24 March (certificate of service); its date line said April
IDPC_DATE_FIX = (r"24 April 2026", "24 March 2026")

SP001_URL = "https://www.gov.uk/government/publications/application-for-summons-or-warrant-for-arrest-for-an-alleged-offence"


def ptext(el):
    return "".join(t.text or "" for t in el.iter(qn("w:t")))


def norm(s):
    return s.replace("’", "'").strip()


def kids(d):
    return [e for e in d.element.body if e.tag != qn("w:sectPr")]


def is_break(el):
    """blank paragraph or a paragraph holding only a page break"""
    return el.tag == qn("w:p") and not ptext(el).strip()


def keep_range(d, start, end):
    """Delete every body child outside [start, end) (indices into kids(d))."""
    ks = kids(d)
    # trim blank / page-break paragraphs from both ends
    while start < end and is_break(ks[start]):
        start += 1
    while end > start and is_break(ks[end - 1]):
        end -= 1
    for i, e in enumerate(ks):
        if i < start or i >= end:
            e.getparent().remove(e)


def find(ks, pred, nth=0, last=False):
    hits = [i for i, e in enumerate(ks) if e.tag == qn("w:p") and pred(norm(ptext(e)))]
    if not hits:
        raise SystemExit("anchor not found")
    return hits[-1] if last else hits[nth]


def replace_in_paragraph(p, pattern, repl):
    """Regex replace across run boundaries, keeping the first run's formatting."""
    runs = [r for r in p.iter(qn("w:r")) if r.find(qn("w:t")) is not None]
    texts = [(r, "".join(t.text or "" for t in r.findall(qn("w:t")))) for r in runs]
    full = "".join(t for _, t in texts)
    changed = False
    while True:
        m = re.search(pattern, full)
        if not m:
            break
        a, b = m.span()
        pos = 0
        new_texts = []
        placed = False
        for r, t in texts:
            s, e = pos, pos + len(t)
            if e <= a or s >= b:
                new_texts.append((r, t))
            else:
                keep_l = t[: max(0, a - s)]
                keep_r = t[max(0, b - s):]
                mid = repl if not placed else ""
                placed = True
                new_texts.append((r, keep_l + mid + keep_r))
            pos = e
        texts = new_texts
        full = "".join(t for _, t in texts)
        changed = True
    if changed:
        for r, t in texts:
            ts = r.findall(qn("w:t"))
            ts[0].text = t
            ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            for extra in ts[1:]:
                r.remove(extra)
    return changed


def apply_fixes(d, extra=()):
    n = 0
    body = d.element.body
    for p in body.iter(qn("w:p")):
        for pat, rep in list(FIXES) + list(extra):
            if replace_in_paragraph(p, pat, rep):
                n += 1
    return n


def drop_unused_hyperlinks(d):
    used = {h.get(qn("r:id")) for h in d.element.body.iter(qn("w:hyperlink"))}
    for rid, rel in list(d.part.rels.items()):
        if rel.reltype.endswith("/hyperlink") and rid not in used:
            del d.part.rels[rid]


def clean_properties(d, title):
    cp = d.core_properties
    cp.author = ""            # check-site.py wants these empty, not just impersonal
    cp.last_modified_by = ""
    cp.title = title
    cp.subject = ""
    cp.keywords = ""
    cp.comments = ""
    cp.category = ""
    cp.revision = 1


def save(d, path, title):
    drop_unused_hyperlinks(d)
    clean_properties(d, title)
    path.parent.mkdir(parents=True, exist_ok=True)
    d.save(str(path))
    print("  wrote", path.name, "%d KB" % round(path.stat().st_size / 1024))


def clone_with_text(proto, text):
    """Copy a paragraph, keep the first run's formatting, set new text."""
    p = copy.deepcopy(proto)
    runs = [r for r in p.iter(qn("w:r"))]
    for h in list(p.iter(qn("w:hyperlink"))):
        h.getparent().remove(h)
    runs = [r for r in p.findall(qn("w:r"))]
    keep = None
    for r in runs:
        if keep is None and r.find(qn("w:t")) is not None:
            keep = r
        else:
            p.remove(r)
    for tag in ("w:bookmarkStart", "w:bookmarkEnd"):
        for b in list(p.iter(qn(tag))):
            b.getparent().remove(b)
    if keep is None:
        raise SystemExit("prototype paragraph has no text run")
    ts = keep.findall(qn("w:t"))
    ts[0].text = text
    ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for extra in ts[1:]:
        keep.remove(extra)
    return p


def build_sp001(main_path, out_dir):
    """Wording for the boxes of the real form. Built from the certificate's styles."""
    d = docx.Document(str(main_path))
    ks = kids(d)
    tbl_i = next(i for i, e in enumerate(ks) if e.tag == qn("w:tbl"))
    table = ks[tbl_i]
    cells = [ptext(tc) for tc in table.iter(qn("w:tc"))]
    # pull the wording of boxes 4 and 5 out of the master's example form
    def paras_of_cell(marker):
        for tc in table.iter(qn("w:tc")):
            t = ptext(tc)
            if t.lstrip().startswith(marker):
                out = []
                for p in tc.findall(qn("w:p")):
                    s = ptext(p).strip()
                    out.append(s)
                return out
        raise SystemExit("SP001 box %s not found" % marker)

    b4 = paras_of_cell("(4)")
    b5 = paras_of_cell("(5)")
    # box 4: drop the form's own instruction; keep what follows the CrimPR 7.3 sentence
    b4 = [s for s in b4 if s and not s.startswith("(4)") and not s.startswith("CrimPR 7.3")]
    b5 = [s for s in b5 if s and not s.startswith("(5)") and not s.startswith("CrimPR 7.2(6)")]

    # prototypes: title, heading, body, example banner (all from the certificate/IDPC)
    cert_i = find(ks, lambda t: t == "CERTIFICATE OF SERVICE")
    idpc_i = find(ks, lambda t: t.startswith("INITIAL DETAILS OF THE PROSECUTION CASE"))
    heading_i = find(ks, lambda t: t.startswith("1.") and "The offence" in t)
    body_i = find(ks, lambda t: t.startswith("This is a private prosecution brought by"))
    banner_i = find(ks, lambda t: t.startswith("THIS IS AN EXAMPLE DOCUMENT"))
    proto_title, proto_head, proto_body, proto_banner = ks[idpc_i], ks[heading_i], ks[body_i], ks[banner_i]

    new = []
    def add(proto, text):
        new.append(clone_with_text(proto, text))

    add(proto_title, "APPLICATION FOR A SUMMONS (FORM SP001): MODEL WORDING")
    add(proto_banner, "THIS IS AN EXAMPLE DOCUMENT – DO NOT SEND TO COURT")
    add(proto_body, "This is not the court form. Do not copy this document into your application and do not "
                     "send it to the court. Download the current form SP001 from GOV.UK and type your own wording "
                     "into its boxes. Court forms change, and the court expects the current one.")
    add(proto_body, "Form SP001: " + SP001_URL)
    add(proto_body, "Below is the wording a leaseholder might type into each box of the form for a section 21 case "
                     "against a housing association. The facts are invented. Replace them with your own, and keep "
                     "the wording as short as the model does.")
    add(proto_head, "Top of the form")
    for s in ["Applicant: Jane Smith",
              "Applicant's address: Flat 12, Meadow Court, Mill Lane, Anytown [postcode]",
              "Email address: jane.smith@example.com",
              "For the court to issue: a summons (delete 'warrant of arrest')",
              "Alleged offence: Failure to comply with a duty imposed by section 21 of the Landlord and Tenant Act 1985",
              "Date of alleged offence: 15 February 2026 (the date the statutory one month deadline expired)",
              "Proposed defendant: Example Housing Association, Example House, High Street, Anytown [postcode]"]:
        add(proto_body, s)
    add(proto_head, "Box (1) Consent to prosecute")
    add(proto_body, "Do you need consent to prosecute? No.")
    add(proto_head, "Box (2) Previous applications")
    add(proto_body, "Have you applied before for the issue of a summons or warrant in respect of any of the allegations "
                     "you are making? No. (If you have, answer Yes and give the details the form asks for.)")
    add(proto_head, "Box (3) Other proceedings")
    add(proto_body, "Has any other prosecutor ever brought a criminal case against the proposed defendant in respect of "
                     "any of the allegations you are making? No. (Related tribunal or Ombudsman proceedings do not make "
                     "the answer Yes.)")
    add(proto_head, "Box (4) Details of the alleged offence")
    for s in b4:
        add(proto_body, s)
    add(proto_head, "Box (5) Summary of the circumstances")
    for s in b5:
        add(proto_body, s)
    add(proto_head, "Box (6) Application for warrant")
    add(proto_body, "Leave blank. You are applying for a summons, not a warrant.")
    add(proto_head, "Box (7) Declaration")
    add(proto_body, "Read the declaration carefully before you sign. You are confirming that the allegations are "
                     "substantially true, that the evidence will be available at trial, and that the application "
                     "discloses all the information that is material to what the court must decide.")
    add(proto_body, "Signed: Jane Smith (applicant)        Date: 17 February 2026")
    add(proto_banner, "THIS IS AN EXAMPLE DOCUMENT – DO NOT SEND TO COURT")

    # empty the body, then append the new paragraphs
    body = d.element.body
    sect = body.find(qn("w:sectPr"))
    for e in list(body):
        if e is not sect:
            body.remove(e)
    for p in new:
        if sect is not None:
            sect.addprevious(p)
        else:
            body.append(p)
    # the master's example form says "the Prosecutor" in box 5; on SP001 she is the applicant
    apply_fixes(d, [(r"the Prosecutor made", "the Applicant made")])
    save(d, out_dir / "s25-model-sp001-wording.docx", "Model wording for form SP001 (example)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--main", required=True)
    ap.add_argument("--costs", required=True)
    ap.add_argument("--guilty", required=True)
    ap.add_argument("--notguilty", required=True)
    ap.add_argument("root", nargs="?", default=".")
    a = ap.parse_args()
    out = Path(a.root) / "resources" / "prosecution" / "downloads"

    # ---- pieces of the main guide ----
    def main_doc():
        return docx.Document(a.main)

    d = main_doc(); ks = kids(d)
    s_check = find(ks, lambda t: t.startswith("Checklist 1:"))
    tbl = next(i for i, e in enumerate(ks) if e.tag == qn("w:tbl"))
    # the SP001 example table is replaced by build_sp001; the rest follow it
    after = [i for i, e in enumerate(ks) if i > tbl and e.tag == qn("w:p")]
    c_start = find(ks, lambda t: t.startswith("IN THE [NAME] MAGISTRATES"), nth=0)
    i_start = find(ks, lambda t: t.startswith("IN THE [NAME] MAGISTRATES"), nth=1)
    w_start = find(ks, lambda t: t.startswith("STATEMENT OF WITNESS"))
    a_start = find(ks, lambda t: t.startswith("IN THE [NAME] MAGISTRATES"), nth=2)

    def pull_back(i):
        # a "THIS IS AN EXAMPLE" banner directly above belongs to this piece
        t = norm(ptext(ks[i - 1])) if i else ""
        return i - 1 if t.startswith("THIS IS AN EXAMPLE") and i - 1 > 0 else i

    a_start = pull_back(a_start)
    pieces = {
        "s25-checklists.docx": (s_check, tbl, "Checklists 1 to 6 (section 25 prosecution guide)"),
        "s25-model-certificate-of-service.docx": (c_start, i_start, "Model certificate of service (example)"),
        "s25-model-idpc.docx": (i_start, w_start, "Model Initial Details of the Prosecution Case (example)"),
        "s25-model-witness-statement.docx": (w_start, a_start, "Model witness statement (example)"),
        "s25-model-written-argument.docx": (a_start, len(ks), "Model written argument for an application hearing (example)"),
    }
    for name, (s, e, title) in pieces.items():
        d = main_doc(); ks2 = kids(d)
        keep_range(d, s, e)
        if name == "s25-checklists.docx":
            # give it a title: clone the first checklist heading, put the title above it
            first = kids(d)[0]
            t = clone_with_text(first, "Checklists 1 to 6")
            first.addprevious(t)
            intro = clone_with_text(first, "For the Guide to Private Prosecutions under Section 25 of the Landlord and "
                                            "Tenant Act 1985, published by the Peabody Complaints Archive. Print this "
                                            "document, or tick the boxes on screen.")
            # the intro should look like body text, not a heading: use the body paragraph style of the next item
            body_proto = next(p for p in kids(d) if p.tag == qn("w:p") and ptext(p).strip().startswith("☐"))
            intro = clone_with_text(body_proto, ptext(intro).replace("☐", ""))
            first.addprevious(intro)
        extra = [IDPC_DATE_FIX] if name == "s25-model-idpc.docx" else ()
        apply_fixes(d, extra)
        save(d, out / name, title)

    build_sp001(a.main, out)

    # ---- costs schedule ----
    d = docx.Document(a.costs); ks = kids(d)
    s = find(ks, lambda t: t.startswith("Model Costs Schedule"))
    keep_range(d, s, len(ks))
    apply_fixes(d)
    save(d, out / "s25-model-costs-schedule.docx", "Model costs schedule (example)")

    # ---- booklet: proposed directions + the whole booklet ----
    d = docx.Document(a.notguilty); ks = kids(d)
    s = find(ks, lambda t: t.startswith("Model Proposed Trial Directions"), last=True)
    e = find(ks, lambda t: t.startswith("What to do next"), last=True)
    keep_range(d, s, e)
    apply_fixes(d)
    save(d, out / "s25-model-proposed-directions.docx", "Model proposed trial directions (example)")

    d = docx.Document(a.notguilty)
    apply_fixes(d)
    save(d, out / "s25-not-guilty-booklet.docx", "If They Plead Not Guilty: working booklet")


if __name__ == "__main__":
    main()
