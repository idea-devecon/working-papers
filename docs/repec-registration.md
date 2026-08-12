# RePEc registration (one-time setup)

Status: **not yet registered** (as of 2026-08-12). Follow this after
the site is live at <https://papers.idea.devecon.org/>.

RePEc's own tutorial: <https://ideas.repec.org/stepbystep.html>.

## What we are registering

- **Archive**: handle `RePEc:ida`, metadata at
  `https://papers.idea.devecon.org/RePEc/ida/`
- **Series**: handle `RePEc:ida:wpaper`, "IDEA Working Papers"

The code `ida` was verified unused against
<https://ideas.repec.org/archives.html> on 2026-08-12, but the RePEc
team has final say — if they assign a different code, change
`archive_code` in `config.yaml` and rerun the build; everything else
follows.

## Steps

1. **Make sure the site is live first.** The archive URL must be
   crawlable when the RePEc team looks at it:
   - <https://papers.idea.devecon.org/RePEc/ida/> shows links to
     `idaarch.redif`, `idaseri.redif` and `wpaper/`
   - `wpaper/` shows links to one `.redif` file per paper
   (The build generates these listings automatically; GitHub Pages
   has no directory autoindex, so RePEc's "simulated directory
   browsing" convention is used, per
   <https://ideas.repec.org/t/httpserver.html>.)

2. **Request the archive code.** Email <repec@repec.org>:

   > Subject: New RePEc archive request: International Development
   > Economics Association
   >
   > We would like to open a RePEc archive for the International
   > Development Economics Association (IDEA), a scholarly society in
   > development economics (https://idea.devecon.org/). We propose
   > archive code `ida`, which appears to be unused. Archive and
   > series templates are already in place at
   > https://papers.idea.devecon.org/RePEc/ida/ — one working-paper
   > series, RePEc:ida:wpaper ("IDEA Working Papers"). Maintainer:
   > [name, email as in config.yaml].

3. **If a different code is assigned**, update `config.yaml`
   (`archive_code`), rerun the build, and confirm the new URL to the
   RePEc team. Do this *before* any paper circulates with a handle.

4. **Verify indexing.** Within a few days papers should appear on
   IDEAS (`https://ideas.repec.org/s/ida/wpaper.html`) and EconPapers.
   Check LogEc for crawl status. If nothing appears within a week,
   write to repec@repec.org with the archive URL.

5. **Afterwards (optional but worthwhile):**
   - Register the series with [EconPapers](https://econpapers.repec.org/)
     alert lists (happens automatically once crawled).
   - Ask authors to claim their papers in the
     [RePEc Author Service](https://authors.repec.org/), which links
     papers to author profiles and citation counts.
   - Consider [NEP](http://nep.repec.org/) — new IDEA papers will be
     picked up by NEP's field reports (e.g. nep-dev) automatically
     once the series is indexed.

## Notes on the metadata files

- Files use the `.redif` extension, which tells RePEc they are UTF-8
  (`.rdf` implies ASCII); accented author names are safe.
  Reference: <https://ideas.repec.org/newmaintainer.html>.
- Template syntax specs:
  [archive](https://ideas.repec.org/t/archtemplate.html),
  [series](https://ideas.repec.org/t/seritemplate.html),
  [paper](https://ideas.repec.org/t/papertemplate.html).
- RePEc crawls roughly daily; our build also runs daily, so a newly
  accepted paper typically shows up on IDEAS within ~48 hours.
