"""Generate the human-facing index page for the series."""

from __future__ import annotations

import html

from .redif import paper_handle
from .zenodo import Paper

_STYLE = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #5a6270; --accent: #14532d;
  --accent-2: #1a7a43; --rule: #e3e6ea; --card: #f7f8f9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14181d; --fg: #e8eaed; --muted: #9aa4b2; --accent: #7fd4a3;
    --accent-2: #5cbb85; --rule: #2a313a; --card: #1c2129;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 17px/1.6 Georgia, 'Times New Roman', serif;
}
header {
  border-bottom: 3px double var(--rule); padding: 2.5rem 1rem 1.5rem;
  text-align: center;
}
header h1 { margin: 0 0 .35rem; font-size: 1.9rem; letter-spacing: .01em; }
header p { margin: .25rem auto; max-width: 44rem; color: var(--muted); }
header a { color: var(--accent-2); }
main { max-width: 46rem; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
article {
  border-bottom: 1px solid var(--rule); padding: 1.4rem 0;
}
.wpno { color: var(--muted); font-size: .85rem; letter-spacing: .04em; }
article h2 { margin: .15rem 0 .3rem; font-size: 1.25rem; }
article h2 a { color: var(--accent); text-decoration: none; }
article h2 a:hover { text-decoration: underline; }
.authors { margin: 0 0 .2rem; }
.meta { color: var(--muted); font-size: .9rem; }
details { margin-top: .5rem; }
summary { cursor: pointer; color: var(--accent-2); font-size: .95rem; }
details p { margin: .5rem 0 0; color: var(--fg); }
.links { margin-top: .55rem; font-size: .95rem; }
.links a {
  color: var(--accent-2); margin-right: 1.1rem; text-decoration: none;
}
.links a:hover { text-decoration: underline; }
.kw { font-size: .85rem; color: var(--muted); margin-top: .35rem; }
footer {
  border-top: 1px solid var(--rule); color: var(--muted);
  font-size: .85rem; text-align: center; padding: 1.5rem 1rem 2.5rem;
}
footer a { color: var(--accent-2); }
.empty { text-align: center; color: var(--muted); padding: 3rem 0; }
"""


def _paper_entry(paper: Paper, entry: dict, cfg: dict) -> str:
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
    return f"""<article>
<p class="wpno">Working Paper No. {number} · <span class="meta">{e(handle)}</span></p>
<h2><a href="{e(paper.doi_url)}">{e(paper.title)}</a></h2>
<p class="authors">{authors}</p>
<p class="meta">{e(paper.pub_date)}</p>
{abstract}
{kw}
<p class="links">{" ".join(links)}</p>
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


def index_html(papers_by_concept: dict[str, Paper], ledger: dict, cfg: dict) -> str:
    s, r = cfg["site"], cfg["repec"]
    e = html.escape
    entries = [
        _paper_entry(papers_by_concept[entry["conceptrecid"]], entry, cfg)
        for entry in sorted(ledger["papers"], key=lambda x: -x["number"])
        if entry["conceptrecid"] in papers_by_concept and not entry.get("withdrawn")
    ]
    body = "\n".join(entries) if entries else '<p class="empty">No papers published yet.</p>'
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(s["title"])}</title>
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
Machine-readable metadata: <a href="/RePEc/{e(r["archive_code"])}/">/RePEc/{e(r["archive_code"])}/</a>.</p>
</footer>
</body>
</html>
"""
