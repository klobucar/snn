# Texas partisanship evidence and scenario schema

Research observed October 17, 2026 Central / October 18 UTC. These are historical counts and conditional arithmetic, not a 2026 turnout or win forecast. Reproduce from repository root with Python 3 and Poppler `pdftotext`:

```sh
python3 senate/2026/texas/data/baselines/build.py
python3 senate/2026/texas/data/baselines/native_evidence.py
python3 senate/2026/texas/data/baselines/primary_audit.py
python3 senate/2026/texas/data/baselines/county_controls.py
python3 senate/2026/texas/data/baselines/reconcile_peer.py
python3 senate/2026/texas/data/baselines/provenance.py
python3 senate/2026/texas/data/baselines/render_report.py
python3 senate/2026/texas/data/baselines/validate.py
python3 senate/2026/texas/data/baselines/provenance.py --assets
python3 senate/2026/texas/data/baselines/validate.py --verify-assets
```

`fetch.py <id> <exact-url>` retains new network evidence with HTTP metadata; it is not needed offline. URLs in the original retrieval metadata and CDX responses are the audit reference. Do not replace a pinned original with a current fetch without recording the new vintage. Generated gzip outputs use mtime 0. Source files are referenced in place to avoid duplicating originals from the turnout/coordinator and House Clerk PDFs from other states.

## Primary county table: `../county-baselines.csv`

1,016 rows, exactly 254 counties for each of four contests. Unique key `(contest, county_fips)`. Order is descending all-candidate **2024 Senate** volume, FIPS ascending for exact ties, then the four contest records within each county. This order is repeated for the sensitivity tables; it is not each contest's separate volume rank.

| Fields | Meaning |
| --- | --- |
| `contest`, `election_date`, `seat_relation` | `2020-senate`: Cornyn/Hegar, same Class II seat as 2026. `2024-senate`: Cruz/Allred, Class I other seat and volume contract. `2024-president` separate comparison. `2022-governor` Abbott/O'Rourke; there was no 2022 Senate election. |
| `county_fips`, `county_name`, `dispatch_key` | Derived five-character FIPS, MEDSL county name, and `TX:<FIPS>`. FIPS/canonical names are mapped from pinned MEDSL county rows; they are not printed county codes in the SOS PDF. |
| `native_county_name`, `native_county_code` | Exact SOS name. Code blank because no native code is printed. Explicit aliases only: COLLINGSWOR → COLLINGSWORTH (48087); THROCKMORT → THROCKMORTON (48447). |
| `d`, `r`, `other`, `candidate_votes`, `pair_votes` | Integer valid votes; D/R are the named DEM/REP candidates, other is every remaining valid named candidate. `candidate_votes=d+r+other`; `pair_votes=d+r`. Other is never relabeled Democratic. |
| `pair_participation` | `(d+r)/candidate_votes`; contest participation within this candidate universe, not a ballot/registration rate. |
| `d_pair_share`, `d_minus_r_pair_margin`, `d_minus_r_all_candidate_margin` | Fractions: D/(D+R), (D−R)/(D+R), (D−R)/all valid candidates. Multiply by 100 for percentage/share/margin points. Zero-denominator quantities are blank. |
| `pair_weight`, `candidate_vote_weight` | County proportion of that contest's statewide pair votes / all valid candidates respectively. Each universe sums to one independently. |
| `historical_winner`, `closeness_band` | Observed D/R pair comparison and absolute pair margin ≤5 pp, >5–10 pp, >10 pp. Historical outcome only; no permanent county label or 2026 classification. |
| `senate2024_volume_rank`, `senate2024_cumulative_votes`, `senate2024_top15`, `senate2024_priority80` | Full rank and exact integer priority contract. Smallest descending set satisfies `5*cumulative >= 4*state_total`; its predecessor does not. Top 15 contained in the 34-county set. |
| `ballots_cast`, `registered_voters`, `undervotes`, `overvotes` | Blank: not published as county controls in the selected SOS county canvass. Blank never means zero. Separate native/primary vendor controls preserve what they actually publish. |
| `method_split_status`, `source_id`, `status`, `geography_vintage` | Source, publication status and geographic limitations. No current precinct crosswalk or approval is implied. |

## Candidate and statewide controls

`county-candidates.csv`: 6,604 rows = 254 × (5 Senate 2024 + 10 president 2024 + 6 governor 2022 + 5 Senate 2020). Unique `(contest, county_fips, candidate_order)`. `native_candidate_name`, `native_party`, `write_in`, `votes` retain the complete named universe, including explicit published zeros. `county_contest_total` repeats a control and must be counted only once per county. `native_county_order` is the printed order; `source_section_line` locates independently extracted text within a literal contest section. Presidential overflow columns follow the source's sequential county order; their separate lines are retained in `primary-extraction.json`.

