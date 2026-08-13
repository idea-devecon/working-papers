# Acknowledging a submission

Papers are posted under CC-BY 4.0 by default, which the authors have to
agree to. The agreement is easy to get and easy to forget to ask for,
so it lives here as fixed wording rather than being reinvented each
time, and `scripts/deposit.py` warns when a submission's metadata does
not record it.

Send this on receipt, before publishing the Zenodo draft.

> NAME— Thanks, received; it'll go up as IDEA Working Paper N. One
> housekeeping point before I post: papers are deposited on Zenodo,
> which mints the DOI and lets RePEc index them, and unless you tell me
> otherwise we post under CC-BY 4.0 — you and your co-authors keep
> copyright, and anyone may redistribute with attribution. If that's
> awkward, say so and we'll use a more restrictive license or hold off.
> Posting as a working paper doesn't preclude journal publication, and a
> revised version can replace the posted one later while keeping the
> same number and DOI.

Adjust the first sentence for multiple papers. The rest should stay
put: each clause is answering a question authors actually ask (who owns
it, does this burn my journal submission, what if I revise it).

## Recording the answer

In the submission's metadata YAML:

```yaml
license_consent: confirmed 2026-08-15
```

Anything not beginning with `confirmed` makes `deposit.py` warn. If an
author asks for different terms, set `license` to what was agreed and
say so:

```yaml
license: cc-by-nc-4.0
license_consent: confirmed 2026-08-15, NC requested by author
```

Silence is not consent. If a submission has been sitting unanswered,
the draft can wait -- an unpublished Zenodo draft costs nothing and the
DOI stays reserved.
