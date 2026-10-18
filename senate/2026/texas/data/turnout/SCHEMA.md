# Texas turnout contract

County dispatch keys are `TX:<county_fips>`; FIPS is a five-character string.
County source identity is the **literal SOS PDF label**, including `COLLINGSWOR`
and `THROCKMORT`. These map explicitly to Collingsworth (48087) and
Throckmorton (48447); no source row is dropped or merged. SOS PDF provides no
county code; `source_county_code` is blank. FIPS mapping comes from the pinned
MEDSL county file and all 1,270 Senate county/candidate cells reconcile to the
actual archived SOS county canvass. Canonical display county names remain
separate from native labels.

`data/county-turnout.csv` contains all 254 counties, descending 2024 Senate
all-candidate votes; equal counts break by ascending FIPS. `senate_2024_total`
is five reported valid candidates, including Tracy Andrus and Analisa Roche
named write-ins. It is the **Class I other seat**, not the Class II seat being
contested in 2026. `senate_2024_other` includes Brown plus both write-ins.
President 2024 includes all ten named slates, including six write-ins. Contest
votes, ballots, registration, under/overvotes and method counts are different
fields. Optional unknowns are blank; zero means an explicit reported zero.
Fraction shares are decimal fractions, never percentages. Cumulative counts
are integers; top15/priority80 flags are 0/1. The 80% test uses integer
`5*cumulative >= 4*state_total`; the previous set must fail it.

`county-candidates-2024.csv` is one original county/candidate row per contest,
with literal county identity, primary party/write-in indicator, count, county
contest total, PDF page and source row order. `primary-county-extraction.json`
retains both named panels of the presidential table and all three archived
PDF vintages. The last two presidential candidates are on an unlabeled
continuation panel: match the 254 rows in the source's unchanged county order,
then require all 254 row totals, all ten candidate state sums and the stated
state total to balance exactly. No residual allocation is allowed.

`priority-set.json` stores the source denominator, original source hash, full
254-key order, top15 numerator, minimum80 numerator and keys, previous-set
numerator, crossing county, remainder and all constituent reporting identities
available in the separately versioned layers. County groups contain county
returns; observed precinct/administrative units and derived VTDs are separate
layers, never added to the county total. Coordinator must accept independent
reconciliation before second-wave dispatch.

Source payloads are retained losslessly in `raw/*.body.gz`; adjacent metadata
records requested/final URL, retrieval UTC, status, all response headers,
original and stored hashes/lengths. PDF text is produced by `pdftotext -layout`.
An HTTP or archive capture date is not a canvass date. Source footer labels
are preserved literally (some PDFs format day/month differently). Historical
precinct/ballot-style/central units, VTD geography and 2026 approved boundaries
are distinct; no cross-year or 2026 unit crosswalk has been proved.

## Finer layers and controls

`native-reporting-units.csv.gz` retains each unique **source file + literal
source county + literal precinct/reporting ID** across every source office,
with source-row count and first row. This inventories identities; it does not
deduplicate raw candidate rows. `native-records-{2024,2022,2020}.csv.gz` retains
every row for all observed exact office variants of the chosen contests and
participation controls. It contains the complete original row as JSON plus
all method columns, original row number, office, district, candidate, party,
count string and role. Header variants are normalized solely for selecting
contests. Counts and source labels remain unchanged. Generic write-ins,
under/overvotes, total rows and registration remain distinct. `id` is a source
row identifier, not a voting method. Numeric method columns are not assumed
mutually exclusive or exhaustive; nonadditive rows are listed explicitly.

Source aliases `La Salle` and `Hildalgo` map explicitly to 48283 and 48215 in
the derivative layer; source strings remain. Angelina's CSV lacks a county
column, so its file name supplies the county mapping. Two repeated Eastland
CSV header rows are retained as explicit nondata anomalies. The file named
Hardin labels its rows Hunt; Jeff Davis labels rows Grayson. Those source
labels are preserved with filename-conflict diagnostics; neither file is
silently reassigned to the filename county. All derivative allocation remains
unvalidated. Source files and native labels may overlap; no deduplication,
rescaling, balancing adjustments or candidate residual allocation is performed.

`primary-native-units.csv.gz` separately inventories original county PDF and
vendor workbook identities, including Angelina `Precinct 11B` and `Precinct
17B` even without Senate candidate rows. `primary-native-records.csv.gz`
retains original Dallas/Travis registration, presidential and Senate workbook
row arrays and expanded candidate/method header arrays. Aggregate `Total:`
rows have their own scope and are not precincts. Every selected numeric column
sums exactly to its own source Total. The original PDF unit rosters are not a
claim that every PDF candidate/method cell has been validated.

`primary-harris-senate-units.csv.gz` is a stronger complete primary extraction:
all 1,584 original Harris Senate units, five named candidates, cast votes,
under/overvotes, five ballot method counts, ballots and registration. Every
unit balances internally and each named candidate's county sum exactly matches
the SOS county canvass. Missing source turnout percentage remains blank.
Only Harris and the two original vendor statistics tables populate county
ballots/registration; their explicit source IDs are supplied. Registration
status composition and snapshot dates remain blank/qualified. These available
county ballot values cannot establish a complete statewide ballot ranking.

`tlc-derived-vtd-units.csv.gz` preserves every CNTYVTD/VTDKEY and complete source
row for each of five 9,712-row TLC files. Count sums use count fields only;
Spanish-surname turnout fractions are preserved without summing rates. The
county reconciliation compares named candidates and the explicit summed valid
write-in group to the primary controls, while retaining generic-write-in scope
differences. No VTD is promoted to a physical precinct or a vote center.

Harris's original 52,427,785-byte PDF is retained as one lossless gzip byte
stream split into ordered 32,000,000- and 11,773,799-byte parts. The metadata
contains each part's hash and the complete stored/original hashes. Concatenate
parts, then decompress; no original byte is removed. `readraw()` reconstructs
it automatically. The fetcher applies this split to any stored object at least
40,000,000 bytes. Source PDFs embedded inside ZIP files remain compressed;
Dallas's 84 MB inner XML workbook is parsed in memory, never retained as an
oversize asset.
