# Peabody Complaints Archive — build and maintenance

*This is the canonical manual. Do not keep a second copy at the repository root;
they drift apart within days.*

Live site: **https://peabodytrust.co.uk**
Test address: https://pbcaeditor.github.io/Complaints-Archive/

This folder holds the scripts that generate parts of the site, plus this note
explaining how the whole thing fits together. These are tools that run on a
computer and produce files you then upload; the site itself is plain static HTML.

**Everything in this folder IS served to visitors.** GitHub Pages publishes every
file in the repository, so `peabodytrust.co.uk/build/check-site.py` resolves. The
repository is public as well, so anything committed here is public twice over and
stays in the commit history even after deletion.

Consequences, which matter:

- **Never commit `check-rules.local.json`.** It holds the building name and the
  staff-name watchlist, which are precisely what the anonymisation rules exist to
  keep off the web. It is in `.gitignore`; keep it local only.
- `robots.txt` carries `Disallow: /build/`. That stops indexing. It is not access
  control and does not make anything private.
- `check-site.py` now scans every served file, not just HTML, for the forbidden
  strings, and flags files in `/build/` as publicly served. That check exists
  because this exact mistake was made and shipped.

---

## 1. What the site is made of

Everything is hand-written static HTML with inline CSS. No framework, no build
step at serve time, no server, no database. That is deliberate: it keeps hosting
free and maintenance near zero.

```
/                              repo root
  index.html                   homepage: intro, pinned article, search, article list
  404.html                     error page (root-absolute links, noindex)
  feed.xml                     Atom feed — generated
  sitemap.xml                  all page URLs
  robots.txt                   crawler rules, points at the feed and sitemap
  search-index.json            homepage search data — generated
  favicon.svg / favicon.ico / apple-touch-icon.png
  CNAME                        holds peabodytrust.co.uk — NEVER DELETE
  google*.html                 Search Console verification — NEVER DELETE
  .nojekyll                    stops GitHub processing files — NEVER DELETE
  README.md                    the only manual; there is no second copy at the
                               repository root

  /images/                     header artwork, share card, verification block
  /pages/                      about, contact, corrections, corrections-log,
                               disclaimer, editorial-policy, privacy,
                               sending-evidence, terms
  /posts/                      the articles
  /resources/                  the Support & resources section
      index.html               hub: all the guides, with the disclaimer — generated
      requesting/index.html    the AI-prompt page for the s21/22 guide — generated
      guide.html               full s21/22 guide — generated
      prosecution/             the section 25 guides and their .docx downloads
      style.css                stylesheet for this section only
      s21-guide.txt            plain-text full s21/22 guide — generated
  /build/                      these scripts (not part of the website)
```

The three files marked NEVER DELETE do not appear in older documentation and are
easy to tidy away by mistake. `CNAME` holds the custom domain, the `google*.html`
file holds Search Console verification, and `.nojekyll` stops GitHub converting
`.md` and other files instead of serving them.

---

## 2. Deployment

Through the GitHub web interface: **Add file → Upload files**, then commit.

Navigate into the destination folder *first*. Uploading into the wrong folder is
the most common mistake and it fails quietly. Uploading a file with an existing
name overwrites it with no prompt; that is how you update a page.

Wait a minute or two for the rebuild, then hard-refresh (Ctrl+F5 / Cmd+Shift+R).

To create a folder, type the path in the filename box when using **Create new
file** — typing `resources/index.html` makes the folder. There is no separate
"new folder" button, because Git only tracks files.

---

## 3. Adding an article

1. Write the article and run the draft check (§5).
2. Save it as `/posts/<slug>.html`, copying an existing article to keep the head,
   banner, nav, share row, print styles and structured data consistent.
3. **The slug is permanent once published.** Renaming it breaks every shared
   link, and static hosting has no redirects.
4. Register it in three scripts: `ORDER` in `build-search-index.py`, and
   `POST_DATES` in both `build-feed.py` and `add-site-features.py`. If it has its
   own header image, add it to `POST_IMAGES` in `add-og-and-share.py` and
   `add-site-features.py` too.
