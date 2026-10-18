# Alaska map package reproduction

All files in this directory belong to the map assignment. Statewide results,
priority and coordinator inputs are read only. No Git command is used by these
scripts. No script is a live collector or a forecast.

Open [index.html](index.html) locally. It links every priority district's original
official PDF, contact sheet and two distinct GIS snapshots. The
[asset manifest](manifest.csv) gives direct official URLs, owner, vintage,
approval status, UTC retrieval, CRS, counts, bytes and SHA-256. The
[source manifest](evidence-manifest.json) additionally preserves every original
response hash, stored hash, response-header hash, HTTP/effective-URL metadata,
curl status and access failure. `raw/` and `originals/` contain source bytes;
`derived/` contains generated artifacts. Original PDFs and ZIP are unmodified.
HTML and native EsriJSON responses use lossless deterministic gzip.

## Offline rebuild

Python 3.11+ and system Poppler `pdftotext` / `pdfinfo` are required. Install the
pinned GIS/rendering dependencies in a temporary environment, outside the
checkout:

```sh
python3 -m venv /tmp/alaska-map-venv
/tmp/alaska-map-venv/bin/pip install -r senate/2026/alaska/maps/requirements.txt
/tmp/alaska-map-venv/bin/python3 -B senate/2026/alaska/maps/build_maps.py
python3 -B senate/2026/alaska/maps/audit_maps.py
```

The independent audit needs only Python's standard library and `pdfinfo`. It
checks all original/header and asset hashes, ZIP CRCs/member hashes and binary
record counts, complete service object-ID batches, all 41 native districts,
all 523 + 522 historical results units, exact 28 x 2 vintage coverage, each PDF
page and native precinct ID, GeoJSON bounds/rings, unknown November approval,
local links, object sizes below 40 MiB, and absence of runtime caches. It writes
[validation.json](validation.json) and [artifact-manifest.json](artifact-manifest.json).
A passing artifact audit does not approve defective geometry.

`build_maps.py` records library versions in [checks.json](checks.json). It uses
pyshp to interpret polygon shell/hole winding, Shapely/GEOS for topology and
pyproj with `always_xy=True` for EPSG:3857 -> EPSG:4326. Native rings and their
original CRS remain in the official ZIP and EsriJSON. Full precision GeoJSON
serialization compacts whitespace only. No simplification, coordinate rounding,
repair, clipping, or allocation of verified votes occurs in these geographic
derivatives. SVG previews use projected coordinates fitted independently to the
district, rounded only to 0.01 display units. Contact sheets render every PDF
page; representative JPEGs use 1.5 pixels per PDF point. No PDF is rewritten.

## Optional network refresh

Refresh deliberately replaces the dated research snapshot. Preserve it first
if the reviewed observation is needed. System `/usr/bin/curl` uses default
certificate validation; there is no insecure TLS option. Python requests is
not used for Alaska downloads.

```sh
python3 -B senate/2026/alaska/maps/fetch_maps.py --refresh
python3 -B senate/2026/alaska/maps/fetch_locator.py --refresh
```

`fetch_maps.py` first saves the modern primary DOE map page. Each PDF URL must
be present both in the turnout dispatch and the newly observed page. PDFs are
downloaded sequentially in the exact 28-HD rank order. The ZIP URL is parsed
from that page. The combined statewide PDF is not duplicated because the
individual packets plus statewide GIS already provide the required coverage.

`fetch_locator.py` retains the official homepage and polling-place page, the
DOE-linked app and its webmap configuration, service owner/item/schema, count,
all object IDs, and all 9 batches of at most 50 features. Each batch must match
its requested IDs and have no transfer-limit flag. Native EsriJSON requests use
all fields and geometry, with no `outSR`, quantization, geometry precision or
spatial filter. An HTTP 200 containing an ArcGIS error cannot pass the batch
checks. Full statewide coverage is retained, including nonpriority districts.

The bounded legacy-route probe can be reproduced separately; its saved HTTP
405 response is evidence of an access failure, not a map:

```sh
python3 -B -c 'import sys; sys.path.insert(0,"senate/2026/alaska/maps"); from fetch_maps import fetch; fetch("https://www.elections.alaska.gov/Core/districtmaps.php", "raw/legacy-districtmaps.html.gz", True)'
```

## Interpretation limits

- `baseline-2024` is the April 2024 precinct-adoption / May 15, 2023 Final
  Proclamation publication. `current-retrieved-2026` is a separate current
  locator observation, not a certified November 2026 vintage. Both contain 402
  physical features. Their identical native-ID sets do not prove equal geometry.
- The archive has eight features with all rings counterclockwise. pyshp warns
  and treats these as shells; all coordinates remain present. See
  [ring-orientation-checks.json](ring-orientation-checks.json). The current
  service does not have this winding anomaly. Self-intersections and measured
  overlaps remain in [topology-checks.json](topology-checks.json). No legal
  boundary/gap certification is performed.
- [snapshot-comparison.json](snapshot-comparison.json) preserves strict and
  tolerance-based coordinate diagnostics. Shapefile binary floats versus
  decimal JSON can defeat exact equality. A comparison tolerance is not a
  change applied to any source geometry and does not create a crosswalk.
- [reporting-unit-compatibility.csv](reporting-unit-compatibility.csv) retains
  all native keys/labels. 2024 physical IDs have an inventory match; 2022 units
  have no established crosswalk. Administrative Absentee/Early/Question units,
  mixed-method Early Voting labels and HD99 are never assigned polygons.
- County FIPS stays blank and state FIPS is `02`. House district numbers across
  election years are not evidence of spatial equivalence.
