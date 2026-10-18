# Texas precinct boundary archive

This archive retains actual source geometry and map bytes for all 34 accepted
priority counties. All 254 counties remain in the inventory. The county priority
is based only on the accepted official 2024 Senate county candidate totals.
Geometry does not allocate those votes or establish a reporting crosswalk.

## Entry points and units

- `index.html` works directly from disk, with no CDN, tiles, fonts, fetch calls,
  external scripts, server or network dependency. Its 34 county pages contain
  previews and actual download links; the complete 254-county table is included.
- `inventory/all-counties.csv` follows the exact accepted turnout order. Keys
  are `TX:<five-digit FIPS>`, with the original county spelling retained.
  The explicit case-only display alias `McLennan` → `Mclennan` joins the local
  source label to the accepted county inventory; no filename mapping is used.
- `sources/<id>.json` records exact requested/final URLs, parent, retrieval UTC,
  HTTP status/headers/redirects, original entity hash/bytes and storage parts.
  An HTTP 202 empty challenge, 403 or 404 is retained as failure evidence and is
  never classified as an original map. `.body` is generic response storage,
  not a claim about MIME type. `originals/` holds response entity bytes.
- `manifest.json` inventories all acquisition sources and map asset groups;
  `manifest.csv` provides the county map assets in accepted order. For split
  originals, `bytes`/`sha256` describe the reconstructed original, not a part.
  `asset-hashes.json` lists actual saved files and strictly enforces the cap.
- `county-notes.json` supplies precise county vintage, source and access gaps.
  `discovery/` preserves published links and exact routes, including links that
  were not downloaded. A published link is not an acquired/current map.

## Original storage and reconstruction

Every saved file must be **strictly below 40,000,000 bytes**. Statewide ZIPs
are kept once, in ordered exact 32,000,000-byte parts plus a remainder. Large
PDFs use lossless gzip, split further if required. `stored_parts` is ordered;
each part has its own hash/byte count. Identical original entities reuse one
stored stream, while retaining separate HTTP observations.

Concatenate parts **before** decompression. Only decompress when
`storage_encoding` is `gzip`. Verify the reconstructed entity against
`original_sha256` and `original_bytes`. This also applies to source originals
reused from peer paths: their own manifests, including Harris's ordered gzip
byte parts, govern reconstruction. We do not duplicate those results files.

```sh
python3 senate/2026/texas/maps/reconstruct.py tlc-24g /tmp/Precincts24G.zip
python3 senate/2026/texas/maps/reconstruct.py local-webb-3 /tmp/Webb-order.pdf
```

`counties/<FIPS>-{24g,26p,22g,20g}.zip` is a lossless county subset of the
single original statewide ZIP. Every SHP geometry record body and DBF record
is copied byte for byte. SHP/SHX file lengths, XY county extent and record
numbers/offsets, and DBF record count are rebuilt; field definitions, all
attributes, rings, vertices and PRJ/CPG bytes are retained. The subset audit
lists the original zero-based row indices, each raw geometry-body and DBF-row
hash, full feature/vertex totals, output hash and successful reopen comparison.
The original statewide ZIP remains available for exact reconstruction.

## Geometry, CRS and diagnostic scope

The TLC files are actual county-collected **precinct** shapefiles, separately
labelled 2020 general, 2022 general, 2024 general and 2026 primary. They are not
the separate TLC VTD catalog. County approval/current November status remains
unknown unless a specific original notice says otherwise; a dated notice does
not approve a results-to-polygon crosswalk or all future versions.

TLC native CRS is its supplied custom NAD83 Texas Lambert Conformal Conic WKT,
with easting/northing axes and metre units. Complete WKT is in `crs/` and the
audits. No EPSG identity is guessed. Original shapefile Polygon type 5 has XY
coordinates and no Z/M/true-curve representation. All vertices are preserved.
No GeoJSON conversion is supplied. Raster previews map native projected XY
directly to pixels; they are display derivatives, not georeferenced originals.
Polygon labels are omitted on dense maps; complete IDs remain in downloads.

`geometry/tlc-*-audit.json` covers the whole original source, all 254 counties,
all IDs, attributes, parts and vertices, invalid/self-intersecting records,
duplicate IDs and positive-area intersections. `inventory/native-geometry-units.csv.gz`
has one row per source geometry with literal `PREC`, `PCTKEY`, zero-based row,
county code, vertex/part counts, validity and every original attribute in JSON.

Intersection diagnostics use each source's **native projected squared units**.
TLC areas are square metres in that projection, not square degrees or geodesic,
ground-survey or legal area. County GIS units may be US survey feet or metres;
never add areas across unlike CRS units. All positive areas, including tiny
floating-point slivers, are retained without a tolerance cutoff. Invalid,
empty and curve-only geometries are excluded from intersections and explicitly
counted. They stay unchanged in originals/subsets; no repair is attempted.
Intersection checks are within each county/source, not a certified county
boundary coverage, cross-county topology or cross-vintage overlay.

