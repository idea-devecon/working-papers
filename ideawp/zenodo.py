"""Fetch and parse records from a Zenodo community.

Uses the public API (no token required for published records):
  GET {api_base}/communities/{community}/records

The endpoint returns Zenodo's legacy serialization: integer ``id``,
string ``conceptrecid``, ``metadata.creators[].name`` ("Last, First"),
HTML ``metadata.description``, and a top-level ``files`` list.
"""

from __future__ import annotations

import html
import json
import re
import threading
from concurrent.futures import Future, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import quote

import time

import requests

# (connect, read) for a single attempt.
TIMEOUT = (10, 60)

# Zenodo asks unauthenticated clients to identify themselves.
USER_AGENT = "ideawp-build (+https://github.com/idea-devecon/working-papers)"

# Zenodo is briefly unavailable often enough that a nightly build must
# retry.  The retrying is done here rather than with a urllib3 Retry
# adapter: the adapter retries only the header phase, and this endpoint
# is served chunked and gzipped, so a stall while the body streams --
# an ordinary failure -- would get a single attempt.  Wrapping the
# request, the body read and the JSON parse covers both phases.
MAX_ATTEMPTS = 6
BACKOFF_BASE = 2.0  # seconds, doubling per attempt
BACKOFF_CAP = 32.0
# Zenodo sends Retry-After on 200s as well as 429s, so honour it but
# never sleep on it indefinitely.
RETRY_AFTER_CAP = 60.0
# Bounds the whole fetch, every page included, so the worst case does
# not scale with the number of pages.
FETCH_DEADLINE = 480.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class ZenodoUnreachable(RuntimeError):
    """Zenodo did not answer after repeated attempts."""

    def __init__(self, message: str, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class FetchIncomplete(RuntimeError):
    """Zenodo answered, but returned fewer records than it reported."""


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def _retry_after(resp) -> float | None:
    """Seconds requested by a Retry-After header, if it is in delta form."""
    if resp is None:
        return None
    raw = resp.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(int(raw)))
    except ValueError:
        return None  # HTTP-date form; our own backoff will do


def _get_json(session, url, params, deadline) -> tuple[dict, int]:
    """GET one page, retrying transient failures.  Returns (data, attempts).

    Raises ZenodoUnreachable once the attempts or the deadline are spent,
    and re-raises immediately for a status that means our request is
    wrong (any 4xx but 429) -- retrying that would only repeat the error.
    """
    attempt = 0
    while True:
        if time.monotonic() >= deadline:
            raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempt)
        attempt += 1
        try:
            return _read_json(session, url, params, deadline, attempt), attempt
        except (requests.RequestException, json.JSONDecodeError) as exc:
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if status is not None and status not in RETRY_STATUSES:
                raise
            if attempt >= MAX_ATTEMPTS:
                raise ZenodoUnreachable(
                    f"Zenodo unreachable after {attempt} attempts "
                    f"({exc.__class__.__name__})",
                    attempt,
                ) from exc
            delay = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_CAP)
            asked = _retry_after(resp)
            if asked is not None:
                delay = min(max(delay, asked), RETRY_AFTER_CAP)
            if time.monotonic() + delay >= deadline:
                raise ZenodoUnreachable(
                    f"Zenodo still failing after {attempt} attempts; the "
                    f"{FETCH_DEADLINE:.0f}s fetch deadline is spent "
                    f"({exc.__class__.__name__})",
                    attempt,
                ) from exc
            time.sleep(delay)


def _read_json(session, url, params, deadline, attempt) -> dict:
    """Bound the caller's wait, including headers, body and JSON decoding.

    Socket timeouts alone permit an indefinitely trickling response. A daemon
    reader owns and closes the response, and checks the deadline between bytes
    so it unwinds on the next byte or socket timeout after the caller refuses.
    It never mutates pipeline state or starts another request (ledger section 5).
    """
    result = Future()

    def read():
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempt)
            timeout = tuple(min(t, remaining) for t in TIMEOUT)
            with session.get(url, params=params, timeout=timeout, stream=True) as resp:
                if resp.status_code in RETRY_STATUSES:
                    raise requests.exceptions.HTTPError(
                        f"HTTP {resp.status_code} from Zenodo", response=resp
                    )
                resp.raise_for_status()
                body = bytearray()
                for chunk in resp.iter_content(chunk_size=1):
                    if time.monotonic() >= deadline:
                        raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempt)
                    body.extend(chunk)
                data = json.loads(body)
            result.set_result(data)
        except BaseException as exc:
            result.set_exception(exc)

    threading.Thread(target=read, daemon=True).start()
    try:
        data = result.result(timeout=max(0.0, deadline - time.monotonic()))
    except FutureTimeout as exc:
        raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempt) from exc
    if time.monotonic() >= deadline:
        raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempt)
    return data


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


def fetch_community_records(
    api_base: str,
    community: str,
    page_size: int = 25,
    session: requests.Session | None = None,
) -> list[Paper]:
    """Return all published records in a community, oldest first.

    Raises rather than returning a partial or empty list: a short fetch
    must never be mistaken for a shrunken community, because the caller
    turns absence into RePEc withdrawal notices.  Three ways this fails:
    ZenodoUnreachable (no answer), FetchIncomplete (answered, but fewer
    records than it reported), or requests.HTTPError (4xx -- our request
    is wrong, e.g. the community was renamed).

    Zenodo rejects page sizes above 25 for unauthenticated requests;
    pagination follows the ``links.next`` URL until exhausted.
    """
    url = f"{api_base}/communities/{community}/records"
    params: dict | None = {"size": page_size, "sort": "oldest"}
    papers: list[Paper] = []
    reported: int | None = None
    deadline = time.monotonic() + FETCH_DEADLINE
    s = session or make_session()
    try:
        seen_urls: set[str] = set()
        attempts = 0
        while url:
            if url in seen_urls:  # a self-referential links.next
                raise FetchIncomplete(
                    f"Zenodo pagination revisited {url}; refusing to loop."
                )
            seen_urls.add(url)
            data, attempts = _get_json(s, url, params, deadline)
            hits = data["hits"]
            if reported is None:
                total = hits.get("total")
                # Zenodo's legacy serialization gives an int; InvenioRDM
                # may nest it as {"value": n}.
                reported = total.get("value") if isinstance(total, dict) else total
            papers.extend(parse_record(h) for h in hits["hits"])
            url = data.get("links", {}).get("next")
            params = None  # the `next` link already carries query parameters
    finally:
        if session is None:  # only close a session we made
            s.close()

    if isinstance(reported, int) and len(papers) != reported:
        raise FetchIncomplete(
            f"Zenodo reported {reported} record(s) but returned {len(papers)}."
        )
    if time.monotonic() >= deadline:
        raise ZenodoUnreachable("Zenodo fetch deadline is spent", attempts)
    return papers
