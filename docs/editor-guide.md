# Series editor's guide

This is the runbook for whoever edits the IDEA Working Papers series.
No step here requires more than basic command-line familiarity, and
most of the pipeline runs itself.

## The moving parts, in one paragraph

Papers live on [Zenodo](https://zenodo.org/communities/ideassoc/),
which stores the PDF and mints a DOI. This repository's build script
runs daily on GitHub Actions: it reads the Zenodo community, assigns
each new paper the next working-paper number (recorded permanently in
`papers.yaml`), and publishes two things to
<https://papers.idea.devecon.org/>: a human-readable index page and a
machine-readable metadata tree (`/RePEc/ida/`) that RePEc crawls
daily. Once a paper is accepted into the Zenodo community, it appears
on the website and in [IDEAS](https://ideas.repec.org/) /
[EconPapers](https://econpapers.repec.org/) within a day or two, with
no further action.

## Handling a submission

1. **Editorial check.** Verify the author is an IDEA member and the
   paper is on-topic. This series applies light editorial review, not
   peer review.

2. **Deposit to Zenodo.** Two equivalent routes:

   *Web route (no tools needed):* Ask the author to upload directly at
   <https://zenodo.org/uploads/new>, choosing:
   - Resource type: *Working paper*
   - Community: *International Development Economics Association*
   - Full author list (with affiliations and ORCIDs where available),
     title, abstract, and keywords. JEL codes go in keywords, written
     like `JEL: O12, Q16`.
   - Visibility *Public*, license CC-BY-4.0 recommended.

   *Script route (editor deposits on the author's behalf):*
   ```sh
   ZENODO_TOKEN=... python scripts/deposit.py metadata.yaml paper.pdf --cover --number N
   ```
   (see the header of `scripts/deposit.py` for the metadata format).
   The script creates an unpublished draft; review it in the browser
   and click Publish. `--cover` prepends the branded series cover
   page — with the WP number, the DOI Zenodo pre-reserves for the
   draft, date, and disclaimer — to the PDF (requires `pdflatex` and
   `pdfunite`; see `scripts/coverpage.py`). Choose `N` as the number
   the ledger will assign: next free number, ordering any queued
   papers by their `publication_date`.

   Note on licensing: the default is CC-BY-4.0, which requires the
   authors' consent — confirm when acknowledging the submission (a
   line like "working papers are posted under a CC-BY 4.0 license
   unless you tell us otherwise" suffices). The license can be
   changed on the draft before publishing.

3. **Accept into the community.** As community curator you'll get a
   Zenodo notification of the submission request; accept it at
   <https://zenodo.org/communities/ideassoc/requests>. Acceptance is
   what makes the pipeline (and hence RePEc) see the paper.

4. **Done.** The nightly build assigns the WP number. To see it
   immediately, run the workflow by hand: repo → Actions → *Build and
   deploy* → *Run workflow* — or locally, `python -m ideawp.build`
   (then commit the updated `papers.yaml`).

## Occasional tasks

- **Revised version of a paper:** on Zenodo, use *New version* on the
  existing record — never a fresh upload. The paper keeps its WP
  number and RePEc handle automatically (numbering is keyed to
  Zenodo's concept record, which is stable across versions).

- **Adding/correcting JEL codes:** edit the paper's entry in
  `papers.yaml`, adding e.g. `jel: [O12, Q16]`. This overrides
  whatever was parsed from Zenodo keywords.

- **Withdrawing a paper:** remove the record from the Zenodo
  community (or restrict it). The pipeline keeps the WP number
  reserved and emits a metadata stub marked withdrawn, per RePEc
  convention. Numbers are never reused.

- **Quarterly highlights:** pick 3–5 papers from the index page;
  nothing in this pipeline needs to change.

## When something breaks

- The GitHub Action fails loudly (email notification) rather than
  publishing a wrong site: a Zenodo API failure aborts the build, so
  papers can't accidentally "disappear" because of an outage.
- All state is in this repository (`config.yaml`, `papers.yaml`) plus
  Zenodo itself. The generated site is disposable — rebuild any time.
- RePEc-side questions: the maintainer contact registered for the
  archive receives their emails; see `docs/repec-registration.md`.

## Handing over the series

A successor needs:
1. Ownership/curator rights on the Zenodo community (add them at
   <https://zenodo.org/communities/ideassoc/members>).
2. Admin on this GitHub repository (or the org that owns it).
3. An update to `maintainer_name`/`maintainer_email` in `config.yaml`
   (and tell RePEc at repec@repec.org if the maintainer email
   changes).

Total ongoing effort: accepting submissions as they arrive; perhaps
five hours a year of everything else.