`gis/*-audit.json` includes original layer/service/item metadata references,
pre/post advertised counts, complete pre/post object-ID sets and every requested
and returned batch ID. Batches are at most 100 and below advertised limits.
Requests use `outFields=*`, no `outSR`, precision, quantization or generalization,
and explicitly request Z, M and true curves. All response pages are original
bytes. All transfer-limit flags are checked. An inaccessible ArcGIS item is
retained as a metadata gap and does not erase an accessible county service.
`geometry/gis-*.json` records actual point dimensions, true-curve returns,
validity, vertex coverage, native axes/units and bounds transformed to geographic
coordinates using pyproj `always_xy=True` for a Texas-bounds diagnostic only.
Johnson advertises/returns Z; source XYZ is retained, while display uses XY.
The other eight services returned XY; no true curves were returned. Advertised
support is distinguished from observed geometry. `metadata-dates.json` separates
item/file/edit clocks from legal adoption; `authority-chains.json` distinguishes
captured county-app-service links from direct county-GIS-domain discovery.

Two additional original shapefile ZIPs have independent audits and full native
attribute inventories: historical Harris adopted precincts and the City of
Galveston's VTD-named reference. They do not replace the TLC county vintages.

## Reporting inventory and compatibility

`inventory/reporting-unit-compatibility.csv.gz` accounts for 48,679 observed
source-scoped identities: 31,702 OE historical, 4,276 original historical vendor
and 12,701 official-results discovery identities. `input_row_json` preserves
the exact peer row, source/file/county identity, source pointers and occurrence
counts. The independent first-wave identity sets are checked, not counted twice.

The status vocabulary is `matched`, `ambiguous`, `administrative/no-polygon`,
`absent geometry`, `source conflict`, `unknown`. This archive approves **zero**
`matched` rows and makes no positive `absent geometry` assertion from a failed
string join. Exact literal same-year county ID overlap is `ambiguous`; no
padding, suffix stripping, vote allocation or count-based matching is used.
An explicit early/mail/total or vote-center label is administrative/no-polygon.
Test/older observation classes and published county/file conflicts are retained
as source conflicts; missing/unverified county components remain unknown.
Polygon completeness does not imply reporting-inventory completeness.

All historical candidate rows/repeats remain in referenced peer originals:
OE 2024 has 184 files but 182 actual county labels; the `hardin` and `jeff_davis`
filenames contain Hunt and Grayson rows. Four files have duplicate candidate
keys, 22 have nonadditive method fields; 2022 contains 101 counties and 2020
248. These defects are preserved in the linked native-source diagnostics,
without reassignment or deduplication. Candidate vintages/universes in original
Harris, Dallas and Travis reports remain separate.

`inventory/accepted-constituents.csv.gz` preserves all 45,944 constituent records
from the accepted 254-group priority contract, including county summaries,
original units and separately labelled derived VTDs. Component ordinal/type,
original JSON, county key/rank and priority flag remain intact. Its county total
and derived VTD entries are never assigned to precinct polygons.

The read-only peer `native-unit-observations.csv.gz` retains all 170,013 current,
test and older observation positions, repeats, contest IDs and raw JSON.
`read-only-references.json` pins exact path/hash/bytes for these and all other
used peer artifacts. Native result IDs, central groups and vote-center locations
are distinct; SOS MID is not FIPS and is never numerically joined here.

## PDFs and visual review

37 actual PDF originals have 311 pages. Every original hash/byte count and page
count is checked, with independent Poppler/PyMuPDF page-count agreement. Complete
source text is stored losslessly; per-page text/image/bounds diagnostics and
literal date/legal lines are in `pdf/inspection.json`. All mapbook pages stay in
their originals. 62 selected first/middle/last page previews and six contact
sheets support visual inspection; selected previews are not full page coverage.
Scanned Collin, signed Guadalupe attachments and other actual map previews were
visually reviewed. Viewer HTML/screenshots are not presented as original PDFs.
PDFs may contain district or VTD cartography; titles and scope remain qualified.

## Reproduce and validate

Use Python 3.11 or newer. Install research dependencies outside this repository;
no dependency/cache folders belong in the retained assets:

```sh
uv venv /tmp/tx-maps-venv
uv pip install --python /tmp/tx-maps-venv/bin/python requests==2.34.2 beautifulsoup4==4.15.0 shapely==2.2.0 pyproj==3.7.2 pyshp==3.1.6 pillow==13.0.0
```

Original network acquisition: `acquire.py tlc`, `county_routes.py`,
`acquire_local.py`, `extra_sources.py` and `acquire_gis.py`. Existing observations
are reused. Every additional exact item/viewer URL is in its source metadata;
the generic replay command reproduces any retained URL in a new directory:

```sh
/tmp/tx-maps-venv/bin/python senate/2026/texas/maps/replay_acquisition.py --source-id smith-100-original --output-dir /tmp/tx-map-smith-new
```

The archive remains immutable during replay; changed network responses are
reported as differing hashes. This is an acquisition aid, not a live collector.

Offline build, inspection and validation, from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/build_geometry.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/build_local_geometry.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/build_compatibility.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/metadata_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/texas/maps/render_pdfs.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/build_index.py
PYTHONDONTWRITEBYTECODE=1 /tmp/tx-maps-venv/bin/python senate/2026/texas/maps/validate.py
```

The PDF script requires host `fitz`/Pillow plus Poppler `pdfinfo`; retained
previews permit offline inspection without rebuilding. Builds do not contact
the network. `validation.json` reports coverage/hashes/IDs/geometry/links/bounds;
`asset-hashes.json` excludes only itself to avoid self-reference. No Git actions,
collector, calibration, approved crosswalk or current legal boundary certification
are part of this package.