`state-candidate-controls.csv`: 26 controls independently parsed from the statewide SOS PDFs. Preserves the statewide printed label separately, since presidential slate names truncate on page 1; full source slate names come from the county header. `difference=county_sum−votes`, required zero. `state_contest_total` is a repeated denominator. `primary-extraction.json` also retains each literal county row, the printed TOTAL row, and text lines. `vintage-comparison.json` checks every candidate/county integer in three 2024 county captures and both 2020 county captures; no changes in the selected contests were found. Do not infer a correction chronology from identical counts.

House Clerk 2020/2024 publications independently agree with Senate statewide totals; 2024 Clerk groups presidential valid write-ins, while SOS lists six named slates. The 2022 Legislature's joint canvass independently agrees with all four party candidates and the two named write-ins' combined 1,637, published as “Others.” These are distinct source presentations, not replacement candidate labels.

`priority-set.json` and `peer-reconciliation.json` retain independent ranking/field checks and peer hashes. County-level coordinator acceptance is distinct from finer-unit acceptance. The read-only coordinator audit is outside this worker's writable scope.

## Targets and sensitivity

`county-target-scenarios.csv`: 5,334 rows = 254 × 7 scenarios × 3 targets. `state-target-scenarios.csv`: 21 rows. Unique `(scenario,target,county_fips)` / `(scenario,target)`.

The four Senate-preference sensitivity scenarios hold **2024 Allred/Cruz county shares** fixed, then use observed all-candidate county volumes from 2022 governor (low), 2024 Senate (base), 2024 president (high), and 2020 Senate (additional). Convert each county's hypothetical contest volume `V_c` to pair volume `T_c=V_c*p_c`, with `p_c` the county's observed 2024 Senate pair participation. The low/high names describe these historical volume examples; they are not estimated 2026 ranges. Three additional scenarios retain each other contest's own preference and actual volume/participation. Read each row's `preference_baseline`, `volume_basis`, `pair_participation_basis`; no statewide common participation shortcut is used. Fractional scenario counts are conditional expected volumes; original historical integers remain unchanged.

Fields preserve historical D/R, baseline pair share, hypothetical all-candidate volume, county pair participation, expected pair votes, pair weight, baseline net, target margins on **both** pair and all-candidate denominators, unbounded/bounded uniform shifts, clipped count/flag, bounded share/net, gain, +1 pp share net value, and selected-county-only requirement/status with all others fixed at baseline shares.

For `T=sum T_c`, `M=sum T_c(2s_c−1)`, pair target `g`, unbounded `δ=(g*T−M)/(2T)`. Targets: tie `g=0`; `A+1-pair-margin` `g=.01`; `A+1-all-candidate-margin` `g=.01*sum(V_c)/T`. Thus D+1 **pair margin** adds 0.5 share points to the tie shift; the all-candidate margin target adds `0.5/participation` share points. A +1 pp pair-share change contributes `0.02*T_c` net votes. All candidate votes outside the named pair remain outside this transfer.

Feasible solve uses `q_c=clip(s_c+δ,0,1)` and bisection on the actual clipped statewide net. Unbounded values remain available. Actual scenarios have no clipping; validator exercises a case where clipping changes the answer. Selected county `q=[T_c+g*T−other_net]/(2T_c)`: <0 already secured, >1 impossible, no positive pool undefined. “Already-winning” uniform status is target-relative; it does not force a positive improvement. All actual county pair pools are positive; no missing historical cells are replaced by zero.

`targets.py --county-fips 48201 --others-share-shift-pp 0 --margin-pp 1 --denominator pair` provides a conditional solve; use `--scenario` to select a retained mix. It clips changed other-county shares explicitly and reports clipping. No one county target is independently necessary.

## Fixed-counted live remainder arithmetic

`live_remainder.py` accepts JSON with `counted={A,B,other}`, `remaining=[{unit,pair_votes,other_votes,A_share}]`, `target_margin`, `denominator` and optional `selected`. A/B identities are explicitly supplied by the scenario; no actual 2026 candidate roster is assumed. The operator must map real final ballot IDs before any future use. `other` is a separate pool, never A. Counted votes cannot be shifted. Unknown counts stay unknown; negative inputs fail; zero solved pool has an undefined required share with an explicit target status.

Final denominator is counted pair + all remaining pair, adding counted and remaining other for `all-candidate`. Required share uses the target net on this **final** denominator. `live-examples.json` contains synthetic statewide/selected-unit tie, pair/all-candidate cushions, low/base/high remainder inputs and unknown/no-pool/impossible cases. Unit labels are illustrative and unmatched to a known remaining electorate. This is neither a live collector nor a probability model.

## Native-unit evidence, preserved separately

