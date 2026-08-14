"""Tests for the Zenodo -> ReDIF pipeline (parser, ledger, templates)."""

import json
import re
from pathlib import Path

import pytest
import yaml

from ideawp import ledger as ledger_mod
from ideawp import bibtex, redif, site, zenodo

FIXTURE = Path(__file__).parent / "fixtures" / "community_records.json"
CONFIG = Path(__file__).parent.parent / "config.yaml"


@pytest.fixture
def cfg():
    with open(CONFIG) as f:
        return yaml.safe_load(f)


@pytest.fixture
def papers():
    hits = json.loads(FIXTURE.read_text())["hits"]["hits"]
    return [zenodo.parse_record(h) for h in hits]


# ---------------------------------------------------------------- parsing

def test_parse_basics(papers):
    p = papers[0]
    assert p.recid == 11111111
    assert p.conceptrecid == "11111110"
    assert p.title == "Credit Constraints & Smallholder Technology Adoption"
    assert [c["name"] for c in p.creators] == ["Doe, Jane", "Rao, Anand"]
    assert p.creators[0]["affiliation"] == "University of Nairobi"
    assert "affiliation" not in p.creators[1]


def test_abstract_html_stripped(papers):
    a = papers[0].abstract
    assert "<" not in a and ">" not in a
    assert "credit constraints" in a
    assert "Results suggest" in a  # both <p>s survive, separated
    assert " " not in a  # &nbsp; collapsed


def test_jel_split_from_keywords(papers):
    p = papers[0]
    assert p.keywords == ["technology adoption", "credit"]
    assert p.jel == ["O12", "Q16"]


def test_pdf_url_quoted(papers):
    assert papers[0].pdf_url == (
        "https://zenodo.org/records/11111111/files/"
        "doe-rao-credit%20constraints.pdf?download=1"
    )


def test_split_keywords_variants():
    kws, jel = zenodo.split_keywords(["JEL O12; D13", "Q1", "poverty", "jel: e21"])
    assert jel == ["O12", "D13", "Q1", "E21"]
    assert kws == ["poverty"]


def test_doi_url_prefers_concept(papers):
    assert papers[0].doi_url == "https://doi.org/10.5281/zenodo.11111110"


# ---------------------------------------------------------------- ledger

def test_ledger_assigns_stable_numbers(papers):
    led = {"next_number": 1, "papers": []}
    new = ledger_mod.sync(led, papers, today="2026-08-12")
    assert [e["number"] for e in new] == [1, 2]
    # oldest publication date gets the lowest number
    assert led["papers"][0]["conceptrecid"] == "11111110"

    # re-sync: nothing new, numbers unchanged
    assert ledger_mod.sync(led, papers, today="2026-08-13") == []
    assert [e["number"] for e in led["papers"]] == [1, 2]


def test_ledger_marks_withdrawn_and_restores(papers):
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    ledger_mod.sync(led, papers[:1], today="2026-08-13")
    assert led["papers"][1]["withdrawn"] is True
    ledger_mod.sync(led, papers, today="2026-08-14")
    assert "withdrawn" not in led["papers"][1]


def test_ledger_roundtrip(tmp_path, papers):
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    path = tmp_path / "papers.yaml"
    ledger_mod.save(path, led)
    assert ledger_mod.load(path) == led


# ---------------------------------------------------------------- redif

def _fields(template):
    """Parse a template back into {key: unwrapped value}."""
    joined = re.sub(r"\n ", " ", template.strip())
    out = {}
    for line in joined.split("\n"):
        k, _, v = line.partition(": ")
        out.setdefault(k, []).append(v)
    return out


def test_archive_template(cfg):
    f = _fields(redif.archive_template(cfg))
    assert f["Template-Type"] == ["ReDIF-Archive 1.0"]
    assert f["Handle"] == ["RePEc:idd"]
    assert f["URL"] == ["https://papers.idea.devecon.org/RePEc/idd/"]
    assert "Maintainer-Email" in f


def test_series_template(cfg):
    f = _fields(redif.series_template(cfg))
    assert f["Template-Type"] == ["ReDIF-Series 1.0"]
    assert f["Handle"] == ["RePEc:idd:wpaper"]
    assert f["Type"] == ["ReDIF-Paper"]
    assert "Provider-Name" in f and "Maintainer-Email" in f
    assert f["Provider-Institution"] == ["RePEc:edi:ideaaea"]


def test_series_template_omits_absent_institution(cfg):
    """Provider-Institution is optional; a fork without an EDIRC record
    should still emit a valid series template."""
    del cfg["repec"]["provider_institution"]
    f = _fields(redif.series_template(cfg))
    assert "Provider-Institution" not in f
    assert f["Handle"] == ["RePEc:idd:wpaper"]


def test_paper_template_mandatory_fields(cfg, papers):
    entry = {"number": 1, "conceptrecid": "11111110"}
    t = redif.paper_template(papers[0], entry, cfg)
    f = _fields(t)
    assert f["Template-Type"] == ["ReDIF-Paper 1.0"]
    assert f["Author-Name"] == ["Doe, Jane", "Rao, Anand"]
    assert f["Title"] == ["Credit Constraints & Smallholder Technology Adoption"]
    assert f["Handle"] == ["RePEc:idd:wpaper:1"]
    assert f["Classification-JEL"] == ["O12, Q16"]
    assert f["File-Format"] == ["application/pdf"]
    assert f["DOI"] == ["10.5281/zenodo.11111110"]


