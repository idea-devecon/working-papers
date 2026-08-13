"""Build the site: fetch Zenodo records, update the ledger, write ReDIF + HTML.

Usage:
    python -m ideawp.build [--config config.yaml] [--ledger papers.yaml]

Idempotent: safe to run on a schedule.  Fails loudly on any Zenodo API
error rather than emitting a tree that would look like mass withdrawal.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from . import ledger as ledger_mod
from . import redif, site, zenodo


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build(cfg: dict, ledger_path: str | Path) -> dict:
    r = cfg["repec"]
    out = Path(cfg["site"]["output_dir"])
    arch_dir = out / "RePEc" / r["archive_code"]
    wp_dir = arch_dir / r["series_code"]

    papers = zenodo.fetch_community_records(
        cfg["zenodo"]["api_base"], cfg["zenodo"]["community"]
    )
    ledger = ledger_mod.load(ledger_path)
    new = ledger_mod.sync(ledger, papers)
    ledger_mod.save(ledger_path, ledger)

    by_concept = {p.conceptrecid: p for p in papers}

    # Clean rebuild of the ReDIF tree (the ledger, not the tree, is state).
    if wp_dir.exists():
        shutil.rmtree(wp_dir)
    wp_dir.mkdir(parents=True)

    # .redif extension signals UTF-8 to RePEc (.rdf would imply ASCII);
    # see https://ideas.repec.org/newmaintainer.html
    code = r["archive_code"]
    (arch_dir / f"{code}arch.redif").write_text(redif.archive_template(cfg), encoding="utf-8")
    (arch_dir / f"{code}seri.redif").write_text(redif.series_template(cfg), encoding="utf-8")
    wp_files = []
    for entry in ledger["papers"]:
        paper = by_concept.get(entry["conceptrecid"])
        rdf = redif.paper_template(paper, entry, cfg)
        fname = f"{code}{entry['number']:04d}.redif"
        (wp_dir / fname).write_text(rdf, encoding="utf-8")
        wp_files.append(fname)

    # Simulated directory listings so the RePEc crawler can discover
    # files (GitHub Pages has no autoindex).
    (out / "RePEc" / "index.html").write_text(
        site.dir_index("RePEc", [f"{code}/"]), encoding="utf-8"
    )
    (arch_dir / "index.html").write_text(
        site.dir_index(f"RePEc:{code}", [f"{code}arch.redif", f"{code}seri.redif", f"{r['series_code']}/"]),
        encoding="utf-8",
    )
    (wp_dir / "index.html").write_text(
        site.dir_index(f"RePEc:{code}:{r['series_code']}", wp_files), encoding="utf-8"
    )

    (out / "index.html").write_text(
        site.index_html(by_concept, ledger, cfg), encoding="utf-8"
    )
    (out / ".nojekyll").write_text("", encoding="utf-8")

    # Static assets (self-hosted webfonts, and their licences) live in the
    # repository; the site tree is disposable and rebuilt from them.
    assets = Path(__file__).resolve().parent.parent / "assets"
    if assets.is_dir():
        shutil.copytree(assets, out / "assets", dirs_exist_ok=True)

    return {
        "papers": len(ledger["papers"]),
        "new": [e["number"] for e in new],
        "withdrawn": [e["number"] for e in ledger["papers"] if e.get("withdrawn")],
        "output": str(out),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--ledger", default="papers.yaml")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    summary = build(cfg, args.ledger)
    print(
        f"Built {summary['output']}: {summary['papers']} paper(s) in ledger; "
        f"new: {summary['new'] or 'none'}; withdrawn: {summary['withdrawn'] or 'none'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
