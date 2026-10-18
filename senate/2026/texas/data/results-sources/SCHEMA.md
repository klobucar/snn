# Texas official reporting schema and limits

## County authority and source inventory

`../official-results-sources.csv` has exactly one row per county, in the accepted
2024 Senate volume order. `dispatch_key=TX:<five-digit FIPS>` comes from the
accepted county CSV. `rank` and `priority` retain the exact 34-county contract.
All 254 current SOS directory authority labels are matched by complete county
name; 239 have a county website anchor in the SOS publication directory. For
the other 15, the office directory remains authoritative and the historical
source-list route is separately labeled discovery. No legal authority count is
inferred from the number of websites or vendor entities.

`authority_role/name` are the observed directory snapshot, not timeless office
assignments. `state_county_id` and `state_mid` are source-native integers.
**MID is 48000 + alphabetical ID and is not FIPS.** Exactly one MID happens to
equal a real county FIPS. The only approved join here is complete native county
name equality to all 254 canonical county names. No substring matching.

JSON fields in the CSV preserve sets of local routes/statuses and the peer
source-list record. `evidence_path` resolves relative to this directory. Blank
remaining votes, measured cadence, timezone and November unit counts are
unknown, not zero. `research_scope` distinguishes 34 individually investigated
priorities from the remaining 220 discovery entries. All priority records also
contain the complete source-native state county Senate object, summary, key
map and EVR row, with source hashes and field pointers.

## HTTP evidence and provenance

`raw/<id>.json`: exact GET request URL, final URL, redirect chain, retrieval
start/end UTC, status, headers, original decoded entity bytes/SHA-256, lossless
gzip stream bytes/SHA-256, and ordered stored part paths/bytes/SHA-256. Failed
connections have an exception and `body_complete=false`; HTTP failures can
have complete error bodies. A 202 empty entity is complete HTTP content but
does not contain usable results. `body_scope` makes that distinction explicit.
The fetcher never truncates; source pagination, absent elections or unknown
roster scope remain semantic limits even with a complete response.

`parent_id` is research context; it is not automatically proof of a hyperlink.
An explicit purpose identifies an actual HTML link, bundle-assembled public
route, search/peer discovery or HTTPS retry. `publication-link-inventory.json`
retains complete observed anchor/iframe/script labels and targets. The state
chain and inspected Clarity/Harris route formulas are documented in the report
and code-route evidence. Search-discovered/peer links cannot by themselves
establish official current publisher status. The unverified legacy Clarity
`pr.json` probes failed and are excluded; `status.json` is the actual observed
current reporting-state resource.

`source-ledger.json` indexes every request. `shared-evidence.json` pins read-only
source ledgers, originals, candidate tables and native inventories; paths use
the declared base, applying each record's `dependency_root` when present
(some originals are owned by the baseline worker). Its source metadata preserves original hashes, stored hashes,
URLs and retrieval clocks without duplicating original bodies. Metadata and
source footer times are not a certification or correction chronology.

## State November setup

Actual public app bundle literal routes:

```
/api-ivis-system/api/s3/enr/electionConstants
/api-ivis-system/api/s3/enr/election/53815
/api-ivis-system/api/s3/enr/election/countyInfo/53815
/api-ivis-system/api/s3/enr/electionRss/53815/history
```

`upload` and the non-Version election objects are base64 JSON. `Version` is a
literal string, not base64. Election 53815 comes from constants; default
`currentelectionInfo` is still 2025 election 51031. No default-election inference.
Senate contest 5075 has seven named candidates; `Federal.Races` and county
`Races['5075'].C` overlap and must not be summed together. County candidate `id`
matches statewide `ID`. Party spellings differ (state LIB versus county L), so
retain literal values rather than joining on party labels.

Home has literal date `11032026`, `LastUpdatedTime=Oct 16, 2026 16:12:10` (zone
unknown), counties CR/CT 0/254, precinct PR/PT 0/5, polling PLR/PLT 0/5299 and
RefreshTime 5. All county Senate TP/TPR sum to 9900. These incompatible setup
denominators remain separate. Candidate V/EV/PE and T/TV, race PR/TP/TPR/OTRV,
and county Summary PRR/PRP/P/RV/VC/VT/NPL/PLR/PLP remain source fields, not a
documented outstanding-vote model. Initial published zeros are retained as
zeros; missing semantics stay null. ReportList flags all false, fileTypes empty;
RSS history response is empty. No actual certified November results exist in
these observations.

