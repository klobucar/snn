# Maine official-results evidence

Owned outputs: this directory, `../official-results-sources.csv`, and `../../official-results.md`. Other Maine evidence is consumed read-only. No Git, shared records or other assignments are part of these scripts.

`native-unit-inventory.json` and the compatibility CSV preserve all 512 native 2024 Senate units. `priority-field-audit.json`, `priority-inspections.json`, and `priority-review.md` retain the exact 164 ordered priorities, parent routes, download attempts and gaps. The CSV has one additional explicitly overlapping statewide-source record. The 348 remaining units have current SOS clerk/state inventory and discovery-level municipal website tests; they are not misrepresented as deeply tested November channels.

`current-clerk-roster.json` retains all 560 source labels, using positional extraction of repeated clerk/registrar column headings. `current-authority-inventory.json` adds HTML roster presence, historical associations and identical contact groups without declaring legal consolidation. `current-voting-places.json` retains every one of the 539 current November workbook rows and original W/P/name/county labels. `authority-edges.json` and `native-unit-inventory.json` preserve one-to-many current associations; none allocate historical combined votes or establish polygon equivalence. STATE UOCAVA is state-administered; T22 MD Twp's current host remains unresolved.

The historical key definition and exact ranking belong to the read-only turnout contract. GeoCodes, W/P labels, Excel row addresses, CVR IDs, ballot-style codes and newsroom IDs are different source identities. County aggregates and municipal/ward/method/round views overlap.

Current membership matching uses complete names in the printed municipality and separately delimited parenthetical components. Integration review replaced broad word matching so Portland does not acquire New Portland/South Portland, and added regression checks for analogous names and explicit Argyle shared-host associations. These remain source relationships and candidates, not certified authority or boundary equivalence.

## Retention and source identity

- `objects/<SHA256>.gz` contains losslessly compressed **original HTTP entity bytes**, content-addressed to avoid duplicates. Original hashes refer to decompressed entities; saved hashes refer to gzip bytes. This includes failed responses. No credentials or private endpoint were used. Public pages may themselves contain CMS initialization tokens; no token-backed request was made.
- `requests/<id>.json` records publisher URL, exact request URL, final URL, UTC retrieval, status, response headers, redirects, completeness/bounds, entity/saved hashes and sizes. `www` publisher versus tested `www3` official request host is explicit. Curl repairs retain the full original header chain and verified TLS transport metadata, alongside prior Python TLS failures. The 65,536-byte absentee206 entity is complete as a range response and incomplete as a statewide dataset; its Content-Range gives the full resource length.
- `requests/*.links.json`/`*.txt[.gz]` are derived HTML catalogs/text. HTML `<base>` is honored. Menus are fetched only from exact public URLs present in actual scripts; navigation is not a vote API. Some discovery tests reach unrelated tax/ordinance/news assets; those retained originals are not result observations and do not support vote counts.
- `extracted/*` contains OOXML source-cell/row extracts, PDF text and selected rendered page previews. `ocr/*` contains bounded **first-page-only** Tesseract results, hashes and selected previews; no claim of whole-document OCR follows. Images and scanned hand counts require visual/source-aware review before ingestion. PDF labels and detected words are evidence, not machine completion flags.
- `web-repair-*`, `blocked-browser-*`, `web-time-check.txt` are web-tool observations, not original HTTP bodies. `web-only-observations.json` identifies the three raw-blocked priority sources additionally readable through that tool. No available browser-control surface supported a live Portland UI inspection. Do not equate a parsed web observation with raw-download success.
- Completed statewide/Union/legislative originals are referenced in `../turnout`/`../baselines` and never copied or refreshed here. `baseline-pin.json` hashes the actual read-only inputs used. The Alfred archived/current evidence and coordinator checks remain unchanged.

`candidates-2026.json` pins the printed/declared write-in/withdrawal roster and its exclusions gap. `local-controls.json` records 14 bounded municipal 2024 candidate checks and unresolved Gorham/Falmouth differences. `rcv-audit.json` preserves the actual June2026 CD2 initial/round/UOCAVA formats, including repeated source rows and mismatches; it is not November Senate data. `inspection-summary.json` counts tested successes separately from failures, shells and unsupported fields. Current vote IDs/flags, outstanding counts and observed vote-arrival cadence remain null.

## Offline validation and rebuilding

Run from the checkout root, without network or third-party packages:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/results-sources/validate.py
```

The validator checks source/asset hashes and sizes, complete native/current-roster coverage, exact164 plus348 remainder, key hash and crossing arithmetic, candidate and historical controls, all425 initial RCV row identities,345 CVR rows/known duplicates, selected actual round controls, link-parent provenance, range bounds, null unsupported fields and report links. Known source discrepancies are asserted as retained findings, not silently repaired to make validation green.

Existing cached derivatives can be rebuilt offline with `control_audits.py`, `directory_audit.py`, and `build_inventory.py`. `local_controls.py` additionally renders selected pages with Poppler. `derive.py` uses Poppler for PDF text and the read-only standard-library turnout OOXML reader; `ocr_samples.py` additionally uses Poppler/Tesseract. `compact_text.py` losslessly compresses large derived text. `hash_assets.py` regenerates the final owned-asset manifest; `validate.py` then writes `validation.json`. Do not run any other assignment's builders.

Network acquisition is deliberately separate. `research.py URL ...` is a bounded public-only fetch (25s timeout,39,000,000-byte entity cap, no cookie jar/credentials). Prior canonical metadata and new observations are retained on refresh; unchanged bytes keep their canonical retrieval record stable. `curl_repair.py` uses macOS verified TLS, never `--insecure`. State/discovery/crawl scripts retain their exact selected links and all failed attempts. They are acquisition/research procedures, not unattended election-night collectors. Historical originals must not be refreshed merely to obtain newer fetch timestamps.

None of this evidence establishes a calibrated win probability, November result-feed completeness, a guaranteed cadence or an exact eligible uncounted-ballot count.
