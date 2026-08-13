#!/usr/bin/env python3
"""Create a Zenodo draft deposit for a working paper.

Usage:
    ZENODO_TOKEN=... python scripts/deposit.py metadata.yaml paper.pdf \
        [--cover --number N] [--sandbox]

Creates an *unpublished draft* with the PDF attached and the ideassoc
community pre-selected, then prints the draft URL.  The series editor
reviews the draft in the browser and clicks Publish -- publishing stays
a human decision.

With --cover, a branded IDEA cover page is prepended to the PDF before
upload (see scripts/coverpage.py; requires pdflatex and pdfunite).  The
cover carries the working-paper number you pass with --number and the
DOI Zenodo pre-reserves for the draft.  Pick the number the ledger will
assign: papers are numbered by publication_date (ties broken by record
id), so check papers.yaml and the dates of anything else in the queue.

The metadata YAML looks like:

    title: Credit Constraints and Smallholder Technology Adoption
    creators:
      - name: "Doe, Jane"          # "Last, First"
        affiliation: University of Nairobi
        orcid: 0000-0002-1825-0097  # optional
      - name: "Rao, Anand"
    abstract: >
      We study how credit constraints affect ...
    publication_date: 2026-08-15   # optional; defaults to today
    keywords: [technology adoption, credit]
    jel: [O12, Q16]                # becomes a "JEL: ..." keyword
    license: cc-by-4.0             # optional; this is the default
    license_consent: confirmed 2026-08-15   # optional but checked; see
                                            # docs/acknowledgment.md

Any other keys are ignored, so the file doubles as the submission
record (who sent it, when).  license_consent is the exception: if it
does not begin with "confirmed", the script warns, because posting
under CC-BY without the authors' agreement is the one mistake here
that is hard to undo.

Get a token at https://zenodo.org/account/settings/applications/
(scopes: deposit:write, deposit:actions).
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

import requests
import yaml

COMMUNITY = "ideassoc"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metadata", help="YAML file with paper metadata")
    ap.add_argument("pdf", help="the paper, as a PDF")
    ap.add_argument("--sandbox", action="store_true", help="use sandbox.zenodo.org")
    ap.add_argument("--cover", action="store_true",
                    help="prepend an IDEA cover page before uploading")
    ap.add_argument("--number", type=int,
                    help="working-paper number for the cover (required with --cover)")
    args = ap.parse_args()
    if args.cover and not args.number:
        ap.error("--cover requires --number")

    token = os.environ.get("ZENODO_TOKEN")
    if not token:
        sys.exit("Set ZENODO_TOKEN (https://zenodo.org/account/settings/applications/)")

    base = "https://sandbox.zenodo.org/api" if args.sandbox else "https://zenodo.org/api"
    auth = {"Authorization": f"Bearer {token}"}

    with open(args.metadata, encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    pdf = Path(args.pdf)
    if not pdf.exists():
        sys.exit(f"No such file: {pdf}")

    for req in ("title", "creators", "abstract"):
        if not meta.get(req):
            sys.exit(f"metadata is missing required field: {req}")

    # Not fatal: depositing a draft before the authors have replied is a
    # normal thing to do.  Publishing without their agreement is not, and
    # the draft is the last checkpoint before that becomes irreversible.
    consent = str(meta.get("license_consent") or "").strip()
    if not consent.lower().startswith("confirmed"):
        print(
            f"WARNING: license_consent is {consent or 'absent'!r}, so the authors have\n"
            f"         not agreed to {meta.get('license', 'cc-by-4.0')} in writing.\n"
            "         The draft stays unpublished; confirm before you click Publish\n"
            "         (wording in docs/acknowledgment.md), then record it in the\n"
            "         metadata as 'license_consent: confirmed <date>'.",
            file=sys.stderr,
        )

    keywords = list(meta.get("keywords", []))
    if meta.get("jel"):
        keywords.append("JEL: " + ", ".join(meta["jel"]))

    deposit_metadata = {
        "upload_type": "publication",
        "publication_type": "workingpaper",
        "title": meta["title"],
        "creators": [
            {k: v for k, v in c.items() if k in ("name", "affiliation", "orcid")}
            for c in meta["creators"]
        ],
        "description": meta["abstract"],
        "publication_date": str(
            meta.get("publication_date") or datetime.date.today().isoformat()
        ),
        "access_right": "open",
        "license": meta.get("license", "cc-by-4.0"),
        "communities": [{"identifier": COMMUNITY}],
    }
    if keywords:
        deposit_metadata["keywords"] = keywords

    # 1. Create an empty deposition (Zenodo pre-reserves its DOI).
    r = requests.post(f"{base}/deposit/depositions", json={}, headers=auth, timeout=30)
    r.raise_for_status()
    dep = r.json()
    doi = (
        dep.get("metadata", {}).get("prereserve_doi", {}).get("doi")
        or f"10.5281/zenodo.{dep['id']}"
    )

    # 1b. Optionally prepend the branded cover page.
    upload = pdf
    tmpdir = None
    if args.cover:
        import tempfile

        sys.path.insert(0, str(Path(__file__).parent))
        import coverpage

        tmpdir = tempfile.TemporaryDirectory()
        upload = Path(tmpdir.name) / f"IDEA-wp{args.number:04d}.pdf"
        coverpage.make_covered_pdf(meta, args.number, doi, pdf, upload)
        print(f"Cover page added (WP No. {args.number}, DOI {doi}).")

    # 2. Upload the PDF to the deposition's file bucket.
    with open(upload, "rb") as fh:
        r = requests.put(
            f"{dep['links']['bucket']}/{upload.name}", data=fh, headers=auth, timeout=300
        )
    r.raise_for_status()
    if tmpdir is not None:
        tmpdir.cleanup()

    # 3. Attach the metadata.
    r = requests.put(
        f"{base}/deposit/depositions/{dep['id']}",
        json={"metadata": deposit_metadata},
        headers=auth,
        timeout=30,
    )
    r.raise_for_status()

    print("Draft created (NOT yet published).")
    print(f"Review and publish here: {r.json()['links']['html']}")
    print("On publish, the record is submitted to the "
          f"'{COMMUNITY}' community for curator acceptance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
