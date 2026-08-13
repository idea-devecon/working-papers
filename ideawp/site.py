"""Generate the human-facing index page for the series."""

from __future__ import annotations

import html

from . import bibtex
from .redif import paper_handle
from .zenodo import Paper

# Typography and palette follow idea.devecon.org, so the series does not
# look like a different organisation from its parent society.  The three
# families are the parent's (Archivo Black display, Libre Franklin text,
# Space Mono for identifiers), but served from assets/fonts/ rather than
# Google's CDN: no third-party request, and an archive that outlives its
# editor should not depend on someone else's uptime.  All three are
# SIL Open Font License 1.1; each family's licence is kept verbatim
# beside the files, in assets/fonts/OFL-*.txt.
#
# Both subsets share the same two unicode-ranges across all three
# families, so they are named once here.
_LATIN = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,"
    "U+2212,U+2215,U+FEFF,U+FFFD"
)
_LATIN_EXT = (
    "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,"
    "U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,"
    "U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
)


def _face(family: str, filename: str, weight: str, urange: str) -> str:
    return (
        f"@font-face{{font-family:'{family}';font-style:normal;"
        f"font-weight:{weight};font-display:swap;"
        f"src:url(assets/fonts/{filename}) format('woff2');"
        f"unicode-range:{urange}}}"
    )


# Libre Franklin is a variable font (wght 100-900): one file covers every
# weight, so it is declared with a range rather than shipped twice.
_FONTS = "\n".join(
    _face(fam, f"{stem}-{sub}.woff2", wt, rng)
    for fam, stem, wt in (
        ("Archivo Black", "archivo-black-400", "400"),
        ("Libre Franklin", "libre-franklin-var", "100 900"),
        ("Space Mono", "space-mono-400", "400"),
    )
    for sub, rng in (("latin", _LATIN), ("latin-ext", _LATIN_EXT))
)

_STYLE = (
    _FONTS
    + """
:root {
  --bg: #fefdfb; --fg: #1a1714; --muted: #666; --accent: #1d6e87;
  --accent-hover: #155a6e; --rule: #dad6cf; --card: #f7f6f3;
  --sans: 'Libre Franklin', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --display: 'Archivo Black', 'Libre Franklin', sans-serif;
  --mono: 'Space Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --serif: Georgia, 'Times New Roman', serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1714; --fg: #f0ece6; --muted: #a19a91; --accent: #7ec3d8;
    --accent-hover: #a3d6e6; --rule: #3a342e; --card: #221e1a;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 var(--sans);
}
a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent-hover); text-decoration: underline; }
header {
  border-bottom: 3px solid var(--rule); padding: 2.5rem 1rem 1.5rem;
  text-align: center;
}
header h1 {
  font-family: var(--display); margin: 0 0 .6rem; font-size: 1.85rem;
  letter-spacing: -.01em; line-height: 1.2;
}
header p { margin: .25rem auto; max-width: 44rem; color: var(--muted); }
main { max-width: 46rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
article { border-bottom: 1px solid var(--rule); padding: 1.4rem 0; }
.wpno {
  font-family: var(--mono); color: var(--muted); font-size: .78rem;
  letter-spacing: .02em; margin: 0;
}
article h2 {
  font-weight: 700; margin: .25rem 0 .3rem; font-size: 1.2rem;
  line-height: 1.3; letter-spacing: -.005em;
}
.authors { margin: 0 0 .2rem; }
.meta { font-family: var(--mono); color: var(--muted); font-size: .8rem; }
details { margin-top: .5rem; }
summary { cursor: pointer; color: var(--accent); font-size: .9rem; }
summary:hover { color: var(--accent-hover); }
details p {
  margin: .5rem 0 0; color: var(--fg); font-family: var(--serif);
  line-height: 1.65;
}
.links { font-family: var(--mono); margin-top: .55rem; font-size: .82rem; }
.links a { margin-right: 1.1rem; }
.kw {
  font-family: var(--mono); font-size: .76rem; color: var(--muted);
  margin-top: .35rem; line-height: 1.5;
}
footer {
  border-top: 1px solid var(--rule); color: var(--muted);
  font-size: .85rem; text-align: center; padding: 1.5rem 1rem 2.5rem;
}
.empty { text-align: center; color: var(--muted); padding: 3rem 0; }
.bibwrap { position: relative; }
.bibwrap pre {
  font-family: var(--mono); font-size: .74rem; line-height: 1.55;
  background: var(--card); border: 1px solid var(--rule);
  border-radius: 4px; padding: .85rem 1rem; margin: .5rem 0 0;
  overflow-x: auto; white-space: pre;
}
button.copy {
  position: absolute; top: .95rem; right: .5rem; z-index: 1;
  font-family: var(--mono); font-size: .7rem; cursor: pointer;
  color: var(--accent); background: var(--bg);
  border: 1px solid var(--rule); border-radius: 3px; padding: .2rem .5rem;
}
button.copy:hover { color: var(--accent-hover); border-color: var(--accent); }
"""
)


BIB_FILENAME = "idea-working-papers.bib"

# One delegated listener rather than one per entry, so the cost does not
# grow with the series.  Without JS the entry is still there to select
# by hand, which is why the <pre> holds the text and the button only
# copies it.
_COPY_JS = """
document.addEventListener('click', function (ev) {
  var btn = ev.target.closest('.copy');
  if (!btn) return;
  var pre = btn.parentElement.querySelector('pre');
  if (!pre || !navigator.clipboard) return;
  navigator.clipboard.writeText(pre.textContent).then(function () {
    btn.textContent = 'Copied';
    setTimeout(function () { btn.textContent = btn.dataset.label; }, 1500);
  }, function () {
    btn.textContent = 'Press Ctrl+C';
    setTimeout(function () { btn.textContent = btn.dataset.label; }, 2000);
  });
});
"""


