"""BibTeX entries for working papers.

Built from the same Zenodo metadata that feeds the ReDIF tree, so the
citation a reader copies off the site cannot drift from the record
RePEc indexes.

Entry type is ``@techreport``.  Under biblatex that is a *hard alias*
for ``@report`` -- the backend rewrites it before any style sees it
(biblatex manual sec. 2.1.2) -- while traditional BibTeX ``.bst``
styles, which most economics journals still ship, know ``@techreport``
and not ``@report``.  So ``@techreport`` costs biblatex users nothing
and keeps the entry usable in AER/Econometrica-style templates; it is
also what IDEAS and EconPapers emit for working-paper series.

``type`` is set explicitly to "Working Paper", which overrides the
alias's default of "technical report" and prints as "Working Paper 3"
under both engines.

The ``doi``/``url`` fields carry the *concept* DOI, following the same
convention as the cover page, so a citation keeps resolving after the
author posts a revision.
"""

from __future__ import annotations

import re
import unicodedata

from .zenodo import Paper

_SPECIALS = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "#": r"\#",
    "$": r"\$",
    "%": r"\%",
    "&": r"\&",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

# Substituted in a single pass.  Replacing one character at a time in
# sequence would corrupt the output whichever order was chosen: the
# replacements for \ ~ ^ themselves contain braces, so a later brace
# rule would escape braces this function had just emitted.
_SPECIAL_RE = re.compile("[" + re.escape("".join(_SPECIALS)) + "]")

_MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)

# Words that make an uninformative first word for a citation key.
_STOPWORDS = frozenset(
    """a an the and or but of on in at to for from with by is are do does
    when what why how""".split()
)


def escape(text: str) -> str:
    """Escape TeX special characters in a field value.

    Accented characters are left as UTF-8: the .bib files are UTF-8 and
    both biber and modern BibTeX read them, which keeps author names
    legible in the source rather than turning them into \\'{e} noise.
    """
    return _SPECIAL_RE.sub(lambda m: _SPECIALS[m.group()], text)


def _fold(text: str) -> str:
    """Drop diacritics, so citation keys stay ASCII (Pena, not Peña)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def cite_key(paper: Paper, taken: frozenset[str] | set[str] = frozenset()) -> str:
    """Return <surname><year><first significant title word>.

    For example ``dureja2026heat``.  On collision a letter is appended
    (``...b``, ``...c``), so a paper's key is stable as long as the
    papers ahead of it in the ledger do not change.
    """
    surname = paper.creators[0]["name"].split(",")[0] if paper.creators else ""
    surname = re.sub(r"[^a-z]", "", _fold(surname).lower()) or "anon"

    year = paper.pub_date[:4] if paper.pub_date else ""

    word = ""
    for token in re.findall(r"[A-Za-z]+", _fold(paper.title)):
        token = token.lower()
        if token not in _STOPWORDS:
            word = token
            break

    key = f"{surname}{year}{word}"
    if key not in taken:
        return key
    for suffix in "bcdefghijklmnopqrstuvwxyz":
        if key + suffix not in taken:
            return key + suffix
    return key  # 26 papers sharing a key: return the collision rather than loop


def entry(paper: Paper, ledger_entry: dict, cfg: dict, key: str) -> str:
    """Render one @techreport entry."""
    r = cfg["repec"]
    lines = [f"@techreport{{{key},"]

    def add(name: str, value: str, braced: bool = True) -> None:
        body = f"{{{value}}}" if braced else value
        lines.append(f"  {name:<11} = {body},")

    if paper.creators:
        add("author", " and ".join(escape(c["name"]) for c in paper.creators))
    # The inner braces protect capitalization from styles that would
    # otherwise lowercase the title.
    add("title", "{" + escape(paper.title) + "}")
    if paper.pub_date:
        add("year", paper.pub_date[:4])
        month = _month(paper.pub_date)
        if month:
            add("month", month, braced=False)
    add("institution", escape(r["provider_name"]))
    add("type", "Working Paper")
    add("series", escape(r["series_name"]))
    add("number", str(ledger_entry["number"]))
    doi = paper.conceptdoi or paper.doi
    if doi:
        add("doi", escape(doi))
    add("url", escape(paper.doi_url))
    lines.append("}")
    return "\n".join(lines)


def _month(pub_date: str) -> str:
    """Map yyyy-mm-dd to a BibTeX month macro (jan, feb, ...)."""
    try:
        return _MONTHS[int(pub_date[5:7]) - 1]
    except (ValueError, IndexError):
        return ""


def bibliography(entries: list[str]) -> str:
    """Join entries into one .bib file."""
    return "\n\n".join(entries) + "\n"
