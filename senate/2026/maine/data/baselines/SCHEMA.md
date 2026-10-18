# Maine baseline and scenario schema

Version: `maine-baselines-1`. Research date 2026-10-17 local / primary retrievals 2026-10-18 UTC. All files are UTF-8; CSV uses a header and ordinary quoted fields. Empty means unavailable, undefined or inapplicable as explained below, never an inferred zero. Counts are integer observations; scenario votes can be fractional expectations.

## Main compatibility CSV

`../county-baselines.csv` has 2,052 disjoint original workbook rows: 517 Senate 2020, 510 governor 2022, 512 Senate 2024 and 513 president 2024. The filename is retained for project compatibility. It does not imply county-level observations. Footer totals are excluded. Never add overlapping contests or years into one turnout total.

| Field | Meaning |
| --- | --- |
| `source_id`, `election_date`, `contest`, `stage` | Explicit election/contest and initial municipal tally stage. No observed central elimination rounds are represented. |
| `source_row_id` | Derived coordinate key `source_id:sheet:R<Excel row>`. Unique in this file; not a state-issued numeric jurisdiction ID. |
| `native_key` | Accepted comparison key `ME:SOS:<date>:<county code or STATE>:<percent-encoded trimmed exact MUNICIPALITY>`. It does not encode contest; the same date/key can occur in Senate and president. Two governor Cranberry rows also share a key. Use `source_row_id` as the disjoint-row primary key. |
| `native_unit_name` | Exact cached workbook label, including trailing whitespace. |
| `unit_name` | Display label, trimmed at both ends only. |
| `native_county_code` | Exact literal A-column code; blank for STATE UOCAVA. |
| `county_section_code` | Printed workbook county-block membership, determined independently of a row's literal county code. Only governor row 190 disagrees: native PEN / section HAN. |
| `parent_county`, `county_fips` | County name and five-character FIPS mapped from the literal native code. These are not silently corrected to the section. Both fields blank for STATE UOCAVA. |
| `native_numeric_unit_id`, `ward_precinct_id` | Blank: not published in selected result workbooks. Registration district intersections are not used as invented vote precincts. |
| `unit_type` | Conservative source-label category: administrative STATE UOCAVA, label containing a composite slash, or native municipal/plantation/township label. Not a legal classification or polygon claim. |
| `<candidate_id>_votes` | Observed candidate/category count. Empty for candidates absent from that source, versus actual zero where the source publishes zero. IDs are explicit analysis slugs; original names/parties/columns are in `candidate-votes.csv`. |
| `d_votes`, `r_votes`, `other_votes` | Named D, named R and all remaining published candidate categories. In 2024 Senate, other includes King and Cherry separately retained in their own columns. Independent is never relabeled D. |
| `contest_votes`, `blank`, `tbc` | All published candidate/Other categories; source BLANK; source TBC. Candidate votes + BLANK = TBC for every row. No inferred overvote/undervote split. |
| `d_r_pair_votes`, `d_r_pair_d_share_pct`, `d_r_pair_margin_pp` | D+R denominator; 100*D/(D+R); 100*(D-R)/(D+R). Shares/margins are empty for zero pair votes. |
| `d_minus_r_votes`, `d_r_historical_label`, `d_r_closeness` | D-R net, pair leader, absolute pair-margin band ≤5 / >5–10 / >10 pp. These labels do not identify the all-candidate winner. |
| `initial_leader` | All-candidate maximum, ties shown with slash-separated distinct IDs. A zero-vote row ties every published category. |
| `contest_weight[_exact]`, `d_r_pair_weight[_exact]` | Weight within this source universe. Decimal plus exact reduced fraction; each weight system sums to one. |
| `net_votes_per_plus_1pp_d_pair_share` | 0.02*(D+R), holding that unit's turnout fixed. Not an all-candidate swing conversion. |
| `source_sheet`, `source_row`, `source_path`, `source_url`, `source_original_sha256` | Workbook coordinate, gzip path relative to this directory, originally linked URL and hash of decompressed original response bytes. |
| `source_status`, `geography_status` | Publication and historical-boundary limitations. Current corrected file labels are not exact release timestamps or November 2026 geographic approval. |

2020 candidate IDs are collins R, gideon D, linn IND, savage IND and the unspecified Others category. 2022: hunkler IND-Unenrolled, lepage R, mills D. 2024 Senate: cherry IND, costello D, king IND, kouzounas R. 2024 president: harris D, oliver Libertarian, stein Green Independent, trump R, west Justice For All, Others unspecified. The complete 9,241 observed candidate/category cells are in `candidate-votes.csv`; party labels remain explicit.

