# Self-hosted webfonts

The three families used by <https://idea.devecon.org/>, so this series
looks like part of the same society rather than a different one:

| Family | Role | File |
|---|---|---|
| Archivo Black | page title | `archivo-black-400-*.woff2` |
| Libre Franklin | body and headings | `libre-franklin-var-*.woff2` |
| Space Mono | identifiers (WP numbers, handles, DOIs, dates) | `space-mono-400-*.woff2` |

They are served from here rather than `fonts.googleapis.com` on purpose:
no third-party request on every page view, and an archive meant to
outlive its editor should not depend on someone else's CDN staying up.

Libre Franklin is a variable font (`wght` 100–900), so a single file per
subset covers every weight and is declared with a weight *range* in the
`@font-face` rule. Archivo Black and Space Mono are static 400.

Each family ships `latin` and `latin-ext` subsets, selected by
`unicode-range` so a browser fetches only what a page actually needs.
`latin-ext` is what makes accented author names render in the intended
face rather than a fallback.

All three are under the SIL Open Font License 1.1. The licences are
**not** interchangeable — each carries its own Reserved Font Name
clause — so each is kept verbatim as `OFL-<Family>.txt`.

## Refreshing

Fonts change rarely and there is no reason to track upstream. If you do
need to re-fetch, get the woff2 URLs from the Google Fonts CSS API with
a modern browser User-Agent (it serves woff2 only to browsers that
support it), and re-copy the licences from
<https://github.com/google/fonts>. Keep the `unicode-range` values in
`ideawp/site.py` in step with whatever the API returns.
