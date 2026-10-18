# Texas official-source evidence

This is a dated research package, not a running collector. Observations were
retrieved on 2026-10-18 UTC (October 17 Central). Every request's precise UTC,
requested/final URL, redirects, status and response headers are retained under
`raw/`. Full entities, including empty/error/test/old responses, are gzip stored.
No entity is silently truncated. Entity hashes cover requests' content/transfer
decoded bytes; text extraction and JSON decoding are separate derivatives.

From the repository root:

```sh
python3 senate/2026/texas/data/results-sources/native_inventory.py
python3 senate/2026/texas/data/results-sources/build.py
python3 senate/2026/texas/data/results-sources/validate.py
python3 senate/2026/texas/data/results-sources/assets.py
python3 senate/2026/texas/data/results-sources/validate.py --verify-assets
```

Offline checks use Python's standard library. Only new network retrievals via
`fetch.py ID EXACT_URL PARENT_ID PURPOSE` need `requests`. The fetcher refuses
to replace an existing ID; use a new ID for a later observation. Its byte-stream
splitting keeps every stored object strictly below 40,000,000 bytes. Identical
entities share one gzip while distinct request metadata is retained. Shared
historical originals are pinned in place, including Harris's two ordered gzip
byte parts. No large historical PDF is downloaded again here.

The root [report](../../official-results.md), [county inventory](../official-results-sources.csv),
[schema](SCHEMA.md), [priority index](priority-index.json),
[HTTP ledger](source-ledger.json), [shared evidence](shared-evidence.json),
[native summary](native-inventory-summary.json), [legal source audit](legal-source-audit.json)
and [validation](validation.json)
are the entry points. `priority/<FIPS>.json` is a separate source/route/field
record for each of the exact ordered 34. The remaining 220 are explicitly
discovery/inventory scope, with accessible state setup objects separately
retained for all 254. Discovery does not establish a functioning county feed.

All current/test/older native identities are available in
`native-unit-identities.csv.gz`; all 170,013 indexed source positions are in
`native-unit-observations.csv.gz`. Read `observation_class`, `unit_kind`,
`source_id`, `election_id`, `contest_id` and source pointer together. Do not join
solely on a native ID. These inventories do not approve a reporting geography.
Historical derivative, original and TLC inventories remain separate read-only
references; `county-native-coverage.csv` makes every county's known gaps visible.

PDF text was extracted using Poppler `pdftotext -layout`. Certification and
selected scanned report pages were rendered with `pdftoppm` and visually
inspected. Blank text from a scan is a text-extraction limitation, not empty
results. `*-preview.png` is a page-scoped derivative, never the original body.
The eCFR web extract is explicitly a rendered tool extract; the direct request
was an access-limited response and is not falsely labeled statute text.
