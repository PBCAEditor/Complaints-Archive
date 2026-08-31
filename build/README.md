Peabody Complaints Archive — build and maintenance
Live site: https://peabodytrust.co.uk
Test address: https://pbcaeditor.github.io/Complaints-Archive/
This folder holds the scripts that generate parts of the site, plus this note
explaining how the whole thing fits together. Nothing in `/build/` is served to
visitors. The site is plain static HTML; these are tools that run on a computer
and produce files you then upload.
---
1. What the site is made of
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
  README.md

  /images/                     header artwork, share card, verification block
  /pages/                      about, contact, corrections, disclaimer,
                               editorial-policy, privacy, terms
  /posts/                      the articles
  /resources/                  the Support & resources section
      index.html               landing page — generated
      guide.html               full guide — generated
      style.css                stylesheet for this section only
      s21-guide.txt            plain-text full guide — generated
  /build/                      these scripts (not part of the website)
```
The three files marked NEVER DELETE do not appear in older documentation and are
easy to tidy away by mistake. `CNAME` holds the custom domain, the `google*.html`
file holds Search Console verification, and `.nojekyll` stops GitHub converting
`.md` and other files instead of serving them.
---
2. Deployment
Through the GitHub web interface: Add file → Upload files, then commit.
Navigate into the destination folder first. Uploading into the wrong folder is
the most common mistake and it fails quietly. Uploading a file with an existing
name overwrites it with no prompt; that is how you update a page.
Wait a minute or two for the rebuild, then hard-refresh (Ctrl+F5 / Cmd+Shift+R).
To create a folder, type the path in the filename box when using Create new
file — typing `resources/index.html` makes the folder. There is no separate
"new folder" button, because Git only tracks files.
---
3. Adding an article
Write the article and run the draft check (§5).
Save it as `/posts/<slug>.html`, copying an existing article to keep the head,
banner, nav, share row, print styles and structured data consistent.
The slug is permanent once published. Renaming it breaks every shared
link, and static hosting has no redirects.
Register it in three scripts: `ORDER` in `build-search-index.py`, and
`POST_DATES` in both `build-feed.py` and `add-site-features.py`. If it has its
own header image, add it to `POST_IMAGES` in `add-og-and-share.py` and
`add-site-features.py` too.
Add its `<loc>` to `sitemap.xml`.
Add an entry to the article list on `index.html`.
Regenerate: `python3 build-search-index.py .` and `python3 build-feed.py .`
Run the site check (§5).
Upload the article, plus `index.html`, `sitemap.xml`, `feed.xml` and
`search-index.json`.
Steps 5 to 7 are the tax on every new article. Skip them and the page works while
search, the feed and the sitemap silently go stale.
---
4. The scripts
Run from the repository root, e.g. `python3 build/build-feed.py .`
They need Python 3 and, for some, `pip install beautifulsoup4 markdown`.
Script	What it does	When to run
`build-search-index.py`	Rebuilds `search-index.json` from `/posts/`	Any article added or edited
`build-feed.py`	Rebuilds `feed.xml`, newest first	Any article added, or a date changed
`build-guide-page.py`	Builds `/resources/index.html`, `guide.html` and `s21-guide.txt` from the guide sources	Guide text or version changed
`add-og-and-share.py`	Adds Open Graph, Twitter and canonical tags, and the share row, to pages that lack them	New page added
`add-site-features.py`	Adds favicon and feed links, print styles, skip link, `<time>` and JSON-LD	New page added
`check-site.py`	Pre-publication checks (§5)	Before every upload
`add-og-and-share.py` and `add-site-features.py` skip anything already done, so
re-running them touches only new pages. Run `add-og-and-share.py` first.
---
5. Checking before you publish
```
python3 build/check-site.py .                    # whole site
python3 build/check-site.py --draft article.md   # one draft
```
Draft mode checks the hard rules: the building name, postcodes, uncensored
tribunal references, flat numbers, street addresses, Peabody staff names,
monetisation language, browser storage, unexpanded placeholders. It is not a
fact-checker.
Site mode checks every page for a title, description, canonical, exactly one
`<h1>`, alt text on images, the disclaimer banner, the analytics snippet, no
browser storage, no third-party resources beyond analytics, valid JSON-LD, no
duplicate ids and no broken internal links. It also checks that every article
appears in the sitemap, feed and search index, that no generated data has been
uploaded into `/images/`, and that the guide's version and check code agree
across all three guide files.
It exits with status 1 if anything blocking is found.
---
6. The Support & resources guide
Three files hold the guide, and they must move together:
`s21-guide.md` — the full guide. The source of `guide.html` and `s21-guide.txt`.
`s21-guide-compact.md` — the short version, embedded in the landing page and
copied by the button. Never served at its own URL.
generated: `guide.html`, `s21-guide.txt`, `resources/index.html`.
Each carries a version number at the top and a check code at the very end. The
codes differ so an assistant quoting them reveals which document it read:
	Version	Check code
Full guide	`0.2.5.4.3.7L`	`L32463`
Short version	`0.2.5.4.3.7S`	`SMRFDI`
The version proves the file was opened; the check code at the end proves it
arrived complete. Both are shown on the landing page as an image, so they
cannot be scraped from the page text by an assistant that never opened the file.
When revising the guide: edit both markdown files, bump both version numbers
and both check codes, regenerate the verification image, run
`build-guide-page.py`, then upload `index.html`, `guide.html`, `s21-guide.txt`
and the new image. `check-site.py` will catch it if the generated files fall
behind, but nothing will catch `s21-guide-compact.md` drifting, because it has no
URL. Change the two markdown files in the same sitting.
---
7. Backups and recovery
Green Code button → Download ZIP after any significant batch. The site
survives independently of the domain: if the domain were lost it stays live at
the github.io address and can be repointed using the DNS records below.
GoDaddy → Manage DNS. Four A records on `@`: `185.199.108.153`,
`185.199.109.153`, `185.199.110.153`, `185.199.111.153`. One CNAME on `www`
pointing at `pbcaeditor.github.io`. GitHub side: Settings → Pages, custom domain
`peabodytrust.co.uk`, source `main` / `(root)`, Enforce HTTPS on.
---
8. Rules that must not be broken
The not-affiliated banner appears on every page.
No building name, street address or postcode anywhere. The convention is
"a mixed-tenure development in Aldgate, east London". The tribunal reference is
censored as `LON/00BG/LSC/XXXX/XXXX`.
Staff referred to by job title, not name, except senior figures acting
publicly.
No ads, nothing for sale, domain not for sale.
Corrections and right of reply stays prominent.
No cookies, localStorage or sessionStorage. GoatCounter is the only external
request any page makes.
Keep the "no response received" lines accurate as things change.
Published URLs never change.