5. Add its `<loc>` to `sitemap.xml`.
6. Add an entry to the article list on `index.html`.
7. Regenerate: `python3 build-search-index.py .`, `python3 build-feed.py .` and
   `python3 add-contents-box.py .`
8. Run the site check (§5).
9. Upload the article, plus `index.html`, `sitemap.xml`, `feed.xml` and
   `search-index.json`.
10. Once the article is live, send the email update (§11).

Steps 5 to 7 are the tax on every new article. Skip them and the page works while
search, the feed and the sitemap silently go stale.

---

## 4. The scripts

Run from the repository root, e.g. `python3 build/build-feed.py .`
They need Python 3 and the packages in `requirements.txt`:
`pip install -r build/requirements.txt`

| Script | What it does | When to run |
|---|---|---|
| `build-search-index.py` | Rebuilds `search-index.json` from `/posts/` | Any article added or edited |
| `build-feed.py` | Rebuilds `feed.xml`, newest first | Any article added, or a date changed |
| `build-guide-page.py` | Builds `/resources/requesting/index.html`, `guide.html` and `s21-guide.txt` from the guide sources | Guide text or version changed |
| `build-prosecution-pages.py` | Builds the four section 25 guide pages and the `/resources/` hub | Prosecution text, or the hub copy, changed |
| `split-prosecution-docs.py` | Cuts the editor's Word masters into the `.docx` downloads (section 6) | A master Word file changed |
| `add-og-and-share.py` | Adds Open Graph, Twitter and canonical tags, and the share row, to pages that lack them | New page added |
| `add-site-features.py` | Adds favicon and feed links, print styles, skip link, `<time>` and JSON-LD | New page added |
| `add-contents-box.py` | Adds an "In this article" box to posts with 5+ sections, the sign-up box to the end of every post, and the "Email updates" and "RSS feed" links to every footer | New article or page added |
| `check-site.py` | Pre-publication checks (§5) | Before every upload |

`add-og-and-share.py` and `add-site-features.py` skip anything already done, so
re-running them touches only new pages. Run `add-og-and-share.py` first.

---

## 5. Checking before you publish

```
python3 build/check-site.py .                    # whole site
python3 build/check-site.py --draft article.md   # one draft
```

Draft mode checks the hard rules: the building name, postcodes, uncensored
tribunal references, flat numbers, street addresses, Peabody staff names,
monetisation language, browser storage, unexpanded placeholders. **It is not a
fact-checker.**

Site mode checks every page for a title, description, canonical, exactly one
`<h1>`, alt text on images, the disclaimer banner, the analytics snippet, no
browser storage, no third-party resources beyond analytics, valid JSON-LD, no
duplicate ids and no broken internal links. It also checks that every article
appears in the sitemap, feed and search index, that no generated data has been
uploaded into `/images/`, and that the guide's version and check code agree
across all three guide files.

**Office files and PDFs.** A `.docx`, `.xlsx` or `.pptx` is a zip archive, so a plain
text search cannot see inside it. Both modes unpack these files and apply the same
rules to the body text, headers, footnotes, comments, deleted text, alt text, cell
values and hyperlink targets (a hidden link can carry an email address that the
visible text does not). They also report document hygiene: author, last-modified-by
and company properties, tracked changes, comments, hidden text, hidden sheets or
slides, speaker notes, macros, embedded thumbnails, and links to local file paths.
Run it on a Word draft before you start converting it:

```
python3 build/check-site.py --draft "My article.docx"
```

Hygiene findings are CHECK for a draft but BLOCK in site mode, because a file in the
repository is public. PDFs get the same treatment if PyMuPDF is installed
(`pip install pymupdf`). A PDF with no text layer, and the old `.doc`/`.xls`/`.ppt`
formats, cannot be read: the checker says so and the file needs checking by eye or
saving in a newer format. To clear author properties in Word: File, Info, Check for
Issues, Inspect Document, then Remove All beside Document Properties.