## Targets

Each `<a>-<b>-unit-targets.csv` preserves every raw baseline row for its contest. The primary three Senate comparisons have native, 2022 printed-section, and 2022 lexical/residual mixes; the three contextual comparisons have native mix. All use observed low/native/high volumes and tie / A+1 margin point targets. This produces 72 state scenarios and 36,948 unit rows.

`candidate_a`, `candidate_b`, `pair` identify the exact denominator. `expected_pair_votes` and `turnout_weight` describe assumed turnout, independent of `baseline_pair_share`. `baseline_net_contribution` is the fixed-preference contribution under those assumed weights. `unbounded_target_share` and `unbounded_uniform_feasible` expose impossible literal uniform shifts. `bounded_target_share` solves a common clipped additive shift across positive-weight rows. `actual_share_shift_pp` can differ at caps. `target_margin_pp` and `target_net_contribution` are the resulting bounded margin/contribution. Zero-pair rows retain zero weight and undefined displayed shares.

`selected_unit_required_share` holds the other units at their baseline shares under the selected turnout mix and solves that unit alone. It does **not** hold them at the table's uniform target. Below zero is already secured under those assumptions, above one impossible, and zero selected turnout undefined. `selected_unit_status` states that result. `net_per_plus_1pp_a_share=0.02*T_u` expresses share opportunity in net votes.

`state-scenarios.csv` records the original fixed-preference statewide net/margin, unconstrained shift, infeasible-unit count, bounded common shift, target and sum. The expected +1-net-vote share increment is an expectation; integer final pair totals impose parity. A+1 **margin point** is separately a 0.01*T net cushion. `scenario-settings.json` lists actual native base contest/pair volumes for each pair, fixed pair-participation conversion, zero-pair counts and observed preference anchors. No common 821,072-vote base is applied to the 2020 source.

## Historical mix assumptions

Native pair weights are directly observed. Printed-section weights use 2022 governor all-candidate volume shares for the 16 printed blocks and STATE UOCAVA while preserving the baseline's within-block pair proportions. This is an explicit coarser sensitivity, not a replacement topology or a municipal crosswalk.

Lexical weights use literal county code plus narrow spelling normalization. `mix-label-crosswalk.csv` records every match or unmatched allocation. No semantic matching of changed composite constituents is attempted. Matched label volume is allocated across any disjoint baseline rows sharing that label in proportion to their pair votes. The collectively unmatched 2022 volume is allocated over unmatched baseline rows in proportion to their pair votes. Such allocation is assumed, not observed in those individual units. All source bytes/rows remain unchanged. Neither lexical agreement nor county membership proves geographic comparability across elections.

`preference-sensitivity.csv` separately recenters the 2020 native shape to observed statewide D-R shares from 2020 Senate, 2024 president or 2022 governor. These different-contest anchors are not estimates of 2026 candidate effects.

## RCV, vintages and provenance

`conditional-rcv-examples.csv` and `conditional-transfer-allocations.csv` are explicitly assumed final-pair transfer exercises, unreachable with unchanged historical first choices because the majority winner stops the historical count. Candidate pools and exhaustion conserve ballots; no observed lower preferences are claimed. `explicit-coalition-example.json` names King and Costello as separate inputs and never calls their sum Democratic votes.

`source-vintage-cell-differences.csv` compares exact original archived/current workbook coordinates; no geographic join is required because their label/row universes agree. `source-vintage-state-controls.csv` distinguishes archive/Clerk from current SOS and the independent NARA five-candidate certificate. `source-vintage-investigation.json` records metadata clocks and chronology limits. Original bytes for both vintages survive in `raw/`.

`manifest.json` records source capture UTC, original/request/final URLs, headers, redirects, status, lengths and SHA-256 of both original and gzip bytes. `workbook-metadata.json` preserves embedded clocks separately from HTTP retrieval/last-modified metadata. Embedded clocks, directory listing times and filename dates are not treated as authoritative release chronology.

`validation.json` records offline checks, synthetic live boundary examples and exact priority reconciliation. `asset-manifest.json` inventories calculation/evidence/report bytes and hashes, excluding itself and the changing validation-result file to avoid circular hashes. `__pycache__` is not a deliverable. Refreshing `collect.py` may change a source vintage; offline reproducibility uses the retained inputs.