- `native-units.csv.gz`: all 31,702 observed OpenElections source identities across all offices, unique `(source_id,native_county_name,native_unit_id)`. Unit strings remain unchanged, including central/administrative/combined or empty labels. Type is unverified. Every nonheader source row contributes to its inventory count. Repeated CSV column headers are retained in `native-source-anomalies.json` and the originals, not fabricated as reporting units.
- `native-cells-<year>.jsonl.gz`: every selected relevant contest/control row, with source ID, original CSV row ordinal (header=1), exact raw field/value dictionary, literal/file/mapped county identities and record-role annotation. Known exact normalized office variants are listed in `native_evidence.py`; state Senate and lieutenant governor are excluded. Original party/candidate/method spellings and blank/NA cells remain intact. No candidate-key deduplication. Composite raw record key `(source_id,source_row)` is unique even when a candidate key repeats.
- Coverage: 2024 184 county files / 10,786 units; 2022 one partial state file / 5,055 units; 2020 one partial state file / 15,861 units. The 2024 file labels Hardin/Hunt and Jeff Davis/Grayson conflict; literal identities cover 182 counties. Explicit source typo Hildalgo → Hidalgo and La Salle → Lasalle are mapped without changing raw strings. Blank Angelina county is mapped from its filename with that reason retained. The 2024 list omits 70 filename counties and contains two misidentified files; it is not a 254-county primary precinct roster.
- `native-source-diagnostics.json` retains duplicate candidate keys, every numeric-method nonadditivity, source office inventory, row roles and conflicts. Numeric method sum is a diagnostic only: modes can overlap, be missing or use differing definitions. No unexplained zeros, sums, deduplication or repairs enter accepted county totals.
- `native-peer-reconciliation.json`, `native-coverage.json`: all shared selected raw fields and complete native inventory/source-rowcounts independently compared to the turnout worker. They establish retention/agreement, not original-precinct certification or a 2026 match.
- `tlc-vtd-cells.csv.gz`: all 48,560 rows (five resources × 9,712). Exact `CNTYVTD`, `VTDKEY`, source field JSON and county prefix retained. These are the TLC **2024 general VTD vintage**, including 2022 results reallocated to that vintage. Every 254 county prefix retained. These keys are never relabeled native precincts. Noninteger turnout/share measures are retained but not summed as counts.
- `tlc-county-disagreements.csv`: every integer candidate/measure county sum compared with a matching primary candidate where available. Generic write-in versus named valid write-ins explicitly has incompatible scope. Missing primary controls stay blank. Every original disagreement remains unchanged.
- `primary-vendor-xml-rows.jsonl.gz`: every row/cell/attribute in every Dallas and Travis original vendor XML worksheet (74,575 rows); original ZIP member is `detail.xls`, Excel XML rather than a binary workbook. No administrative or text rows suppressed. `primary-vendor-table-identities.csv.gz` retains table row labels, including totals, across worksheets. `primary-vendor-selected-unit-rows.csv.gz` retains all registration/president/Senate row arrays; source worksheet and row distinguish appearances.
- `primary-vendor-candidate-conflicts.csv`, `primary-vendor-registration-controls.csv`, `primary-unit-audit.json`: independently checked numeric-column sums, candidate method totals, shared raw row equality and source-vintage/universe differences. Generic write-ins are not distributed among named candidates. These controls do not change primary county baselines.
- `original-{harris,bexar,angelina,midland}-2024.txt.gz` retains independently extracted full primary PDF text. `primary-pdf-unit-identities.csv` includes exact reporting-label evidence and page/line. Harris 1,584; Bexar 776 ballot-style units; Angelina 41 including 11B/17B; Midland 46 including suffixes. All source bytes remain referenced. PDF label presence checks alone do not certify a candidate/method table or match it to a polygon. Separately, `harris-primary-senate-unit-controls.csv.gz` independently extracts all 1,584 Senate unit rows, all five named candidates (preserving Roche before Andrus in this source), cast/under/over/registration and five ballot methods. Every unit balances; all five candidate sums match the SOS county row. `harris-primary-senate-controls.json` and `county-ballot-registration-controls.csv` retain the source-native controls. One unit has no turnout percentage; that field stays blank. These separately sourced controls do not change the chosen SOS candidate baseline. Administrative labels and reporting units in original evidence must remain available when a narrower parser lacks a mapping.

## Provenance, clocks and limits

`source-ledger.json` has exact original/stored hashes/bytes, requested/final URLs, retrieval UTC, HTTP status/headers and source scope for 223 responses/references. Read-only shared bodies are addressed by relative path plus hash; no mutable upstream dependency is needed offline. The preserved 2024 **county** footer is literally `07/01/2025 10.42 AM`; **statewide** footer is `01/07/2025 10:42 AM`. Date conventions and certification dates are not inferred from the strings or archive captures. HTTP retrieval time is not a count-update time. The archived April capture can contain an earlier publication; no cause/timeline is assumed.

`asset-manifest.json` hashes every owned deliverable except itself; excludes Python cache files. All listed stored assets must be strictly below 40,000,000 bytes. Uncompressed shared Harris PDF exceeds that threshold, and its compressed body also exceeds it, so use the two hash-checked ordered compressed parts (32,000,000 and 11,773,799 bytes), concatenated before decompression; this assignment does not duplicate that PDF. `validation.json` records offline checks and material limitations. `--verify-assets` is read-only so validating the manifest does not modify the file it hashes.