**Orphaned files.** Site mode lists downloads and images that no page, feed or
stylesheet refers to. They are still served at their own URL, so an unlinked draft
or old document stays public with nobody watching it. Link it or delete it. Files
that are deliberately unlinked are listed in `ORPHAN_ALLOWED` in `check-site.py`,
with the reason.

It exits with status 1 if anything blocking is found.

---

## 6. The Support & resources guide

Three files hold the guide, and they must move together:

- `s21-guide.md` — the full guide. The source of `guide.html` and `s21-guide.txt`.
- `s21-guide-compact.md` — the short version, embedded in the AI-prompt page
  (`/resources/requesting/`) and copied by the button. It is not linked from anywhere, but GitHub Pages serves
  every file in the repository, so it IS reachable at its own URL. That is not a
  problem (the guide is meant to be public) but nothing should claim otherwise.
- generated: `guide.html`, `s21-guide.txt`, `resources/requesting/index.html`.

Each carries a version number at the top and a check code at the very end. The
codes differ so an assistant quoting them reveals which document it read:

| | Version | Check code |
|---|---|---|
| Full guide | `0.2.6.1.8.4L` | `L70918` |
| Short version | `0.2.6.1.8.4S` | `SWQHPN` |

The version proves the file was opened; the check code at the end proves it
arrived complete. Both are shown on the AI-prompt page **as an image**, so they
cannot be scraped from the page text by an assistant that never opened the file.

**When revising the guide:** edit both markdown files, bump both version numbers
and both check codes, regenerate the verification image
(`python build/make-verification-image.py .`, which reads the numbers from the two
markdown files), run `build-guide-page.py`, then upload `index.html`, `guide.html`, `s21-guide.txt`
and the new image. `check-site.py` will catch it if the generated files fall
behind, but nothing will catch `s21-guide-compact.md` drifting, because it has no
URL. Change the two markdown files in the same sitting.

### The hub, and where things live

`/resources/` is the hub of all the guides (copy in `HUB_GUIDES` and `build_hub()` in
`build-prosecution-pages.py`). The AI-prompt page that used to be `/resources/` is now
`/resources/requesting/`. `guide.html`, `s21-guide.txt` and `s21-guide.md` did not move,
because prompts in circulation point at them.

### The section 25 prosecution guides

Four pages under `/resources/prosecution/`, plus Word downloads. The URLs are
permanent (rule 8): `index.html` (main guide), `if-they-plead-guilty.html`,
`if-they-plead-not-guilty.html`, `costs.html`, and `downloads/s25-*.docx`.

- **Page text:** `build/prosecution/{main,guilty,not-guilty,costs}.md`, built by
  `python build/build-prosecution-pages.py .` (needs `markdown`). Edit the markdown,
  never the generated HTML. A link to a `.docx` in the markdown gets a download
  attribute and the file size added automatically.
- **Downloads:** the editor keeps four master Word files (main guide with its
  appendices, costs, guilty plea, not-guilty booklet) outside the repo.
  `python build/split-prosecution-docs.py --main M.docx --costs C.docx --guilty G.docx
  --notguilty N.docx .` cuts them into nine files (checklists, six model documents,
  the proposed directions and the whole booklet), blanks the author properties, and
  swaps the masters' example address for an invented one with no postcode. It finds
  each piece by its text, so editing a master does not break it. Needs `python-docx`.
  Re-run it, then re-run the page builder, whenever a master changes.
- **Examples:** the model documents use an invented case (Jane Smith against Example
  Housing Association) and the invented address "Meadow Court, Mill Lane, Anytown
  [postcode]". `check-site.py` blocks anything shaped like a postcode or a numbered
  street address, so do not put a realistic one back.
- The court form SP001 is **not** reproduced. The download holds only the wording for
  its boxes, with a note to use the court's own form.
- Not versioned: unlike the s21 guide, these pages carry no version number or check
  code, only "last reviewed" (see `REVIEWED` in the page builder).

