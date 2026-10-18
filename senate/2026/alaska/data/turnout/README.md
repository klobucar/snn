# Alaska turnout evidence and schemas

Research observations: 2026-10-18 UTC / 2026-10-17 America/Chicago. This directory belongs to the turnout assignment. No cross-year district or precinct join is performed.

- `../county-turnout.csv`: 41 ranked 2024 groups, HD1-40 plus separate HD99. Compatibility filename only; these are not Alaska borough/census-area counties. All-candidate presidential votes define the primary ranking. Separate ballot ranking fields are included.
- `district-turnout-2022.csv`: all 41 native 2022 groups and Senate first choices including Write-in. Separate election vintage; not joined to 2024 numbers.
- `reporting-units-2024.csv`, `reporting-units-2022.csv`: all 523 / 522 nonoverlapping constituent records, each independently ranked. Source keys, exact labels, native IDs where supplied, election/contest/vintage, candidate counts, ballots and registration are retained. Unit-level priority flags refer to the unit-level ranking; `district_in_priority_set` identifies district research membership.
- `priority-set.json`: exact ordered 28-district 2024 dispatch list, totals, source summaries, observed map-source links and constituent source keys. `24GENR:HD06` is a project composite key for native HD `6`; it is not a county FIPS or a timeless district identity.
- `candidate-reconciliation.csv`: 13 statewide candidate comparisons to official PDFs.
- `district-reconciliation.csv`: 697 candidate/ballot/registration comparisons to all 82 district PDFs; every difference is zero.
- `method-reconciliation.csv`: actual statewide methods alongside source-label-category counts. Four 2024 units named Early Voting include some Election Day counts. No such statewide label/category difference appears in 2022.
- `method-candidate-reconciliation-2022.csv`: 25 statewide candidate/method cells, deduplicated from repeated display rows in the official formatted text export.
- `senate-rcv2022-parsed.json`: independent parsed official rounds and the retained 250-ballot RCV-versus-full-first-choice population difference. Rounds are separate allocations, never added.
- `checks.json`, `ranking-table.md`, `ranking-table-2022.md`: reproducible checks and readable full district rankings.
- `peer-hd-cross-check.csv` / `.json`: 82 same-election district-volume comparisons to the independent partisanship CSV, all zero differences, with observed peer-file hashes. `cross_check_peer.py` also checks the full-ballot counts in the companion six-unit CVR coverage audit against our official PDF extraction; it does not independently replay the CVR or become a dependency of the turnout rebuild.

Raw response names are logical source names. Original CSV/UTF-16 text/HTML bytes are retained in lossless gzip archives (`precinct2024.csv.gz`, `precinct2022.txt.gz`, etc.); PDF responses remain original `.pdf` bytes. `evidence-manifest.json` and the corresponding `.retrieval.json` identify the exact official URL, UTC retrieval times, curl default TLS verification result, HTTP metadata, SHA-256 of the decompressed original bytes, and SHA-256 of any stored gzip archive. `.headers` files contain the actual response headers including redirects. The failed 2024 combined ballot-count request has failure metadata/headers rather than a fabricated downloaded body.

Each 2024 `native_pct_seq_nbr` identifies one source unit; 80 `native_pct_id` cells really are blank. These blanks are not filled from a guess. A derived key `24GENR:4:seq:449`, for example, identifies the exact `District 6 - Early Voting` source row group. The 2022 export supplies labels rather than an ID matrix; `22GENR:Senator:record:<N>` records the original CSV-reader TSV record ordinal, while literal precinct IDs are extracted only when present in the source label. An original label remains available even when whitespace is normalized solely for PDF matching. Regional IDs are not inferred from administrative suffixes.

In 2024, `method` is the source-label category, while `election_day_*`, `early_voting_*` and other explicit method columns are the actual source method matrix. In district files, `*_label_category_*` denotes administrative labels. The 2022 actual-method district fields and per-unit under/overvote fields are unavailable and blank; statewide actual methods are independently published. Registration `0` on administrative rows is a literal structural source value, not a population estimate. All `county_fips` cells are blank, with meaningful `state_fips=02`. Preserve identifiers as text if opening a CSV in spreadsheet software.

Rebuild offline with Python stdlib and Poppler:

```sh
python3 senate/2026/alaska/data/turnout/build_turnout.py
```

The script reads gzip directly, extracts full district/statewide PDF text using `pdftotext -layout`, validates all coverage/identities and source/header hashes, and regenerates all derivative CSV/JSON/tables plus the marked ranking table in `../../turnout.md`. It does not make network calls. Original `.extracted.txt` files and rendered PNGs are evidence-reading aids rather than substitute primary sources.

Download one source with default curl TLS verification:

```sh
python3 senate/2026/alaska/data/turnout/fetch_evidence.py NAME URL
```

`--refresh` reads all successful source URLs from the current manifest and fetches them again, replacing observations and timestamps. Preserve the reviewed snapshot first. No Git operations are part of these scripts. Candidate IDs/parties and detailed method columns not duplicated in the compact derivatives remain in the original source archives at the exact retained record keys.
