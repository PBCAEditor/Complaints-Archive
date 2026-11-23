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

3. Office files and PDFs are opened up, in both modes. A .docx, .xlsx or .pptx
   is a zip archive, so a plain text search never sees inside it. The checker
   unpacks it and applies the same rules to the body text, headers, footnotes,
   comments, deleted text, alt text and hyperlink targets (a hidden link can
   carry an email address the visible text does not), and flags document
   hygiene: author and company properties, tracked changes, comments, hidden
   text, hidden sheets, speaker notes, macros, embedded thumbnails and links to
   local file paths. Site mode treats hygiene findings as BLOCK because the
   file is public; draft mode reports them as CHECK. PDFs are handled the same
   way when PyMuPDF is installed.

4. Site mode also lists orphaned files: downloads and images that no page links
   to. They are still publicly reachable at their own URL, which is the problem.

Exit code is 1 if anything BLOCK-level is found, so it can gate a commit.
"""
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, unquote, quote

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("This script needs beautifulsoup4:  pip install beautifulsoup4")

SITE = "https://peabodytrust.co.uk"

# ---------------------------------------------------------------- draft rules

DRAFT_RULES = [
    ("Postcode (S9.2)", r"\b[A-Z]{1,2}[0-9][0-9A-Z]?\s?[0-9][A-Z]{2}\b", "BLOCK", 0),
    ("Postcode district (S9.2)", r"\b(?:London\s+)?E1\b(?!\d)", "BLOCK", 0),
    ("Uncensored tribunal ref (S9.2)", r"LON/00[A-Z]{2}/[A-Z]{3}/\d{4}/\d{4}", "BLOCK", 0),
    ("Flat/apartment number (S9.2)", r"\b(?:flat|apartment|apt)\s*\.?\s*\d{3}\b", "BLOCK", re.I),
    ("Street address (S9.2)", r"\b\d+[a-z]?\s+[A-Z][a-z]+\s+(?:Street|St|Road|Rd|Lane|Avenue|Ave|Way|Court|Close|Place|Row|Gardens)\b", "BLOCK", 0),
    ("Monetisation (S9.4)", r"\b(?:advertise here|sponsored|buy now|donate|for sale|purchase this domain)\b", "CHECK", re.I),
    ("Browser storage (S9.6)", r"localStorage|sessionStorage|document\.cookie|indexedDB", "BLOCK", 0),
    ("'No response' claim (S9.7)", r"no response (?:has been )?(?:was )?received|had not responded|did not respond|declined to comment", "CHECK", re.I),
    ("Unexpanded placeholder", r"\b(?:TBC|TODO|TK|XXX|\[insert|\[name\]|check tenure)", "CHECK", re.I),
    ("Local file path", r"(?:/Users/|C:\\\\|/home/)", "CHECK", 0),
]


# ---------------------------------------------------------- local-only rules
#
# Some patterns cannot live in this file: the building name and the staff-name
# watchlist are exactly what the anonymisation rules exist to keep off the web,
# and this repository is public. They are loaded from an untracked file instead.
#
# Create check-rules.local.json NEXT TO THIS SCRIPT, and add it to .gitignore:
#
#   {
#     "Building name (S9.2)":     {"pattern": "...", "severity": "BLOCK"},
#     "Peabody staff name (S9.3)": {"pattern": "...", "severity": "CHECK"}
#   }
#
# If the file is absent the script says so and continues without those rules.

LOCAL_RULES_FILE = Path(__file__).with_name("check-rules.local.json")


def load_local_rules():
    if not LOCAL_RULES_FILE.exists():
        return None
    data = json.loads(LOCAL_RULES_FILE.read_text(encoding="utf-8"))
    out = []
    for label, cfg in data.items():
        out.append((label, cfg["pattern"], cfg.get("severity", "BLOCK"),
                    re.I if cfg.get("ignore_case") else 0))
    return out


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


# ------------------------------------------------- Office files and PDFs
#
# .docx/.xlsx/.pptx are zip archives of XML, so the plain-text rules never see
# inside them. These helpers unpack them and hand back (location, text) pairs
# for the same rules, plus "notes" about document hygiene.
#
# Notes carry a level: "META" is hygiene that is BLOCK for a file that is being
# published (site mode) and CHECK for a draft still being written (draft mode);
# "CHECK" and "BLOCK" are the same in both modes.

OFFICE_EXT = {".docx", ".docm", ".dotx", ".xlsx", ".xlsm", ".pptx", ".pptm"}
UNINSPECTABLE_EXT = {".doc", ".xls", ".ppt", ".odt", ".ods", ".odp"}
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TEXT_TAGS = {"t", "delText", "instrText"}
SKIP_PART = re.compile(
    r"(^|/)(theme|slideLayouts|slideMasters|printerSettings|_rels)/|"
    r"(^|/)(styles|fontTable|settings|webSettings|numbering|stylesWithEffects|"
    r"\[Content_Types\]|app|core|custom)\.xml$|\.rels$")
MAX_PART = 50 * 1024 * 1024
MAX_TOTAL = 200 * 1024 * 1024


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def document_kind(path):
    ext = Path(path).suffix.lower()
    if ext in OFFICE_EXT:
        return "Office document"
    if ext == ".pdf":
        return "PDF"
    if ext in UNINSPECTABLE_EXT:
        return "legacy Office document"
    return None


def inspect_office(path):
    """Return (pairs, notes) for an OOXML file. pairs = [(location, text)]."""
    pairs, notes = [], []
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        return pairs, [("CHECK", "not a valid Office (zip) file, so it could not be inspected")]
    with zf:
        infos = zf.infolist()
        if sum(i.file_size for i in infos) > MAX_TOTAL or any(i.file_size > MAX_PART for i in infos):
            return pairs, [("CHECK", "unusually large when unpacked; not inspected")]
        names = [i.filename for i in infos]

        def parse(name):
            data = zf.read(name)
            if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
                notes.append(("CHECK", f"{name}: contains an XML DOCTYPE/ENTITY, skipped as unsafe"))
                return None
            try:
                return ET.fromstring(data)
            except ET.ParseError:
                notes.append(("CHECK", f"{name}: unreadable XML"))
                return None

        # -- body text, headers, footers, footnotes, comments, notes, sheets
        counts = Counter()
        for name in names:
            if not name.endswith(".xml") or not name.startswith(("word/", "xl/", "ppt/")):
                continue
            if SKIP_PART.search(name):
                continue
            root = parse(name)
            if root is None:
                continue
            label = name.rsplit("/", 1)[-1][:-4]
            n = 0
            for el in root.iter():
                tag = _local(el.tag)
                if tag in ("p", "si", "is"):
                    s = "".join(t.text or "" for t in el.iter() if _local(t.tag) in TEXT_TAGS)
                    if s.strip():
                        n += 1
                        pairs.append((f"{label} block {n}", s))
                elif tag in ("f", "definedName") and (el.text or "").strip():
                    pairs.append((f"{label} {tag}", el.text))
                elif tag == "c" and el.get("t") == "str":
                    # a text cell whose value sits in <v> (written by some tools
                    # instead of the shared-strings table)
                    v = "".join(x.text or "" for x in el if _local(x.tag) == "v")
                    if v.strip():
                        n += 1
                        pairs.append((f"{label} cell {el.get('r', n)}", v))
                for attr in ("descr", "title", "alt"):
                    v = el.get(attr)
                    if v and v.strip():
                        pairs.append((f"{label} alt-text", v))
                if tag == "sheet" and el.get("name"):
                    pairs.append((f"{label} sheet name", el.get("name")))
                    if el.get("state") in ("hidden", "veryHidden"):
                        notes.append(("META", f"hidden worksheet: {el.get('name')!r}"))
                if tag in ("row", "col") and el.get("hidden") in ("1", "true"):
                    counts[f"hidden {tag}s"] += 1
                if el.tag.startswith(W_NS):
                    if tag in ("ins", "del", "moveFrom", "moveTo"):
                        counts["tracked changes"] += 1
                    elif tag == "vanish" and el.get(W_NS + "val") not in ("0", "false", "off"):
                        counts["hidden text runs"] += 1
                if tag == "sld" and el.get("show") == "0":
                    notes.append(("META", f"hidden slide: {name}"))
            if name.startswith("word/comments") and n:
                counts["comments"] += n
            if name.startswith(("ppt/notesSlides/", "ppt/comments/")) and n:
                counts["speaker notes or comments"] += n
            if name.startswith(("xl/comments", "xl/threadedComments")) and n:
                counts["cell comments"] += n
        for what, c in counts.items():
            level = "CHECK" if what.startswith("hidden") and "run" not in what and "text" not in what else "META"
            notes.append((level, f"{c} {what}"))

        # -- document properties
        def props(name, wanted, flagged):
            if name not in names:
                return
            root = parse(name)
            if root is None:
                return
            for el in root.iter():
                tag = _local(el.tag)
                val = (el.text or "").strip()
                if tag in wanted and val:
                    pairs.append((f"property {tag}", val))
                    if tag in flagged:
                        notes.append(("META", f"document property {tag} is set: {val!r}"))
        props("docProps/core.xml", {"creator", "lastModifiedBy", "title", "subject",
                                    "description", "keywords", "category"},
              {"creator", "lastModifiedBy", "subject", "description", "keywords", "category"})
        props("docProps/app.xml", {"Company", "Manager", "HyperlinkBase"},
              {"Company", "Manager", "HyperlinkBase"})
        if "docProps/custom.xml" in names:
            root = parse("docProps/custom.xml")
            if root is not None:
                for el in root.iter():
                    if _local(el.tag) == "property" and el.get("name"):
                        notes.append(("META", f"custom property: {el.get('name')!r}"))
                        pairs.append(("custom property", "".join(el.itertext())))

        # -- hyperlinks and other external targets
        for name in names:
            if not name.endswith(".rels"):
                continue
            root = parse(name)
            if root is None:
                continue
            for rel in root:
                if rel.get("TargetMode") != "External":
                    continue
                target = (rel.get("Target") or "").strip()
                kind = (rel.get("Type") or "").rsplit("/", 1)[-1]
                pairs.append((f"{name.rsplit('/', 1)[-1]} {kind} target", unquote(target)))
                low = target.lower()
                if low.startswith("mailto:"):
                    notes.append(("CHECK", f"mailto link (check the address is meant to be public): {target}"))
                if low.startswith("file:") or re.match(r"^[A-Za-z]:[\\/]", target) or target.startswith("\\\\"):
                    notes.append(("META", f"link to a local file path: {target}"))
                if kind not in ("hyperlink",):
                    notes.append(("CHECK", f"external {kind} reference: {target}"))

        # -- things that should not be in a published file at all
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            notes.append(("BLOCK", "contains a VBA macro project"))
        if any(n.startswith("docProps/thumbnail") for n in names):
            notes.append(("META", "contains an embedded preview thumbnail of the document"))
        if any("/embeddings/" in n for n in names):
            notes.append(("CHECK", "contains embedded objects"))
        if any(n.startswith("xl/externalLinks/") for n in names):
            notes.append(("CHECK", "links to other workbooks"))
    return pairs, notes


def inspect_pdf(path):
    """Return (pairs, notes) for a PDF. Needs PyMuPDF; says so if it is missing."""
    try:
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf
    except ImportError:
        return [], [("CHECK", "PyMuPDF is not installed, so this PDF was not inspected "
                              "(pip install pymupdf)")]
    pairs, notes = [], []
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        return [], [("CHECK", f"could not open PDF: {e}")]
    with doc:
        for key, val in (doc.metadata or {}).items():
            if key in ("author", "subject", "keywords", "title") and (val or "").strip():
                pairs.append((f"property {key}", val))
                if key != "title":
                    notes.append(("META", f"PDF property {key} is set: {val!r}"))
        has_text = False
        for pno, page in enumerate(doc, 1):
            for j, line in enumerate(page.get_text().splitlines(), 1):
                if line.strip():
                    has_text = True
                    pairs.append((f"page {pno} line {j}", line))
            for link in page.get_links():
                if link.get("uri"):
                    pairs.append((f"page {pno} link", link["uri"]))
            for annot in page.annots() or []:
                content = (annot.info or {}).get("content", "")
                if content.strip():
                    notes.append(("META", f"annotation or comment on page {pno}"))
                    pairs.append((f"page {pno} annotation", content))
        if doc.page_count and not has_text:
            notes.append(("CHECK", "no text layer (scanned images?), so the text rules could "
                                   "not run; any name in the picture needs checking by eye"))
    return pairs, notes


def inspect_document(path):
    kind = document_kind(path)
    if kind == "Office document":
        return inspect_office(path)
    if kind == "PDF":
        return inspect_pdf(path)
    return [], [("CHECK", "legacy format that cannot be inspected; save it as .docx/.xlsx/.pptx "
                          "and check that copy")]


def scan_pairs(pairs, rules):
    out = []
    for loc, line in pairs:
        for label, pattern, sev, flags in rules:
            for m in re.finditer(pattern, line, flags):
                out.append((sev, label, loc, m.group(0), line.strip()[:110]))
    return out


def notes_to_findings(notes, site_mode):
    return [("BLOCK" if lvl == "BLOCK" or (lvl == "META" and site_mode) else "CHECK",
             "Document hygiene", "", "", msg) for lvl, msg in notes]


def document_findings(path, rules, site_mode):
    """All findings for one Office file or PDF, as (sev, label, loc, hit, ctx)."""
    pairs, notes = inspect_document(path)
    return pairs, notes_to_findings(notes, site_mode) + scan_pairs(pairs, rules)


def check_draft(path):
    findings = []
    local = load_local_rules()
    if local is None:
        findings.append(("BLOCK", "Privacy rules unavailable: "
                         f"{LOCAL_RULES_FILE.name} not found, so the building-name "
                         "and staff-name checks did NOT run", 0, "", ""))
        local = []
    rules = DRAFT_RULES + local

    kind = document_kind(path)
    if kind:
        pairs, found = document_findings(path, rules, site_mode=False)
        findings += found
        header = f"Checked: {path}\n{kind}: {len(pairs)} text blocks, links and properties\n"
    else:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
        pairs = list(enumerate(text.splitlines(), 1))
        findings += scan_pairs(pairs, rules)
        header = f"Checked: {path}\n{len(pairs)} lines, {len(text.split())} words\n"

    texts = [t for _, t in pairs]
    for sev, label, idx, hit, ctx in unexpanded_initialisms("\n".join(texts), texts):
        findings.append((sev, label, pairs[idx - 1][0] if pairs else 0, hit, ctx))

    print(header)
    if not findings:
        print("No rule hits.")

    def order(f):
        return (f[0] != "BLOCK", f[2] if isinstance(f[2], int) else 10 ** 9, str(f[2]))

    for sev, label, loc, hit, ctx in sorted(findings, key=order):
        where = f"line {loc}" if isinstance(loc, int) else (loc or "document")
        if hit:
            print(f"[{sev}] {label}  {where}\n        matched: {hit!r}\n        context: {ctx}\n")
        else:
            print(f"[{sev}] {label}  {where}\n        {ctx}\n")
    return any(f[0] == "BLOCK" for f in findings)

# ----------------------------------------------------------------- site rules

# Downloads and images that are meant to be reachable only through a link. An
# unlinked one is still served at its own URL, and nobody is looking at it any
# more, which is how a stale draft ends up public.
ORPHAN_EXT = (OFFICE_EXT | UNINSPECTABLE_EXT |
              {".pdf", ".csv", ".zip", ".rtf", ".txt", ".md",
               ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico"})
ORPHAN_IGNORE = {"README.md", "CLAUDE.md", "robots.txt"}
# Deliberately unlinked files, with the reason. Keep this list short.
ORPHAN_ALLOWED = {
    "resources/s21-guide-compact.md": "embedded in the resources/requesting page and copied by "
                                      "its button (build/README.md section 6)",
    "resources/s21-guide.md": "markdown source of guide.html and s21-guide.txt, public by design "
                              "(build/README.md section 6)",
}
REFERENCE_EXT = {".html", ".xml", ".json", ".css", ".js", ".txt", ".md", ".webmanifest"}


def find_orphans(root: Path):
    """Return [(rel_path, reason)] for served files that nothing refers to."""
    corpus = {}
    candidates = []
    for f in root.rglob("*"):
        if not f.is_file() or ".git" in f.parts:
            continue
        rel = f.relative_to(root).as_posix()
        if rel.startswith("build/") or f.name in ORPHAN_IGNORE:
            continue
        ext = f.suffix.lower()
        if ext in REFERENCE_EXT:
            corpus[rel] = f.read_text(encoding="utf-8", errors="ignore").lower()
        if ext in ORPHAN_EXT and rel not in ORPHAN_ALLOWED:
            candidates.append(rel)
    out = []
    for rel in candidates:
        name = rel.rsplit("/", 1)[-1].lower()
        needles = {name, quote(name), name.replace(" ", "%20"), name.replace(" ", "+")}
        if not any(rel != other and any(n in text for n in needles)
                   for other, text in corpus.items()):
            out.append((rel, "orphaned: no page, feed or stylesheet refers to it, but it is "
                             "still served at its own URL. Link it or delete it."))
    return out


def html_files(root):
    out = []
    for pattern in ("index.html", "404.html", "pages/*.html", "posts/*.html",
                    "resources/*.html", "resources/*/*.html", "evidence/*.html"):
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

        # fragment links point at ids that exist on the page
        page_ids = {e["id"] for e in soup.find_all(id=True)}
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") and len(href) > 1 and href[1:] not in page_ids:
                bad("BLOCK", rel, f"fragment link to a missing id: {href}")

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

    # ---- forbidden strings in ANY served file, not just HTML.
    # /build/ is served by GitHub Pages like everything else.
    local = load_local_rules()
    if local is None:
        bad("BLOCK", LOCAL_RULES_FILE.name,
            "Privacy rules unavailable. The building-name and staff-name checks "
            "did NOT run, so this check is incomplete.")
        local = []
    # Office files and PDFs are opened up (see inspect_office); everything else
    # is searched as text. Document hygiene (author properties, tracked
    # changes, comments and so on) is checked even if the local rules are
    # missing, because that does not depend on the watchlist.
    local_labels = {label for label, _, _, _ in local}
    # The rules file necessarily contains every pattern it defines, so
    # matching against it is a false alarm. It is gitignored and never
    # deployed. Skipping it is what lets a clean run report zero blocking;
    # a blocking count that is never zero stops being read.
    rules_path = LOCAL_RULES_FILE.resolve()
    for f in root.rglob("*"):
        if not f.is_file() or ".git" in f.parts:
            continue
        if f.resolve() == rules_path:
            continue
        rel = f.relative_to(root).as_posix()
        if document_kind(f):
            _, found = document_findings(f, DRAFT_RULES + local, site_mode=True)
            seen = set()
            for sev, label, loc, hit, ctx in found:
                if label in local_labels:
                    # never echo a watchlist match into the output
                    msg = f"{label} appears in a file served from the site (at {loc})"
                elif hit:
                    msg = f"{label} at {loc}: {hit!r}"
                else:
                    msg = f"{label}: {ctx}"
                if (sev, msg) not in seen:
                    seen.add((sev, msg))
                    bad(sev, rel, msg)
            continue
        if not local:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pattern, sev, flags in local:
            if re.search(pattern, content, flags):
                bad("BLOCK", rel, f"{label} appears in a file served from the site")

    # ---- orphaned downloads and images: served, but no page points at them
    for rel, why in find_orphans(root):
        bad("CHECK", rel, why)

    # ---- scripts and sources should not be served at all
    # The local rules file is excluded: it is gitignored, so it is never pushed
    # and never served. Listing it here claimed the opposite.
    for f in (root / "build").glob("*"):
        if f.is_file() and f.name not in ("README.md", LOCAL_RULES_FILE.name):
            bad("CHECK", f.relative_to(root).as_posix(),
                "served publicly; GitHub Pages serves everything in the repository")

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

    rules_note = (f"privacy rules loaded, {len(local)} patterns" if local
                  else "PRIVACY RULES NOT LOADED")
    print(f"Checked {len(files)} pages, {len(posts)} articles; {rules_note}.\n")
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