def _paper_entry(paper: Paper, entry: dict, cfg: dict, key: str) -> str:
    r = cfg["repec"]
    e = html.escape
    number = entry["number"]
    handle = paper_handle(r["archive_code"], r["series_code"], number)
    authors = ", ".join(e(c["name"]) for c in paper.creators)
    links = [f'<a href="{e(paper.doi_url)}">DOI</a>']
    if paper.pdf_url:
        links.insert(0, f'<a href="{e(paper.pdf_url)}">PDF</a>')
    links.append(f'<a href="{e(paper.html_url)}">Zenodo</a>')
    abstract = (
        f"<details><summary>Abstract</summary><p>{e(paper.abstract)}</p></details>"
        if paper.abstract
        else ""
    )
    kw = ""
    bits = list(paper.keywords)
    if entry.get("jel") or paper.jel:
        bits.append("JEL: " + ", ".join(entry.get("jel") or paper.jel))
    if bits:
        kw = f'<p class="kw">{e(" · ".join(bits))}</p>'
    bib = bibtex.entry(paper, entry, cfg, key)
    bib_block = (
        '<details class="bib"><summary>BibTeX</summary>'
        '<div class="bibwrap">'
        '<button class="copy" type="button" data-label="Copy">Copy</button>'
        f"<pre>{e(bib)}</pre></div></details>"
    )
    return f"""<article>
<p class="wpno">Working Paper No. {number} · <span class="meta">{e(handle)}</span></p>
<h2><a href="{e(paper.doi_url)}">{e(paper.title)}</a></h2>
<p class="authors">{authors}</p>
<p class="meta">{e(paper.pub_date)}</p>
{abstract}
{kw}
<p class="links">{" ".join(links)}</p>
{bib_block}
</article>"""


def dir_index(title: str, entries: list[str]) -> str:
    """Simulated directory listing.

    GitHub Pages does not autoindex directories, but the RePEc crawler
    discovers files by listing each directory; RePEc's docs sanction a
    default file (index.html) that links to the directory's contents.
    See https://ideas.repec.org/t/httpserver.html
    """
    e = html.escape
    links = "\n".join(f'<br/><a href="{e(x)}">{e(x)}</a>' for x in entries)
    return f"<!doctype html>\n<html>\n<head><title>{e(title)}</title></head>\n<body>\n{links}\n</body>\n</html>\n"


def cite_keys(papers_by_concept: dict[str, Paper], ledger: dict) -> dict[str, str]:
    """Map conceptrecid -> BibTeX citation key.

    Allocated in ascending working-paper number so that a new paper
    cannot change the key of an older one: readers cite these, and a
    key that moved would silently break a bibliography.
    """
    keys: dict[str, str] = {}
    taken: set[str] = set()
    for entry in sorted(ledger["papers"], key=lambda x: x["number"]):
        paper = papers_by_concept.get(entry["conceptrecid"])
        if paper is None or entry.get("withdrawn"):
            continue
        key = bibtex.cite_key(paper, taken)
        taken.add(key)
        keys[entry["conceptrecid"]] = key
    return keys


def bib_file(papers_by_concept: dict[str, Paper], ledger: dict, cfg: dict) -> str:
    """The whole series as one .bib file."""
    keys = cite_keys(papers_by_concept, ledger)
    return bibtex.bibliography(
        [
            bibtex.entry(papers_by_concept[entry["conceptrecid"]], entry, cfg,
                         keys[entry["conceptrecid"]])
            for entry in sorted(ledger["papers"], key=lambda x: x["number"])
            if entry["conceptrecid"] in keys
        ]
    )


def index_html(papers_by_concept: dict[str, Paper], ledger: dict, cfg: dict) -> str:
    s, r = cfg["site"], cfg["repec"]
    e = html.escape
    keys = cite_keys(papers_by_concept, ledger)
    entries = [
        _paper_entry(papers_by_concept[entry["conceptrecid"]], entry, cfg,
                     keys[entry["conceptrecid"]])
        for entry in sorted(ledger["papers"], key=lambda x: -x["number"])
        if entry["conceptrecid"] in keys
    ]
    body = "\n".join(entries) if entries else '<p class="empty">No papers published yet.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(s["title"])}</title>
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<style>{_STYLE}</style>
</head>
<body>
<header>
<h1>{e(s["title"])}</h1>
<p>{e(r["series_description"])}</p>
<p>A series of the <a href="{e(s["homepage"])}">International Development
Economics Association</a>. To submit a paper, contact the series editor at
<a href="mailto:{e(s["contact_email"])}">{e(s["contact_email"])}</a>.</p>
</header>
<main>
{body}
</main>
<footer>
<p>Papers are archived on <a href="https://zenodo.org/communities/{e(cfg["zenodo"]["community"])}/">Zenodo</a>
and indexed by <a href="https://ideas.repec.org/">RePEc/IDEAS</a>.
Machine-readable metadata: <a href="/RePEc/{e(r["archive_code"])}/">/RePEc/{e(r["archive_code"])}/</a>.
Every entry as one file: <a href="{e(BIB_FILENAME)}">{e(BIB_FILENAME)}</a>.</p>
</footer>
<script>{_COPY_JS}</script>
</body>
</html>
"""
