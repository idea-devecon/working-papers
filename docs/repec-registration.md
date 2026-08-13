# RePEc registration (one-time setup)

Status: **code assigned 2026-08-13**; awaiting first crawl. Kept as a
record of what was done, and as the procedure a successor society
would follow if it forked this repo for its own series.

RePEc's own tutorial: <https://ideas.repec.org/stepbystep.html>.

## What we registered

- **Archive**: handle `RePEc:idd`, metadata at
  `https://papers.idea.devecon.org/RePEc/idd/`
- **Series**: handle `RePEc:idd:wpaper`, "IDEA Working Papers"

## How to check whether a code is free

We first requested `ida` and were refused: it belongs to IDEAGOV
(International Center for Decentralization and Governance), whose
series `RePEc:ida:wpaper` has been running for years. The RePEc team
assigned `idd` instead.

The check that missed this was <https://ideas.repec.org/archives.html>.
That page lists ~2200 codes and `ida` is **not among them**, so it is
incomplete — absence from it proves nothing. Do not rely on it.

Fetch the IDEAS prefix directly instead. A taken code returns 200, a
free one 404:

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://ideas.repec.org/s/idd/
```

This distinguished `ida` (200, taken) from `idd` (404, free). The
RePEc team still has final say; propose a code, but expect to be
reassigned.

**If a different code is assigned**, change `archive_code` and
`base_url` in `config.yaml`, update the handles hardcoded in
`tests/test_pipeline.py` (they read the real `config.yaml`, so they
fail otherwise and CI runs them before deploying), rerun the build,
and confirm the new URL to the RePEc team. Do this *before* any paper
circulates with a handle.

Deployment is unaffected by the old tree: `site/` is gitignored and
CI builds it from a clean checkout, so only the current code is ever
published. A *local* `site/` does keep the old `RePEc/<old>/`
directory, since the build cleans only the series directory under the
current code — delete it by hand so local inspection is not
misleading.

## Steps

1. **Make sure the site is live first.** The archive URL must be
   crawlable when the RePEc team looks at it:
   - <https://papers.idea.devecon.org/RePEc/idd/> shows links to
     `iddarch.redif`, `iddseri.redif` and `wpaper/`
   - `wpaper/` shows links to one `.redif` file per paper
   (The build generates these listings automatically; GitHub Pages
   has no directory autoindex, so RePEc's "simulated directory
   browsing" convention is used, per
   <https://ideas.repec.org/t/httpserver.html>.)

2. **Request the archive code.** Check it is free first (see above),
   then email <repec@repec.org>:

   > Subject: New RePEc archive request: International Development
   > Economics Association
   >
   > We would like to open a RePEc archive for the International
   > Development Economics Association (IDEA), a scholarly society in
   > development economics (https://idea.devecon.org/). We propose
   > archive code `<code>`, which appears to be unused. Archive and
   > series templates are already in place at
   > https://papers.idea.devecon.org/RePEc/<code>/ — one working-paper
   > series, RePEc:<code>:wpaper ("IDEA Working Papers"). Maintainer:
   > [name, email as in config.yaml].

   Sent 2026-08-12 proposing `ida`; answered 2026-08-13 assigning
   `idd`. Expect a day or two.

3. **Apply the assigned code** as described above, then reply to the
   RePEc team confirming the archive URL they should crawl.

4. **Verify indexing.** Within a few days papers should appear on
   IDEAS (`https://ideas.repec.org/s/idd/wpaper.html`) and EconPapers.
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