def test_paper_template_wraps_long_lines(cfg, papers):
    t = redif.paper_template(papers[1], {"number": 2, "conceptrecid": "22222220"}, cfg)
    assert all(len(line) <= 78 for line in t.splitlines())
    # continuation lines are indented, so no line looks like a stray new key
    body = _fields(t)
    assert "robustness" in body["Abstract"][0]


def test_paper_template_jel_override(cfg, papers):
    entry = {"number": 1, "conceptrecid": "11111110", "jel": ["O13"]}
    f = _fields(redif.paper_template(papers[0], entry, cfg))
    assert f["Classification-JEL"] == ["O13"]


def test_withdrawn_paper_has_no_file_cluster(cfg, papers):
    entry = {
        "number": 3,
        "conceptrecid": "999",
        "withdrawn": True,
        "title": "Gone Paper",
        "authors": ["Doe, Jane"],
        "date": "2026-01-01",
    }
    t = redif.paper_template(None, entry, cfg)
    f = _fields(t)
    assert "File-URL" not in f
    assert f["Title"] == ["Gone Paper"]
    assert f["Handle"] == ["RePEc:idd:wpaper:3"]


# ---------------------------------------------------------------- site

def test_index_html(cfg, papers):
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    html_out = site.index_html({p.conceptrecid: p for p in papers}, led, cfg)
    assert "Credit Constraints &amp; Smallholder Technology Adoption" in html_out
    assert "Working Paper No. 2" in html_out
    assert "doi.org/10.5281/zenodo.11111110" in html_out
    # newest first
    assert html_out.index("Remittances") < html_out.index("Credit Constraints")


def test_dir_index():
    out = site.dir_index("RePEc:idd", ["iddarch.redif", "iddseri.redif", "wpaper/"])
    assert '<a href="iddarch.redif">iddarch.redif</a>' in out
    assert '<a href="wpaper/">wpaper/</a>' in out


def test_index_html_empty(cfg):
    html_out = site.index_html({}, {"next_number": 1, "papers": []}, cfg)
    assert "No papers published yet" in html_out


# ------------------------------------------------------------- bibtex

def _led(papers):
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    return led


def test_bibtex_entry_shape(cfg, papers):
    entry = bibtex.entry(papers[1], {"number": 2}, cfg, "okonkwo2026remittances")
    assert entry.startswith("@techreport{okonkwo2026remittances,")
    assert entry.rstrip().endswith("}")
    f = dict(
        re.match(r"\s*(\w+)\s*=\s*(.*?),?$", line).groups()
        for line in entry.splitlines()[1:-1]
    )
    assert f["author"] == "{Okonkwo, Chidi}"
    # Inner braces protect the title's capitalization from the style.
    assert f["title"] == "{{Remittances and Rural Labor Markets}}"
    assert f["year"] == "{2026}"
    assert f["month"] == "aug"  # a macro, so deliberately unbraced
    assert f["type"] == "{Working Paper}"
    assert f["series"] == "{IDEA Working Papers}"
    assert f["number"] == "{2}"
    assert f["doi"] == "{10.5281/zenodo.22222220}"


def test_bibtex_escapes_tex_specials(cfg, papers):
    # The fixture title contains a literal ampersand.
    entry = bibtex.entry(papers[0], {"number": 1}, cfg, "doe2026credit")
    assert r"Credit Constraints \& Smallholder" in entry
    assert "&amp;" not in entry  # HTML escaping must not leak into the .bib


def test_bibtex_escape_backslash_not_doubled():
    assert bibtex.escape("a_b") == r"a\_b"
    assert bibtex.escape("100%") == r"100\%"
    assert bibtex.escape("\\") == r"\textbackslash{}"
    assert bibtex.escape("{x}") == r"\{x\}"


def test_cite_key_form_and_stopwords(papers):
    assert bibtex.cite_key(papers[0]) == "doe2026credit"
    assert bibtex.cite_key(papers[1]) == "okonkwo2026remittances"


def test_cite_key_disambiguates(papers):
    first = bibtex.cite_key(papers[0])
    assert bibtex.cite_key(papers[0], {first}) == first + "b"
    assert bibtex.cite_key(papers[0], {first, first + "b"}) == first + "c"


def test_cite_keys_stable_under_new_papers(cfg, papers):
    """A later paper must not change an earlier paper's key."""
    led = _led(papers)
    keys = site.cite_keys({p.conceptrecid: p for p in papers}, led)
    older = {p.conceptrecid: p for p in papers[:1]}
    led_older = {"next_number": 2, "papers": [e for e in led["papers"] if e["number"] == 1]}
    assert site.cite_keys(older, led_older)["11111110"] == keys["11111110"]


def test_bib_file_holds_every_paper(cfg, papers):
    out = site.bib_file({p.conceptrecid: p for p in papers}, _led(papers), cfg)
    assert out.count("@techreport{") == 2
    assert out.endswith("\n")


def test_index_html_embeds_bibtex(cfg, papers):
    out = site.index_html({p.conceptrecid: p for p in papers}, _led(papers), cfg)
    assert "<summary>BibTeX</summary>" in out
    assert "@techreport{doe2026credit," in out
    # Inside the page the entry is HTML-escaped, so the ampersand the
    # .bib escapes for TeX must survive as an HTML entity too.
    assert r"Credit Constraints \&amp; Smallholder" in out
    assert site.BIB_FILENAME in out