---

## 7. Backups and recovery

Green **Code** button → **Download ZIP** after any significant batch. The site
survives independently of the domain: if the domain were lost it stays live at
the github.io address and can be repointed using the DNS records below.

GoDaddy → Manage DNS. Four **A** records on `@`: `185.199.108.153`,
`185.199.109.153`, `185.199.110.153`, `185.199.111.153`. One **CNAME** on `www`
pointing at `pbcaeditor.github.io`. GitHub side: Settings → Pages, custom domain
`peabodytrust.co.uk`, source `main` / `(root)`, Enforce HTTPS on.

---

## 8. Corrections, updates and sources

A **correction** means something published was wrong. Log it on
`/pages/corrections-log.html`: article, date, what was wrong, what changed, and
whether the conclusion changed. Keep that page truthful even when empty; its
value is that it exists before there is anything in it.

An **update** means new information arrived and the article as published was not
wrong. Do not log it. Instead add one line under the byline:

```html
<p class="updated">Substantively updated <time datetime="2026-08-18">18 August 2026</time>:
short description of what changed.</p>
```

Only add it where there has genuinely been a substantive update. Do not add a
standing "status" line to every article: a currency claim you have not checked is
worse than no claim.

**Source labels.** Where an article identifies what a claim rests on, use these
four categories:

- **Open source** — published material anyone can check. Cite it so it survives
  link rot: publisher, title, publication date, and the date accessed. Use
  neutral citations for judgments.
- **Document held** — material held by the archive but not published. Name what
  it is and its date, not who supplied it.
- **First-hand account** — the editor's own, identified as such.
- **Resident account** — someone else's, anonymised, and weighted accordingly.

---

## 9. Byline and authorship convention

Adopted September 2026, applied as articles are revised rather than retrospectively.
Older articles keep their existing byline until a correction or change is warranted.

**Analysis.** Bylined to the Peabody Complaints Archive, not to an individual. The
initialism **PCA** may be used. Structured, evidence-led pieces resting on documents
and data.

**Opinion.** Bylined to the author by name, written in the first person.

**Guest authors.** Always named, whichever category the piece falls into.

The initialism is defined once, in the "What this site is" section on the homepage:
"The Peabody Complaints Archive (PCA) is written and run by leaseholders and
residents". `check-site.py` flags any page other than the homepage that uses PCA
without expanding it on first use. That is a CHECK rather than a BLOCK, because on
an analysis piece the byline itself carries the full name.

**Presentation.** Analysis pieces carry no pull quotes: the type is plain and the tables
and methodology do the work. A drop cap is permitted on the standfirst where it reads
well, but not on the opening body paragraph, which on a data-led piece often begins with
a figure or an initialism and looks awkward. Opinion pieces may use both drop caps and
pull quotes. The two
reproduced-document pages (the honours letter and the HCLG evidence) carry no drop cap,
pull quotes or header image, because they read as documents rather than articles.

**Methodology and sources.** Where an analysis piece rests on a dataset, the methodology,
limitations, sensitivity checks, any downloadable data and the source list go in a
visually separate appendix at the foot of the article (`<section class="appendix">`),
introduced by an "End of article" rule. Reference material should be reachable but
clearly not part of the argument.

**Headlines and framing.** Provocative framing is a legitimate technique but a
conditional one. Use it only where all three of these hold:

- The piece rests on original data or documents nobody else has published.
- The headline asks a question the article actually answers, rather than deferring or
  dodging it.
- The methodology, limitations and, where possible, the underlying data are published
  alongside.

Where the payoff is proportionate to the promise, the framing is earned. Where it is not,
it costs the credibility that the About, corrections and editorial policy pages exist to
establish, and that is much harder to rebuild than traffic is to gain.

**Keep it rare.** One provocative headline on a site of sober analysis reads as a
deliberate choice. Several in succession reads as the site's register, and the sobriety
elsewhere stops being believed. The default remains plain, descriptive headlines:
reporting, opinion and document-led analysis carry their own weight and do not need a
hook.

