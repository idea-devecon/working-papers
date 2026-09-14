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


def test_sync_never_withdraws_a_paper_on_its_own(papers):
    """Absence from a fetch is an alarm, not an instruction to withdraw.

    A degraded API, a truncated page and a renamed community all look
    like absence, and a withdrawal notice published to RePEc is not
    something a nightly job should be able to do unattended.
    """
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    ledger_mod.sync(led, papers[:1], today="2026-08-13")
    assert all("withdrawn" not in e for e in led["papers"])
    # It is reported instead, for the caller to refuse on.
    missing = ledger_mod.missing_from(led, papers[:1])
    assert [e["number"] for e in missing] == [2]


def test_sync_never_clears_an_editors_withdrawal(papers):
    """The flag is the editor's; a paper still in the community keeps it."""
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, papers, today="2026-08-12")
    led["papers"][1]["withdrawn"] = True
    ledger_mod.sync(led, papers, today="2026-08-13")
    assert led["papers"][1]["withdrawn"] is True
    # ...and a withdrawn paper absent from the fetch is not an alarm.
    assert ledger_mod.missing_from(led, papers[:1]) == []


def test_withdrawn_flag_beats_a_live_record(cfg, papers):
    """A manual withdrawal must drop the File cluster even if Zenodo still
    serves the record -- otherwise the editor's decision never reaches RePEc."""
    entry = {"number": 1, "conceptrecid": papers[0].conceptrecid,
             "title": papers[0].title, "authors": ["Doe, Jane"],
             "date": papers[0].pub_date, "withdrawn": True}
    out = redif.paper_template(papers[0], entry, cfg)
    assert "This paper has been withdrawn." in out
    assert "File-URL" not in out and "Abstract" not in out


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



# ------------------------------------------------------------- fetching


# ------------------------------------------------- fetching (proposed)

import http.server
import socket
import socketserver
import threading

import requests
from requests.adapters import BaseAdapter


class _Server:
    """A local HTTP server that records every request it receives."""

    def __init__(self, responder):
        self.hits = []
        hits, reply = self.hits, responder

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                hits.append(self.path)
                status, body = reply(len(hits), self.path)
                payload = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *a):
                pass

        self._srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self._srv.daemon_threads = True
        self.url = "http://127.0.0.1:%d" % self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def close(self):
        self._srv.shutdown()
        self._srv.server_close()


@pytest.fixture
def server():
    made = []

    def make(responder):
        s = _Server(responder)
        made.append(s)
        return s

    yield make
    for s in made:
        s.close()


