"""Emit ReDIF templates (the metadata format RePEc crawls).

Specs: https://ideas.repec.org/t/archtemplate.html
       https://ideas.repec.org/t/seritemplate.html
       https://ideas.repec.org/t/papertemplate.html

Formatting rules observed here:
- Each field is ``Key: value``.  Long values wrap onto continuation
  lines indented with a single space (so they cannot be mistaken for a
  new ``Key:``).
- Author attributes must immediately follow their ``Author-Name:`` to
  form a cluster; likewise ``File-Format`` follows ``File-URL``.
- Files are written UTF-8; metadata for this series is expected to be
  essentially ASCII.
"""

from __future__ import annotations

import re
import textwrap

from .zenodo import Paper

WRAP = 78


def _clean(value: str) -> str:
    """Collapse whitespace/newlines so a value cannot break template structure."""
    return re.sub(r"\s+", " ", str(value)).strip()


def field(key: str, value: str) -> str:
    text = f"{key}: {_clean(value)}"
    return textwrap.fill(
        text, width=WRAP, subsequent_indent=" ", break_long_words=False, break_on_hyphens=False
    )


def paper_handle(archive_code: str, series_code: str, number: int) -> str:
    return f"RePEc:{archive_code}:{series_code}:{number}"


def archive_template(cfg: dict) -> str:
    r = cfg["repec"]
    lines = [
        field("Template-Type", "ReDIF-Archive 1.0"),
        field("Handle", f"RePEc:{r['archive_code']}"),
        field("Name", r["archive_name"]),
        field("Maintainer-Name", r["maintainer_name"]),
        field("Maintainer-Email", r["maintainer_email"]),
        field("Description", r["archive_description"]),
        field("URL", r["base_url"]),
    ]
    return "\n".join(lines) + "\n"


def series_template(cfg: dict) -> str:
    r = cfg["repec"]
    lines = [
        field("Template-Type", "ReDIF-Series 1.0"),
        field("Name", r["series_name"]),
        field("Description", r["series_description"]),
        field("Type", "ReDIF-Paper"),
        field("Provider-Name", r["provider_name"]),
        field("Provider-Homepage", r["provider_homepage"]),
    ]
    # Optional, and the only optional Provider-* field: the provider's
    # EDIRC handle, which lets RePEc cross-link the series with the
    # society's institution record.  A fork without an EDIRC record
    # leaves the key out of config.yaml.
    if r.get("provider_institution"):
        lines.append(field("Provider-Institution", r["provider_institution"]))
    lines += [
        field("Maintainer-Name", r["maintainer_name"]),
        field("Maintainer-Email", r["maintainer_email"]),
        field("Handle", f"RePEc:{r['archive_code']}:{r['series_code']}"),
    ]
    return "\n".join(lines) + "\n"


def paper_template(paper: Paper | None, entry: dict, cfg: dict) -> str:
    """ReDIF-Paper template for one working paper.

    ``paper`` is the live Zenodo record, or None if the record has been
    withdrawn from the community -- in which case a minimal template is
    built from the ledger snapshot, without a File cluster (per RePEc
    guidance on withdrawn papers).
    """
    r = cfg["repec"]
    number = entry["number"]
    lines = [field("Template-Type", "ReDIF-Paper 1.0")]

    if paper is not None:
        for c in paper.creators:
            lines.append(field("Author-Name", c["name"]))
            if c.get("affiliation"):
                lines.append(field("Author-Workplace-Name", c["affiliation"]))
        lines.append(field("Title", paper.title))
        if paper.abstract:
            lines.append(field("Abstract", paper.abstract))
        if paper.pub_date:
            lines.append(field("Creation-Date", paper.pub_date))
        if paper.pdf_url:
            lines.append(field("File-URL", paper.pdf_url))
            lines.append(field("File-Format", "application/pdf"))
        if paper.keywords:
            lines.append(field("Keywords", ", ".join(paper.keywords)))
        jel = entry.get("jel") or paper.jel
        if jel:
            lines.append(field("Classification-JEL", ", ".join(jel)))
        doi = paper.conceptdoi or paper.doi
        if doi:
            lines.append(field("DOI", doi))
    else:  # withdrawn: rebuild what we can from the ledger snapshot
        for name in entry.get("authors", []):
            lines.append(field("Author-Name", name))
        lines.append(field("Title", entry.get("title", f"IDEA Working Paper {number}")))
        if entry.get("date"):
            lines.append(field("Creation-Date", entry["date"]))
        lines.append(field("Note", "This paper has been withdrawn."))

    lines.append(field("Number", str(number)))
    lines.append(field("Handle", paper_handle(r["archive_code"], r["series_code"], number)))
    return "\n".join(lines) + "\n"
