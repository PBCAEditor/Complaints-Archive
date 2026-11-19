# Peabody Complaints Archive: brief for Claude Code

Independent, resident-run site at https://peabodytrust.co.uk, hosted on GitHub Pages
from this repository (`main`, root). Hand-written static HTML with inline CSS. No
framework, no server, no database. The editor is not a coder but is very competent with
Windows and hardware, and wants things explained ("teach a man to fish"), in plain steps.

**The canonical manual is `build/README.md`. Read it before any site task.** This file is
a brief, not a second manual: do not copy its contents here, because duplicates drift.

## This repository is public

GitHub Pages serves every file in the repo, `build/` and this file included, and the git
history is public too. So never put any of the following in a file, a commit message, a
scratch note committed by accident, or an Office document's properties:

- the building's name, street address or postcode (write "a mixed-tenure development in
  Aldgate, east London"; the tribunal reference is censored as `LON/00BG/LSC/XXXX/XXXX`);
- the names of Peabody staff (use job titles, except senior figures acting publicly);
- the editor's private email address or personal details.

The watchlist lives in `build/check-rules.local.json`, which is git-ignored and must
never be committed. Do not print its contents into chat or into any file.

## Hard rules (build/README.md section 10)

1. The not-affiliated banner appears on every page.
2. No building name, address or postcode; censored tribunal reference.
3. Staff by job title.
4. No ads, nothing for sale.
5. Corrections and right of reply stays prominent.
6. No cookies, localStorage or sessionStorage. GoatCounter is the only external request.
7. Keep "no response received" lines accurate. Ask the editor to confirm them at publication.
8. Published URLs never change. A slug is permanent once published.

Never delete `CNAME`, `.nojekyll` or the `google*.html` verification file.

## Workflow for an article (full steps: build/README.md section 3)

1. Build from the editor's copy. **Keep every hyperlink** (Word conversions have lost them
   twice). Never invent a source or link: verify each URL, and say which ones are bot-blocked.
2. Run `python build/check-site.py --draft posts/<slug>.html` on the finished page. It
   checks the hard rules; it is not a fact-checker.
3. Register the article: `ORDER` in `build-search-index.py`; `POST_DATES` in
   `build-feed.py` and `add-site-features.py`; `POST_IMAGES` in `add-og-and-share.py` and
   `add-site-features.py` if it has its own header image (1200x675 JPEG, no EXIF);
   `POST_UPDATED` in `build-feed.py` for substantive updates; `sitemap.xml`; and the
   article list in `index.html`.
4. Regenerate: `build-search-index.py .`, `build-feed.py .`, `add-contents-box.py .`
   (run from the repo root). Re-running the scripts must leave the article unchanged.
5. Run `python build/check-site.py .` (expect 0 blocking; the `build/` items are CHECKs).
6. Preview locally with `python -m http.server 8765 --bind 127.0.0.1`, look at the page,
   then stop the server.
7. Show the editor the changes and any claims you could not verify. **Commit and push only
   after the editor says to.** Afterwards confirm the live page, image and feed.

Updates to an existing article are not corrections. Add the `<p class="updated">` line
under the byline, set `article:modified_time` and JSON-LD `dateModified`, add a
`POST_UPDATED` entry, bump the sitemap `lastmod`, and mark the homepage list entry
"Updated <date>". Corrections go in `pages/corrections-log.html`.

Byline: analysis is bylined to the Peabody Complaints Archive (PCA, expanded on first use),
opinion to the author by name (section 9). Copy an existing article of the same type.

## Evidence log and redaction

`evidence/index.html` holds redacted copies of documents. Original, unredacted files must
never be put in the repo or left in the repo folder. The method that has worked:

1. Find the text to redact with PyMuPDF coordinates and assert full coverage.
2. Draw boxes on a 200 dpi raster, then save as a 1200 px JPEG with no EXIF.
3. OCR the result (Windows.Media.Ocr) and run the draft check on the OCR text, handling
   image-only text such as signatures by eye.
4. Use the entry pattern: heading with id, `<p class="meta">`, intro, an `<h4>` per document,
   a `<figure class="doc">` with a long alt text, then "What it establishes." and
   "Redactions." paragraphs. State only what the redaction actually did; do not invent reasons.

Any exception to the staff-name rule is the editor's explicit, per-document decision.

## Environment notes (Windows, PowerShell 5.1)

- `git` is often not on PATH. GitHub Desktop bundles one at
  `%LOCALAPPDATA%\GitHubDesktop\app-<version>\resources\app\git\cmd\git.exe`; add that
  folder to `$env:PATH` in each command, because environment changes do not persist between
  tool calls. The same applies to Python (`python` may resolve to a Microsoft Store stub).
- Write commit messages to a file and use `git commit -F <file>` (quoting breaks otherwise;
  `Set-Content -Encoding utf8` adds a BOM, so prefer `[IO.File]::WriteAllText` with
  `UTF8Encoding($false)`).
- `.gitattributes` fixes line endings. Do not rewrite whole files' line endings.
- Check `git fetch` and `git log` first. The site is also edited from other (web) chats, so
  the repo can move without this session knowing.
- Do not rewrite published history or force-push unless the editor asks. A history scrub
  with `git-filter-repo` was done once to remove staff names.
- Put temporary files in the session scratchpad, not in the repo.

## Open work (as of November 2026)

- Prosecution guide (section 25) at `/resources/prosecution/`: not built. `guide.html` and
  `s21-guide.txt` must keep their URLs because prompts in circulation point at them.
- Make `check-site.py` look inside Office files (hidden links, author properties) and spot
  orphaned downloads.
- Deferred: one source file for all article metadata, nav wrapping on desktop, image sizes,
  heading structure on information pages, topic labels.
- The deployment section of `build/README.md` still describes uploading through the GitHub
  website. Day-to-day work now uses git through GitHub Desktop.
