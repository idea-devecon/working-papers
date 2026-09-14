# Prior-art ledger: Zenodo fetch integrity

Search tier: git and ripgrep; no GitNexus tools available.

## 1. Task
Enforce the whole-fetch deadline and document manual withdrawal in PR #1.

## 2. Existing machinery
- `ideawp/zenodo.py:_get_json`: retries request/body/JSON failures; covered by
  `test_a_flapping_get_is_retried_and_then_succeeds` and the malformed-body test.
- `ideawp/zenodo.py:fetch_community_records`: collects pages and checks totals;
  covered by `test_every_page_is_collected` and truncation tests.
- `ideawp/ledger.py:missing_from`: missing live entries stop builds;
  covered by `test_sync_never_withdraws_a_paper_on_its_own`.
- `ideawp/build.py:build`: fetch and integrity checks precede ledger/site writes;
  covered by `test_a_silently_empty_fetch_never_withdraws_the_series`.

## 3. Definitions
- `zenodo.py:FETCH_DEADLINE` is seconds for the whole fetch, all pages included.
- `zenodo.py:TIMEOUT` is the connect/read timeout for one attempt.
- `ledger.py:sync`: "The withdrawn flag is never touched here; it belongs to
  the editor."

## 4. Invariants
Never publish partial data or modify the ledger on a fetch refusal. Keep
number assignments and manual withdrawal flags. Close owned sessions; do not
close caller-owned sessions. Retry transient failures, not ordinary 4xx.

## 5. Reuse decisions
Extend the existing retry and pagination functions. Add a bounded wait around
network reads because socket inactivity timeouts cannot enforce elapsed time.
A daemon reader may unwind after the caller refuses, but must not request
another page or write state. Read cooperatively and close responses on exit.
Reuse the local HTTP server tests for successful, delayed and incomplete data.
Update the existing editor runbook rather than add a second procedure.

## 6. Open questions
None. Manual withdrawal was accepted on 2026-09-14 (IDEA handoff).
