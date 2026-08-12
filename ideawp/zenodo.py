"""Fetch and parse records from a Zenodo community.

Uses the public API (no token required for published records):
  GET {api_base}/communities/{community}/records

The endpoint returns Zenodo's legacy serialization: integer ``id``,
string ``conceptrecid``, ``metadata.creators[].name`` ("Last, First"),
HTML ``metadata.description``, and a top-level ``files`` list.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote

import requests

TIMEOUT = 30

# A JEL classification code: letter + 1-2 digits (e.g. O12, Q18, D1).
_JEL_CODE = re.compile(r"^[A-Z]\d{1,2}$")
# A keyword that is a list of JEL codes, optionally prefixed "JEL"/"JEL:".
_JEL_KEYWORD = re.compile(
    r"^(?:JEL(?:\s+codes?)?[:\s]+)?([A-Z]\d{1,2}(?:[,;\s]+[A-Z]\d{1,2})*)$",
    re.IGNORECASE,
)


class _TextExtractor(HTMLParser):
    """Reduce Zenodo's HTML descriptions to plain text."""

    def __init__(self) -> None:
        super().__init__()
        self.chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        self.chunks.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("p", "br", "div", "li"):
            self.chunks.append(" ")


def strip_html(text: str) -> str:
    """Return plain text: tags removed, entities unescaped, whitespace collapsed."""
    if not text:
        return ""
    parser = _TextExtractor()
    parser.feed(html.unescape(text))
    return re.sub(r"\s+", " ", "".join(parser.chunks)).strip()


def split_keywords(raw_keywords: list[str] | None) -> tuple[list[str], list[str]]:
    """Split Zenodo keywords into (keywords, jel_codes).

    Keywords that consist of JEL classification codes (optionally
    prefixed with "JEL:") are routed to the JEL list; everything else
    stays a keyword.
    """
    keywords: list[str] = []
    jel: list[str] = []
    for kw in raw_keywords or []:
        kw = kw.strip()
        if not kw:
            continue
        m = _JEL_KEYWORD.match(kw)
        if m:
            codes = re.split(r"[,;\s]+", m.group(1))
            jel.extend(c.upper() for c in codes if _JEL_CODE.match(c.upper()))
        else:
            keywords.append(kw)
    return keywords, jel


@dataclass
class Paper:
    recid: int
    conceptrecid: str
    doi: str
    conceptdoi: str
    title: str
    creators: list[dict]  # {name, affiliation?, orcid?}
    abstract: str
    pub_date: str  # yyyy-mm-dd (Zenodo publication_date)
    keywords: list[str] = field(default_factory=list)
    jel: list[str] = field(default_factory=list)
    pdf_url: str = ""
    html_url: str = ""

    @property
    def doi_url(self) -> str:
        """Prefer the concept DOI: it always resolves to the latest version."""
        return f"https://doi.org/{self.conceptdoi or self.doi}"


def parse_record(hit: dict) -> Paper:
    md = hit.get("metadata", {})
    keywords, jel = split_keywords(md.get("keywords"))
    recid = int(hit["id"])

    pdf_url = ""
    for f in hit.get("files") or []:
        if f.get("key", "").lower().endswith(".pdf"):
            pdf_url = (
                f"https://zenodo.org/records/{recid}/files/"
                f"{quote(f['key'])}?download=1"
            )
            break

    return Paper(
        recid=recid,
        conceptrecid=str(hit.get("conceptrecid", "")),
        doi=hit.get("doi", "") or md.get("doi", ""),
        conceptdoi=hit.get("conceptdoi", ""),
        title=strip_html(md.get("title", "")),
        creators=[
            {
                k: v
                for k, v in {
                    "name": c.get("name", "").strip(),
                    "affiliation": c.get("affiliation"),
                    "orcid": c.get("orcid"),
                }.items()
                if v
            }
            for c in md.get("creators", [])
        ],
        abstract=strip_html(md.get("description", "")),
        pub_date=md.get("publication_date", ""),
        keywords=keywords,
        jel=jel,
        pdf_url=pdf_url,
        html_url=hit.get("links", {}).get("self_html", f"https://zenodo.org/records/{recid}"),
    )


def fetch_community_records(api_base: str, community: str, page_size: int = 25) -> list[Paper]:
    """Return all published records in a community, oldest first.

    Raises on any HTTP error: a failed fetch must never be mistaken
    for an empty community (papers would look withdrawn).

    Zenodo rejects page sizes above 25 for unauthenticated requests;
    pagination follows the ``links.next`` URL until exhausted.
    """
    url = f"{api_base}/communities/{community}/records"
    params: dict | None = {"size": page_size, "sort": "oldest"}
    papers: list[Paper] = []
    while url:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        papers.extend(parse_record(h) for h in data["hits"]["hits"])
        url = data.get("links", {}).get("next")
        params = None  # the `next` link already carries query parameters
    return papers
