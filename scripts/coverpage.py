#!/usr/bin/env python3
"""Prepend an IDEA Working Papers cover page to a paper PDF.

Usage:
    python scripts/coverpage.py metadata.yaml paper.pdf --number 1 \
        --doi 10.5281/zenodo.XXXXXX [-o covered.pdf]

Requires pdflatex (with tikz/geometry/hyperref) and pdfunite (poppler).
pdfunite is used for concatenation because it preserves the paper's
internal link annotations, which a pdfpages \\includepdf would drop.

Reads the same metadata YAML as deposit.py, plus optional cover fields:
    date_display: August 2026     # defaults to publication_date
    random_order: true            # typeset (r) between author names
"""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

TEMPLATE = Path(__file__).parent / "cover_template.tex"

LICENSES = {
    "cc-by-4.0": r"This work is licensed under a Creative Commons Attribution 4.0 International license.",
}


def tex_escape(s: str) -> str:
    out = ""
    for ch in str(s):
        out += {
            "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}", "\\": r"\textbackslash{}",
        }.get(ch, ch)
    return out


def display_name(name: str) -> str:
    """'Last, First' -> 'First Last' (leave other forms alone)."""
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}"
    return name


def month_year(date_str: str) -> str:
    try:
        d = datetime.date.fromisoformat(str(date_str))
        return d.strftime("%B %Y")
    except ValueError:
        return str(date_str)


def build_cover(meta: dict, number: int, doi: str, out_pdf: Path) -> None:
    creators = meta["creators"]
    sep = r" \textcircled{\scriptsize r} " if meta.get("random_order") else ", "
    names = [tex_escape(display_name(c["name"])) for c in creators]
    if meta.get("random_order") or len(names) <= 2:
        authors = sep.join(names)
    else:
        authors = ", ".join(names[:-1]) + ", and " + names[-1]

    # Unique affiliations, in author order.
    affs: list[str] = []
    for c in creators:
        a = c.get("affiliation")
        if a and a not in affs:
            affs.append(a)
    affiliations = " \\textperiodcentered{} ".join(tex_escape(a) for a in affs)

    date_disp = meta.get("date_display") or month_year(meta.get("publication_date", ""))
    year = str(meta.get("publication_date", datetime.date.today().isoformat()))[:4]
    jel = meta.get("jel") or []
    jelline = (
        r"\vspace{0.4em}{\normalsize JEL: " + tex_escape(", ".join(jel)) + r"\par}"
        if jel
        else ""
    )
    license_note = LICENSES.get(str(meta.get("license", "cc-by-4.0")).lower(), "")

    tex = TEMPLATE.read_text(encoding="utf-8")
    for key, val in {
        "@@NUMBER@@": str(number),
        "@@DATE@@": tex_escape(date_disp),
        "@@TITLE@@": tex_escape(meta["title"]),
        "@@AUTHORS@@": authors,
        "@@AFFILIATIONS@@": affiliations,
        "@@DOI@@": tex_escape(doi),
        "@@JELLINE@@": jelline,
        "@@YEAR@@": tex_escape(year),
        "@@LICENSE@@": license_note,
    }.items():
        tex = tex.replace(key, val)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "cover.tex").write_text(tex, encoding="utf-8")
        for _ in range(2):  # two passes for stable layout
            proc = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "cover.tex"],
                cwd=tmpdir, capture_output=True, text=True,
            )
        if proc.returncode != 0:
            tail = "\n".join(proc.stdout.splitlines()[-25:])
            sys.exit(f"pdflatex failed:\n{tail}")
        shutil.copy(tmpdir / "cover.pdf", out_pdf)


def prepend_cover(cover: Path, paper: Path, out: Path) -> None:
    proc = subprocess.run(
        ["pdfunite", str(cover), str(paper), str(out)], capture_output=True, text=True
    )
    if proc.returncode != 0:
        sys.exit(f"pdfunite failed: {proc.stderr}")


def make_covered_pdf(meta: dict, number: int, doi: str, paper: Path, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cover = Path(tmp) / "cover.pdf"
        build_cover(meta, number, doi, cover)
        prepend_cover(cover, paper, out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("metadata")
    ap.add_argument("pdf")
    ap.add_argument("--number", type=int, required=True, help="working paper number")
    ap.add_argument("--doi", required=True, help="DOI to print on the cover")
    ap.add_argument("-o", "--output", help="output path (default: <pdf>-wpN.pdf)")
    args = ap.parse_args()

    with open(args.metadata, encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    paper = Path(args.pdf)
    out = Path(args.output or paper.with_name(f"{paper.stem}-wp{args.number}.pdf"))
    make_covered_pdf(meta, args.number, args.doi, paper, out)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