@pytest.fixture
def dead_port():
    """A port nothing is listening on: a stand-in for Zenodo being down."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _ScriptedAdapter(BaseAdapter):
    """Serves canned responses; records the exact URL and timeout used."""

    def __init__(self, pages):
        super().__init__()
        self.pages = list(pages)
        self.urls = []
        self.timeouts = []
        self.headers = []
        self.closed = False

    def send(self, request, timeout=None, **kw):
        self.urls.append(request.url)
        self.timeouts.append(timeout)
        self.headers.append(dict(request.headers))
        status, payload = self.pages.pop(0)
        r = requests.Response()
        r.status_code = status
        r.url = request.url
        r.request = request
        r.headers["Content-Type"] = "application/json"
        r._content = json.dumps(payload).encode()
        return r

    def close(self):
        self.closed = True


def _scripted(pages):
    session = requests.Session()
    adapter = _ScriptedAdapter(pages)
    session.mount("https://", adapter)
    return session, adapter


def _page(hits, next_url=None, total=None):
    """A Zenodo-shaped page.  `total` defaults to honest self-consistency."""
    return {
        "hits": {"hits": hits, "total": len(hits) if total is None else total},
        "links": {"next": next_url} if next_url else {},
    }


@pytest.fixture
def impatient(monkeypatch):
    """The real retry policy with only the sleeps removed.

    What decides *whether* to retry -- MAX_ATTEMPTS, RETRY_STATUSES --
    is untouched, so these tests still fail if the policy is weakened;
    zeroing the backoff just spends the budget in milliseconds.
    """
    monkeypatch.setattr(zenodo, "BACKOFF_BASE", 0.0)
    monkeypatch.setattr(zenodo, "RETRY_AFTER_CAP", 0.0)


RAW_HITS = json.loads(FIXTURE.read_text())["hits"]["hits"]


def _cfg_at(cfg, url, tmp_path):
    return dict(
        cfg,
        zenodo=dict(cfg["zenodo"], api_base=url + "/api"),
        site=dict(cfg["site"], output_dir=str(tmp_path / "site")),
    )


def _seeded_ledger(tmp_path):
    """A ledger already holding both fixture papers, as a live series."""
    led = {"next_number": 1, "papers": []}
    ledger_mod.sync(led, [zenodo.parse_record(h) for h in RAW_HITS], today="2026-01-01")
    path = tmp_path / "papers.yaml"
    ledger_mod.save(path, led)
    return path


# --- the retry policy, exercised rather than described ---------------

# --- the retry policy, exercised rather than described ---------------

def test_a_flapping_get_is_retried_and_then_succeeds(server, impatient):
    """Two 502s then a 200: the blip that started all this."""
    srv = server(lambda n, path: (502, "") if n < 3 else (200, json.dumps(_page(RAW_HITS))))
    got = zenodo.fetch_community_records(srv.url + "/api", "c")
    assert len(got) == 2
    assert len(srv.hits) == 3


def test_a_body_that_fails_after_the_headers_is_retried(server, impatient):
    """The header phase is not the whole request.

    Zenodo serves this endpoint chunked and gzipped, so a failure while
    the body streams -- or a truncated payload that will not parse -- is
    an ordinary outcome.  A retry that lives in an HTTP adapter covers
    only the headers and would give this a single attempt.
    """
    srv = server(
        lambda n, path: (200, "{not json" if n == 1 else json.dumps(_page(RAW_HITS)))
    )
    got = zenodo.fetch_community_records(srv.url + "/api", "c")
    assert len(got) == 2
    assert len(srv.hits) == 2


def test_a_persistent_outage_spends_the_budget_then_raises(server, impatient):
    srv = server(lambda n, path: (503, ""))
    with pytest.raises(zenodo.ZenodoUnreachable) as ei:
        zenodo.fetch_community_records(srv.url + "/api", "c")
    assert len(srv.hits) == zenodo.MAX_ATTEMPTS
    assert ei.value.attempts == len(srv.hits)  # the count we report is observed


def test_a_bad_request_is_not_retried(server, impatient):
    """404 means the community moved; hammering it would only repeat."""
    srv = server(lambda n, path: (404, ""))
    with pytest.raises(requests.exceptions.HTTPError):
        zenodo.fetch_community_records(srv.url + "/api", "c")
    assert len(srv.hits) == 1


def test_rate_limiting_is_treated_as_zenodo_being_busy(server, impatient):
    """429 is the one 4xx that means wait, not that we asked wrongly."""
    srv = server(lambda n, path: (429, ""))
    with pytest.raises(zenodo.ZenodoUnreachable):
        zenodo.fetch_community_records(srv.url + "/api", "c")
    assert len(srv.hits) == zenodo.MAX_ATTEMPTS


def test_every_request_is_bounded_and_identifies_itself(server):
    seen = {}

    class Recorder(requests.Session):
        def get(self, url, **kw):
            seen.update(timeout=kw.get("timeout"), ua=self.headers.get("User-Agent"))
            return super().get(url, **kw)

    srv = server(lambda n, path: (200, json.dumps(_page(RAW_HITS))))
    sess = Recorder()
    sess.headers["User-Agent"] = zenodo.USER_AGENT
    zenodo.fetch_community_records(srv.url + "/api", "c", session=sess)
    assert seen["timeout"] is not None
    assert "ideawp" in seen["ua"]


def test_every_page_is_collected(server, impatient):
    pages = []
    srv = server(lambda n, path: (200, pages[min(n, len(pages)) - 1]))
    srv_url = srv.url
    nxt = srv_url + "/api/next-page"
    pages.append(json.dumps(_page(RAW_HITS[:1], next_url=nxt, total=2)))
    pages.append(json.dumps(_page(RAW_HITS[1:], total=2)))
    got = zenodo.fetch_community_records(srv_url + "/api", "c")
    assert [p.recid for p in got] == [int(h["id"]) for h in RAW_HITS]
    assert srv.hits[1] == "/api/next-page"  # the next link, used verbatim


def test_pagination_that_loops_is_refused(server, impatient):
    """A self-referential links.next must not spin until the job is killed."""
    srv = server(
        lambda n, path: (200, json.dumps(_page(RAW_HITS[:1], next_url=srv.url + "/api/p", total=2)))
    )
    with pytest.raises(zenodo.FetchIncomplete):
        zenodo.fetch_community_records(srv.url + "/api", "c")


# --- a short fetch must never read as a withdrawal -------------------

def test_an_empty_community_that_should_not_be_empty_is_refused(server, impatient):
    """The catastrophic path: 200 OK, zero hits, total says otherwise."""
    srv = server(lambda n, path: (200, json.dumps(_page([], total=4))))
    with pytest.raises(zenodo.FetchIncomplete):
        zenodo.fetch_community_records(srv.url + "/api", "c")


def test_a_truncated_page_is_refused(server, impatient):
    """Because the query sorts oldest-first, truncation drops the newest."""
    srv = server(lambda n, path: (200, json.dumps(_page(RAW_HITS[:1], total=2))))
    with pytest.raises(zenodo.FetchIncomplete):
        zenodo.fetch_community_records(srv.url + "/api", "c")


def test_a_silently_empty_fetch_never_withdraws_the_series(
    cfg, tmp_path, server, impatient
):
    """End to end: exit non-zero, nothing published, ledger untouched.

    A self-consistent empty answer (total 0) passes the fetch check, so
    the ledger is the last line of defence.
    """
    from ideawp import build as build_mod

    ledger_path = _seeded_ledger(tmp_path)
    before = ledger_path.read_text()
    srv = server(lambda n, path: (200, json.dumps(_page([], total=0))))
    with pytest.raises(build_mod.IncompleteData, match="absent from the Zenodo fetch"):
        build_mod.build(_cfg_at(cfg, srv.url, tmp_path), ledger_path)
    assert ledger_path.read_text() == before
    assert not (tmp_path / "site").exists()


def test_the_wrong_community_never_burns_paper_numbers(
    cfg, tmp_path, server, impatient
):
    """A rename or merge can return a perfectly well-formed wrong answer.

    Allocating numbers to those records is the one failure here that no
    later run can undo: numbers are never reused, so the handles would
    be served as phantom papers forever.
    """
    from ideawp import build as build_mod

    ledger_path = _seeded_ledger(tmp_path)
    before = ledger_path.read_text()
    foreign = json.loads(json.dumps(RAW_HITS))  # deep copy
    for i, h in enumerate(foreign):
        h["id"] = 99000000 + i
        h["conceptrecid"] = str(99000010 + i)
    srv = server(lambda n, path: (200, json.dumps(_page(foreign))))
    with pytest.raises(build_mod.IncompleteData):
        build_mod.build(_cfg_at(cfg, srv.url, tmp_path), ledger_path)
    assert ledger_path.read_text() == before  # next_number did not advance


def test_an_empty_series_may_legitimately_be_empty(cfg, tmp_path, server, impatient):
    """Day zero must still build: no ledger, no papers, no alarm."""
    from ideawp import build as build_mod

    srv = server(lambda n, path: (200, json.dumps(_page([], total=0))))
    summary = build_mod.build(_cfg_at(cfg, srv.url, tmp_path), tmp_path / "papers.yaml")
    assert summary["papers"] == 0
    assert (tmp_path / "site" / "index.html").exists()


def test_a_refused_connection_is_reported_as_an_outage(
    cfg, tmp_path, dead_port, impatient
):
    """The exception a dead Zenodo really raises -- not the one we imagine."""
    from ideawp import build as build_mod

    with pytest.raises(build_mod.ZenodoUnavailable):
        build_mod.build(
            _cfg_at(cfg, "http://127.0.0.1:%d" % dead_port, tmp_path),
            tmp_path / "papers.yaml",
        )


def test_main_exits_nonzero_and_annotates_a_refusal(
    cfg, tmp_path, server, impatient, capsys, monkeypatch
):
    """CI must go red, with one readable line instead of a traceback."""
    from ideawp import build as build_mod

    ledger_path = _seeded_ledger(tmp_path)
    srv = server(lambda n, path: (200, json.dumps(_page([], total=0))))
    conf = tmp_path / "config.yaml"
    conf.write_text(yaml.safe_dump(_cfg_at(cfg, srv.url, tmp_path)))
    rc = build_mod.main(["--config", str(conf), "--ledger", str(ledger_path)])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("::error title=Zenodo data incomplete::")
    assert "Traceback" not in err
