# Reproduce this snapshot

Run from the repository root. No Git operation is needed or performed. All generated files remain within this package and `../precinct-maps.md`.

## Offline verification

`python3 -B senate/2026/ohio/maps/audit_maps.py`

This uses only Python's standard library, performs no network request, checks read-only baseline hashes, every native reporting identity, count/ID pagination, native shapefile binary records/rings/vertices, all original HTTP hashes and ZIP CRCs, derivative counts/vertices/coordinates, recorded source defects, PDF completeness/preview manifests, all 32 index sections/links and the 40 MB individual-file ceiling. It writes `validation.json`, `artifact-manifest.json` and `zip-member-manifest.json`. Source geometry defects and access gaps remain explicit; passing does not certify boundaries. PDF page counts and rendered page inspections were produced by MuPDF; rerender to independently repeat that parser/render step.

## Rebuild derived files without changing originals

Use a disposable environment outside the repository with the exact recorded versions in `build-environment.json`: Python3.11, shapely2.2.0 / GEOS3.14.1, pyproj3.7.2 / PROJ9.5.1, pyshp2.3.1. The PDF render step additionally uses PyMuPDF and Pillow (versions recorded in `render-environment.json`). Set `PROJ_NETWORK=OFF` and use `python -B`. Do not retain the environment or bytecode caches in this package.

1. `python -B senate/2026/ohio/maps/build_maps.py` regenerates full-vertex GeoJSON, display SVGs, source geometry/ID diagnostics and Census all 88 inventory from retained originals. Native curves remain in EsriJSON; server-linearized polygon derivatives are separately identified. No geometry repair/simplification.
2. `python -B senate/2026/ohio/maps/render_documents.py` parses complete originals and renders every PDF page to contact sheets plus larger first-page previews. For an independent full rerender, remove generated `derived/pdf/` and the generated PDF manifest first; the retained source PDFs remain untouched.
3. `python -B senate/2026/ohio/maps/build_inventory.py` compares exact native historical identifiers/labels and preserves all 17,811 records without vote allocation.
4. `python -B senate/2026/ohio/maps/build_delivery.py` regenerates source ledger, gaps, county inventory, static index and the assigned narrative report. `county_notes.py` contains curated source-chain and vintage observations.
5. Remove any `__pycache__`/temporary dependencies, then run the standard-library audit above.

The raw snapshot consists of `evidence/**` and its adjacent `.meta.json` files. A `.bin` retains exact response bytes; identify format by metadata/magic, and use index suggested download extensions. `.gz` is explicit lossless compression of the HTTP decoded entity body, not a server-side boundary conversion. Headers retain the actual original HTTP observations, including errors; browser directory observations have no fabricated HTTP status. Source and stored hashes differ for gzip by design. Derived maps and raster previews are separately labeled.

## Public acquisition/replay

The acquisition/discovery scripts (`fetch_maps.py`, `discover*.py`, `probe_sources.py`, `primary_routes.py`, `alternate_routes.py`, `inspect_apps.py`, `continue_sources.py`, `final_discover.py`, `resolve_remaining.py`, `source_finish.py`, `historical_alternatives.py`, `new_hosts.py`, `last_alternatives.py`, `acquire*.py`, `prepare_curves.py`, `fetch_documents.py`, `complete_documents.py`, `retain_tuscarawas.py`) contain exact public landing, app, catalog, map service and historical snapshot URLs. Existing metadata is cached deliberately so rerunning does not replace this dated evidence. `import_review.py` imports the coordinator-verified original Tuscarawas server render and exact provenance from the separate read-only review directory. The copied metadata and render-request parameters also make that public export independently reproducible.

For a fresh acquisition, use a new output snapshot directory rather than overwrite this one. `refetch_snapshot.py --output <new-directory>` replays every retained HTTP request using the standard library and emits fresh UTC/status/headers/body hashes, including failures. Public service data and errors can change; a fresh body need not have this snapshot's hash. Do not substitute fresh records into this snapshot or treat retrieval time as legal approval. Original exact response bodies, native CRS/Z/M/curve content and all attributes remain the archival source of record.
