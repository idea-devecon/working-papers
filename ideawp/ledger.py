"""The paper ledger: a committed YAML file mapping Zenodo records to WP numbers.

Working-paper numbers are assigned once and never reused or renumbered;
the ledger (papers.yaml) is the authority.  Records are keyed by Zenodo
``conceptrecid``, which is stable across versions of a record, so a
revised paper keeps its number (and its RePEc handle).

Each entry snapshots enough metadata (title, authors, date) to keep
emitting a minimal ReDIF template if a record is later removed from the
community ("withdrawn": RePEc convention is to keep the template but
drop the File cluster).

Editors may add a ``jel`` list to an entry by hand; it overrides JEL
codes parsed from Zenodo keywords.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import yaml

from .zenodo import Paper


def load(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {"next_number": 1, "papers": []}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("next_number", 1)
    data.setdefault("papers", [])
    return data


def save(path: str | Path, ledger: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("# IDEA Working Papers ledger.  Numbers are assigned once and never\n")
        f.write("# reused.  Maintained by the build pipeline; editors may add per-\n")
        f.write("# paper overrides (e.g. 'jel: [O12, Q18]') by hand.\n")
        yaml.safe_dump(ledger, f, sort_keys=False, allow_unicode=True, width=79)


def sync(ledger: dict, papers: list[Paper], today: str | None = None) -> list[dict]:
    """Assign numbers to unseen papers; refresh snapshots; flag withdrawals.

    Mutates ``ledger`` in place and returns the list of newly added
    entries.  ``papers`` must be the *complete* current contents of the
    community (oldest first), from a successful fetch.
    """
    today = today or datetime.date.today().isoformat()
    by_concept = {e["conceptrecid"]: e for e in ledger["papers"]}
    seen = set()
    new_entries = []

    for p in sorted(papers, key=lambda p: (p.pub_date, int(p.conceptrecid or 0))):
        if not p.conceptrecid:
            raise ValueError(f"record {p.recid} has no conceptrecid")
        seen.add(p.conceptrecid)
        entry = by_concept.get(p.conceptrecid)
        if entry is None:
            entry = {
                "number": ledger["next_number"],
                "conceptrecid": p.conceptrecid,
                "added": today,
            }
            ledger["next_number"] += 1
            ledger["papers"].append(entry)
            by_concept[p.conceptrecid] = entry
            new_entries.append(entry)
        # Refresh the snapshot (title/authors may change across versions).
        entry["title"] = p.title
        entry["authors"] = [c["name"] for c in p.creators]
        entry["date"] = p.pub_date
        entry.pop("withdrawn", None)

    for entry in ledger["papers"]:
        if entry["conceptrecid"] not in seen:
            entry["withdrawn"] = True

    ledger["papers"].sort(key=lambda e: e["number"])
    return new_entries