Public EVR route uses `getFile?type=EVR_ELECTION` then the actual November ID and
published date option with `type=EVR_EARLYVOTING`. The sample contains all 254
aggregate rows, date_updated 2026-10-17, zero in-person total and 46,998 in the
field `total_mail_votes_for_election`. These are turnout statistics, not
candidate counts or proven accepted/tabulated/published valid Senate votes.
Do not download individual-voter reports to construct an outstanding estimate.

## Local source-native units

`native-unit-observations.csv.gz` has every indexed source position, including
all retained contest-detail appearances. Composite key is source_id + pointer.
`raw_row_json` preserves the aligned native row arrays/attributes at that
position; source-level arrays and controls remain in the original body.
`native-unit-identities.csv.gz` groups only within source, county, election,
observation class, kind and exact native ID, retaining occurrence counts and
the first pointer/row. It does not deduplicate candidate observations or combine
different sources. `native-field-schemas.json` records root fields, array bounds
and current settings; full originals control any unindexed field.

Clarity source `status.P` is a native reporting-label array, with parallel
S/R/B/C/CONTEST. It is not automatically a physical precinct roster. Tarrant
retains labels with ` - F99` and ` - FSB` suffixes; their allocation/type remains
unverified. `details.Contests[].P` repeats relevant native labels per contest;
`V/T` arrays overlap summary totals. `vc[].voteCenter.idVoteCenter` is a different
object with name/address/coordinates; `vc_status.P/S` is a separate status view.
No precinct-to-vote-center join is inferred. Source status enum includes
Certified/NotReported/PartiallyReported/Participating/CompletelyReported/
NotParticipating; completion of one category is not final certification.

Clarity `summary` uses contest K/C, CH/P/V/PCT parallel candidate arrays,
PR/TP and T. Candidate identities are source array positions unless a real ID
is provided; none is manufactured. `vt.Types` supplies source method names;
`vt.Contests[].Votes` is candidate × method. Tarrant uses Absentee/Early/Election;
Bexar Election Day/Absentee/Early Voting; El Paso Election Day/Early Voting/
Absentee By Mail. V and its method views overlap. `IsRCV=false` is a local
software field, not a legal rule for some other race. Settings' recount/runoff
thresholds are configuration, not the Texas legal recount eligibility test.

Harris 1126 uses Senate i=9189; ca candidate labels align to ab/ev/ed/tv and
under/overvote arrays. A generic WRITE-IN is retained as one bucket and never
allocated across the four declared write-ins. `pr.json` and `pv-9189.json` have
all 1224 native p labels, distinct from 2024 original 1584 and SOS setup1225.
Timestamp dt ends Z (UTC), but is a September setup timestamp. County status
and Senate-detail appearances overlap. Registration/ballot setup zeros do not
prove zero eligible people. Current geographic approval and crosswalk are null.

Tarrant127297, ElPaso127348 and FortBend127480 are **test_mode_excluded** despite
November dates and hidden test watermarks. Bexar127291 is **November_initial_zero**
with testmode0. Bell126390 (May26 runoff) and Parker126014 (March3 primary)
are **older_election_excluded**. Their native identities remain available for
lexical comparison with their exclusion labels. Collin's retained CSV is a
June13 local runoff. No old/test rows become November votes.

The retained Grayson March3 Democratic primary PDF has 546 pages and 42 literal
precinct labels. All 546 header appearances are indexed as `pdf_precinct_label`
with PDF page/text-line pointers. Only the exact normalized report title is
excluded; IDs are not selected by numeric shape or a word substring. Source
lines remain in the complete Poppler text derivative and original PDF. This is
older-election evidence; it adds no November geographic approval.

## Historical controls and missing geography

The accepted county ranking uses all five 2024 Senate candidates and reconciles
to 11,291,854. There was no 2022 Senate contest; governor is a comparator and
2020 Senate is the same-seat comparison. County 2024 footer
`07/01/2025 10.42 AM` and statewide footer `01/07/2025 10:42 AM` remain distinct.
Archive/retrieval time is separate. Exact COLLINGSWOR/THROCKMORT labels and their
explicit FIPS aliases are retained in peer originals; no new spelling repair.

Shared historical inventories retain 31,702 derivative identities, 4,276 primary
identities and TLC VTD rows in separate scopes. Hardin/Hunt and Jeff Davis/
Grayson filename conflicts, duplicate candidate keys, nonadditive methods,
partial OE coverage, original vendor universe/vintage differences and TLC
redistricting discrepancies remain unresolved. No source agreement certifies
a precinct polygon or November reporting crosswalk. `county-native-coverage.csv`
uses null for unknown current approved unit counts, even where historical or
test/setup labels are available.