**Reach is not the only measure.** The article that travels furthest in resident groups
and the article that changes something are often not the same piece. Written evidence to
a select committee, an open letter, or a piece read by an APPG secretariat may draw a
fraction of the traffic and do considerably more. Judge pieces against what they were for.

In the page markup, an institutional byline also changes the JSON-LD `author` field
from `Person` to `Organization`. Copy an existing article of the same category rather
than editing this by hand.

A note on the edge case: a piece can be structurally analysis and still turn to the
first person where the argument needs it. That tension is an editorial choice for the
editor, not a rule to be resolved here.

---

## 10. Rules that must not be broken

1. The not-affiliated banner appears on **every** page.
2. No building name, street address or postcode anywhere. The convention is
   "a mixed-tenure development in Aldgate, east London". The tribunal reference is
   censored as `LON/00BG/LSC/XXXX/XXXX`.
3. Staff referred to by job title, not name, except senior figures acting
   publicly.
4. No ads, nothing for sale, domain not for sale.
5. Corrections and right of reply stays prominent.
6. No cookies, localStorage or sessionStorage. GoatCounter is the only external
   request any page makes on its own. The "Email updates" links and the homepage
   sign-up form send nothing to Buttondown until a reader clicks or presses
   Subscribe. Never use Buttondown's iframe or script embeds, or load any image
   from them (§11).
7. Keep the "no response received" lines accurate as things change.
8. Published URLs never change.

---

## 11. Email updates (Buttondown)

Readers who do not use RSS can get an email when an article is published. The
list is held by Buttondown, and the sign-up page is
`https://buttondown.com/pbcaeditor`. The account belongs to the editor; Claude
cannot log in to it and never has the subscriber list.

**How it reaches the site.** The same sign-up box ends every article, between the
article and the share buttons; `add-contents-box.py` adds it to new articles (its
`SIGNUP_BOX` and `SIGNUP_CSS`). The homepage box has Buttondown's plain `<form>` embed
(the "form" option on Buttondown's Settings → Embedding page), restyled to match
the site, with their "Powered by Buttondown" referral link removed (rule 4). Never
use their `<iframe>` option: it contacts Buttondown on every page load. "Email
updates" is a plain link in every footer (added
by `add-contents-box.py`, so new pages get it automatically) and in the box on the
homepage (`section.emailupdates` in `index.html`). Neither makes any request to
Buttondown until a reader uses it. Keep it that way (rule 6). The
homepage box sits under the intro while the list is new; once it is established,
move it to the bottom of the page, above "Get in touch" (the editor's decision,
26 November 2026).

**Settings that must stay as they are.** The privacy notice (`pages/privacy.html`,
"Email updates") describes these, so if one changes, change the notice first.

- Double opt-in on: a reader is subscribed only after clicking the confirmation email.
- Open and click tracking off.
- Sender name "Peabody Complaints Archive"; a public sender address, never the
  editor's private one.
- No promotion in the emails (rule 4).
- The free plan covers the first 100 subscribers. Check Buttondown's pricing page
  for what happens beyond that. RSS-to-email is a paid add-on, which is why each
  email is written by hand.

**Sending an update for a new article** (about five minutes), after the page is
live and checked:

1. In Buttondown choose New email. Subject: the article's title.
2. Body: two or three sentences taken from the article's own standfirst or feed
   summary, then the article's full `https://peabodytrust.co.uk/posts/<slug>.html`
   link. Do not paste the article in. Do not state anything the article does not.
3. Send a test to the editor's own address and read it on a phone.
4. Send. Claude can draft step 2 from the article on request.

**Requests from subscribers.** Unsubscribing is the link in every email. To delete
an address entirely, remove the subscriber in Buttondown's dashboard. Any other
request goes through the privacy notice's normal route.

**If the provider changes,** update `EMAIL_URL` in `add-contents-box.py`, the
homepage box, the privacy notice, and this section.