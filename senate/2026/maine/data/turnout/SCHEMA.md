# Maine turnout tables and dispatch contract

All source paths inside tables/JSON are relative to `senate/2026/maine/data/turnout/`.
The output `../county-turnout.csv` uses the requested compatibility name but has
512 native municipal/administrative reporting units, not county rows.

- `native_key`: source-backed composite `ME:SOS:<election-date>:<native county
  code or STATE>:<percent-encoded trimmed source MUNICIPALITY>`. This is a
  research key, not an invented official numeric ID. `native_state_numeric_unit_id`
  is blank because none is published. `unit_name` preserves raw text, including
  trailing spaces. County FIPS describe the printed reporting county; unallocated
  STATE UOCAVA fields are blank. No polygon allocation is inferred.
- `rank`, `senate_votes_2024`, `vote_denominator`, `weight_exact`, `cumulative_votes`,
  `cumulative_share_exact`: 2024 Senate published four-candidate initial municipal
  tally, excluding BLANK. State denominator 821072. Exact fractions are reduced
  rational strings (including `1`); decimal share columns are rounded displays.
- Candidate columns explicitly name Independent Cherry, Democratic Costello,
  Independent King and Republican Kouzounas. They sum to `senate_votes_2024`.
  BLANK plus candidates equals TBC (`ballots_cast_2024`), without inferring detailed
  undervote/overvote categories. Methods overlap only if additional source views
  are later added: do not sum such views into these complete initial totals.
- `top15`, `minimum80`, `priority` are 0/1. Priority is the union of top15 and
  minimum80, here exactly the first164. Sort descending candidate votes, ascending
  native county code (empty for UOCAVA), ascending trimmed source name, Python
  Unicode order. Exact crossing is `5*cumulative >= 4*statewide`.
- `ballot_*` columns use independent descending TBC ranking and 842447 denominator.
  The separate comparator `*-ranked.csv` tables independently rank candidate and
  ballot volume using each complete source universe; their flags are True/False.
- `president_2024_*`, `governor_2022_*`: conservative links by native county and
  lexical name normalization only; values/ranks come from the comparator's full
  independent ranking. A join is not a boundary crosswalk. Blank means unmatched,
  not zero. `comparator-label-crosswalk.csv` documents every attempted base link;
  unmatched comparator rows remain in their own complete rankings.
- `registered_{active,inactive}_{2024,2022}`: dated registration stocks linked by
  the same conservative label rule. Not ballots and not a rate denominator for
  voting-eligible population. Do not sum partial joins as statewide counts.
- `source_path`, `source_sheet`, `source_rows`: exact provenance. Source-row CSVs
  are long tables with every candidate, BLANK and TBC for each raw row. Their unique
  identity is (`source_row_key`,`source_column`), not the name. Governor2022 has
  510 raw rows/509 grouped labels because Cranberry Isles is repeated twice with
  distinct positive counts. Preserve both rows; no claimed ward identity.
- `county_section_code` and `county_label_conflict` in raw tables distinguish the
  2022 T3 ND Twp source defect: row190 prints PEN inside HAN's section. The county
  context table uses printed native codes and therefore differs from the certified
  HAN/PEN section controls by four votes. Do not silently repair it.

`priority-set.json` has ordered `priority`, `nonpriority_remainder`, and
`all_unit_coverage` arrays. Each entry retains source paths/rows and available
historical CVR district-intersection keys. `results_ward_precinct_ids` is empty
because statewide selected result workbooks publish no such IDs. Registration
constituents do not certify reporting-precinct or polygon equivalence. A CVR key
combines county, municipality, W/P, CG, SS, SR and CC plus year; active/inactive
are distinct statuses in the separate registration table. All unmatched units
survive. Numeric or name equality across years is not boundary equivalence.

`priority-keys.txt` contains only the ordered164 exact keys, UTF-8 with LF after
each key including final. SHA256:
`086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407`.

Offline: run `build_turnout.py`, `compare_vintages.py`, `write_report.py`, then
`hash_assets.py`, then `validate_turnout.py` with `PYTHONDONTWRITEBYTECODE=1`.
`asset-manifest.json` hashes every owned asset except itself and the generated
validation report; `manifest.json` separately hashes original/saved source bytes.
`xlsx_read.py` reads cached
OOXML cells and preserves row/column addresses; it does not modify originals.
`extract_pdf_evidence.py` rebuilds PDF text/previews with Poppler. Network refresh
is separate (`fetch_evidence.py --only ID ...`), requires requests, and uses the
retained manifest's known URLs with a 30s timeout/38MiB cap; no crawler/pagination.
Historical legislative library files have their own URLs/status and are never
relabeled as current SOS downloads. HTTP Last-Modified, workbook timestamps,
filenames and retrieval dates are different provenance fields, not interchangeable
certification dates. Raw files and sheet extracts are losslessly gzip-compressed.
