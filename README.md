# IDEA Working Papers

Infrastructure for the working paper series of the [International
Development Economics Association](https://idea.devecon.org/) (IDEA).

Live site: <https://papers.idea.devecon.org/> ·
Archive: [Zenodo community `ideassoc`](https://zenodo.org/communities/ideassoc/) ·
RePEc handle: `RePEc:ida:wpaper`

## How it works

```
Zenodo community (curated; stores PDFs, mints DOIs)
    │  public REST API, nightly + on demand
    ▼
this repo: GitHub Actions runs `python -m ideawp.build`
    │  assigns WP numbers (papers.yaml ledger, committed)
    │  emits ReDIF metadata + index.html
    ▼
GitHub Pages  →  papers.idea.devecon.org
    │  /            human-readable index of the series
    │  /RePEc/ida/  machine-readable ReDIF tree
    ▼
RePEc crawls daily  →  IDEAS / EconPapers / NEP alerts
```

Design choices worth knowing:

- **`papers.yaml` is the only state.** Working-paper numbers are
  assigned once, keyed to Zenodo's version-stable concept record, and
  never reused — revised papers keep their number and RePEc handle.
  The generated site is disposable.
- **Failures are loud.** A Zenodo API error aborts the build rather
  than emitting a tree in which every paper looks withdrawn.
- **Succession is cheap.** Editors need the Zenodo curator role and
  repo access; see [docs/editor-guide.md](docs/editor-guide.md).
  Everything series-specific sits in `config.yaml`.

## Contents

| Path | What |
|---|---|
| `config.yaml` | All series-specific settings (names, handles, URLs) |
| `papers.yaml` | The ledger: WP number ↔ Zenodo record (committed state) |
| `ideawp/` | The pipeline: fetch → ledger → ReDIF + HTML |
| `scripts/deposit.py` | Editor helper: PDF + YAML → Zenodo draft |
| `docs/editor-guide.md` | Runbook for the series editor |
| `docs/repec-registration.md` | One-time RePEc setup instructions |
| `.github/workflows/build-deploy.yml` | Nightly build + Pages deploy |

## Development

```sh
pip install -r requirements.txt
python -m pytest tests/    # unit tests, offline (fixtures)
python -m ideawp.build     # real build against the live community
```

The build writes `site/` (gitignored) and updates `papers.yaml` if new
papers have appeared.
