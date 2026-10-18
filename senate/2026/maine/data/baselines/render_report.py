#!/usr/bin/env python3
"""Regenerate the owned Maine research report from frozen CSV outputs."""
import csv,json
from collections import Counter
from pathlib import Path
from build import ROOT,CONFIG

def read(name):return list(csv.DictReader((ROOT/name).open()))
def fmt(n,d=0):return f'{float(n):,.{d}f}'
def table(headers,rows):
    return '| '+' | '.join(headers)+' |\n| '+' | '.join('---' for _ in headers)+' |\n'+''.join('| '+' | '.join(str(v) for v in row)+' |\n' for row in rows)

def main():
    base=list(csv.DictReader((ROOT.parent/'county-baselines.csv').open()))
    state=read('state-scenarios.csv');controls=read('state-controls.csv');ranked=read('independent-priority-ranking.csv')
    sums={s:{r['category']:int(r['all_native_row_sum']) for r in controls if r['source_id']==s} for s in CONFIG}
    counts=[]
    descriptions={'senate-2020':'2020 Senate, same seat','governor-2022':'2022 governor, midterm','senate-2024':'2024 Senate, other seat','president-2024':'2024 president, statewide'}
    for source,cfg in CONFIG.items():
        s=sums[source];total=sum(s[c[0]] for c in cfg['candidates'].values());d=s[cfg['d']];r=s[cfg['r']]
        detail='; '.join(cid+' '+fmt(s[cid]) for cid,_,_ in cfg['candidates'].values() if cid not in [cfg['d'],cfg['r']])
        counts.append([descriptions[source],cfg['n'],fmt(d),fmt(r),detail,fmt(total),fmt(s['blank']),fmt(s['tbc'])])
    state_table=table(['Contest','Native rows','D','R','Other identities / published category','All candidate categories','BLANK','TBC'],counts)
    vintage=[]
    for r in read('source-vintage-state-controls.csv'):
        vintage.append([r['source_id'],r['category'],fmt(r['legislature_archive']),fmt(r['current_sos']),f"{int(r['sos_minus_clerk']):+d}"])
    vintage_table=table(['Contest','Category','Legislature archive = Clerk','Current corrected SOS','SOS minus archive'],vintage)
    pair_rows=[]
    for pair in ['gideon-collins','king-kouzounas','costello-kouzounas','cherry-kouzounas','harris-trump','mills-lepage']:
        a=next(x for x in state if x['pair']==pair and x['mix']=='native' and x['volume']=='native-observed' and x['target']=='tie')
        b=next(x for x in state if x['pair']==pair and x['mix']=='native' and x['volume']=='native-observed' and x['target']!='tie')
        pair_rows.append([pair,fmt(a['expected_pair_votes']),fmt(a['native_observed_a_share_pct'],6),fmt(a['fixed_preference_net']),fmt(a['unbounded_uniform_a_share_shift_pp'],6),fmt(a['bounded_common_shift_pp'],6),fmt(b['bounded_common_shift_pp'],6),a['unbounded_out_of_range_units']])
    pair_table=table(['Named pair, A first','Pair votes','A share %','A minus B net','Unbounded tie shift, share pp','Bounded tie common shift, pp','Bounded A+1 margin common shift, pp','Unbounded tie infeasible units'],pair_rows)
    index={r['native_key']:r for r in base if r['source_id']=='senate-2024'}
    showcase=ranked[:15]+[r for r in ranked if index[r['native_key']]['unit_name']=='STATE UOCAVA']
    contribution=[]
    for rank in showcase:
        r=index[rank['native_key']];t=int(r['contest_votes']);king=int(r['king_votes']);rep=int(r['kouzounas_votes']);d=int(r['costello_votes'])
        contribution.append([rank['rank'],r['unit_name'],fmt(t),fmt(100*king/t,2),fmt(100*d/t,2),fmt(king-rep),fmt(d-rep),fmt(.02*(king+rep),2)])
    contribution_table=table(['Volume rank','Native unit','All Senate candidates','King all-vote %','Costello all-vote %','King minus R net','D minus R net','Net gain from +1 pp King pair share'],contribution)
    mixes=[]
    for pair in ['gideon-collins','king-kouzounas','costello-kouzounas']:
        for mix in ['native','2022-section','2022-lexical']:
            r=next(x for x in state if x['pair']==pair and x['mix']==mix and x['volume']=='native-observed' and x['target']=='tie')
            mixes.append([pair,mix,fmt(r['fixed_preference_net'],2),fmt(r['fixed_preference_margin_pp'],6),fmt(r['bounded_common_shift_pp'],6)])
    mix_table=table(['Pair','Mix, fixed statewide pair volume','Fixed-share net','Fixed-share margin pp','Bounded tie shift, share pp'],mixes)
    classifications=[]
    for source in CONFIG:
        rr=[r for r in base if r['source_id']==source];c=Counter(r['d_r_historical_label'] for r in rr)
        classifications.append([source,c['D'],c['R'],c['tie']])
    class_table=table(['Contest','D ahead of R','R ahead of D','D-R tie, including zero'],classifications)
    report='''# Maine native-unit partisanship and conditional win targets

Research snapshot: **2026-10-17 America/Chicago**; downloads have **2026-10-18 UTC** timestamps in the [source manifest](data/baselines/manifest.json). These are historical baselines and deterministic scenarios. **No calibrated 2026 probability or forecast is claimed.**

The same-seat 2020 Senate baseline has **Gideon (D) 347,223 versus Collins (R) 417,645**, a 70,422-vote deficit. At its observed pair weights, the algebraic uniform tie benchmark is **+4.603539 D-share percentage points**; a **D+1 margin point** requires **+5.103539 share points** before enforcing unit bounds. The bounded all-unit solutions are +4.603545 and +5.103546 common share points. These describe one combination of performance and turnout, not a requirement that every town improve identically.

The 2024 Senate race was the **other seat**. **King IND 427,570** and **Cherry IND 20,193** remain distinct from **Costello D 88,875** and **Kouzounas R 284,434**. A King-versus-Republican calculation is separate from a Democratic-versus-Republican calculation. A two-name comparison that drops the actual majority winner cannot resolve a multicandidate Senate outcome.

## Primary sources and native geography

The current SOS [2024 archive](https://www3.maine.gov/sos/node/2479), [2022 archive](https://www3.maine.gov/sos/node/1956), and [2020 archive](https://www3.maine.gov/sos/elections-voting/election-results-data/election-results-2020) supply the independently downloaded original workbooks. Direct files are [2024 Senate corrected](https://www3.maine.gov/sos/sites/maine.gov.sos/files/inline-files/US%20Senator%20FINAL-Corrected%2020241205.xlsx), [2024 president corrected](https://www3.maine.gov/sos/sites/maine.gov.sos/files/inline-files/President%20and%20Vice%20President%20FINAL-Corrected%2020241205.xlsx), [2022 governor](https://www3.maine.gov/sos/sites/maine.gov.sos/files/inline-files/Governor.xlsx), and [2020 Senate](https://www3.maine.gov/sos/sites/maine.gov.sos/files/content/assets/ussenator1120.xlsx). The linked original `www.maine.gov` URLs and tested official `www3` alternatives are both retained; the alternate host is not a historical web capture. All selected requests succeeded, and original response bytes are retained losslessly as gzip.

The compatibility file [county-baselines.csv](data/county-baselines.csv) contains **2,052 disjoint source rows**, not a 16-county replacement table. Its separate universes are towns/cities, plantations, unorganized-area/composite labels and STATE UOCAVA. County and statewide footer totals are validation controls and are excluded from disjoint-unit arithmetic. Parent county FIPS maps the native code through the retained [Census county-code file](https://www2.census.gov/geo/docs/reference/codes/files/st23_me_cou.txt); all 16 mappings validate. STATE UOCAVA has no invented county, polygon or municipality ID. No ward/precinct IDs appear in these selected statewide workbooks; blank ID fields mean absent, not zero. A future ward or method result requires a separately verified crosswalk.

`source_row_id` includes source, sheet and Excel row and is unique. `native_unit_name` preserves exact source text, including trailing spaces in **Winterport** and **Madawaska Lake**; `unit_name` trims only display whitespace. The accepted key is `ME:SOS:<date>:<native CTY or STATE>:<percent-encoded trimmed exact MUNICIPALITY>`. The same date/key can recur across contests; use the unique source row ID for disjoint observations. It is not a permanent geographic identifier. Full [schema and methods](data/baselines/SCHEMA.md) explain the fields.

Two 2022 Cranberry Isles rows (**165 and 166**) both contain positive counts. Both survive, without guessed island/ward labels; together they have 115 candidate votes and 117 TBC. There are **510 raw 2022 rows / 509 distinct county-plus-label groups**. Row **190, T3 ND Twp**, carries native code **PEN** within the printed **HAN** section: Hunkler 0, LePage 3, Mills 1, BLANK 0, TBC 4. Both codes are retained. Section footer sums reconcile; aggregating the literal codes moves four votes between Hancock and Penobscot relative to the printed sections. No correction is silently imposed.

The 2024 Senate has **Wesley/Day Block Twp** combined; president has **Wesley** and **Day Block Twp** separately. Labels such as Senate **Medway/Molunkus Twp** and presidential **Medway/Twps** are not silently treated as identical. Year/contest differences remain visible. Lexical spelling matches are explicitly unverified comparisons, not boundary approval.

## Complete statewide controls

'''+state_table+'''
All named candidates and published Others categories sum exactly to the workbook's cached statewide controls; all disjoint rows satisfy candidate categories + BLANK = TBC. The [9,241 candidate cells](data/baselines/candidate-votes.csv), [26 state controls](data/baselines/state-controls.csv), and [416 section-control cells](data/baselines/county-section-checks.csv) preserve the calculation. Others is an aggregate of unspecified identities, not a party reassignment. BLANK is the source category; separate overvotes, undervotes and invalid write-ins cannot be recovered from it here. TBC is the workbook's ballot count, distinct from candidate votes, pair votes, registration and population.

The 2020 totals also agree with the [House Clerk 2020 publication](https://clerk.house.gov/member_info/electionInfo/2020/statistics2020.pdf), PDF page 34 / printed 32. The independently retained [2022 Legislature governor tabulation](https://lldc.mainelegislature.org/Open/Elections/Returns/2022/20221108/elec_20221108ad.pdf) has the same statewide controls. There was **no 2022 U.S. Senate election in Maine**; this comparator is governor, not Senate. These are final historical publications; this research does not claim to have obtained every municipality's signed original return.

## Why the 2024 House Clerk and current SOS disagree

The official [Maine Legislature directory](https://lldc.mainelegislature.org/Open/Elections/Returns/2024/20241105/) retains [Senate workbook b](https://lldc.mainelegislature.org/Open/Elections/Returns/2024/20241105/elec_20241105b.xlsx) and [presidential workbook a](https://lldc.mainelegislature.org/Open/Elections/Returns/2024/20241105/elec_20241105a.xlsx). Their statewide cached totals exactly match the [House Clerk 2024 publication](https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf), PDF page 31 / printed 29, published March 10, 2025. They differ from the current SOS corrected workbooks as follows:

'''+vintage_table+'''
Every numerical difference is localized to **Alfred, York County** plus the resulting York/state footers: **33 changed numeric cells** in total. Senate row **517** changes Cherry 69→40, Costello 219→203, King 746→985, Kouzounas 714→810, BLANK 328→38. Candidate votes increase 290. Presidential row **518** changes Harris 680→981, Oliver 31→13, Stein 23→17, Trump 891→1,031, West 39→8, Others 0→0, BLANK 412→26. Candidate votes increase 386. Alfred's TBC stays **2,076** in both contests. Native labels and all other disjoint reporting rows agree. The [cell differences](data/baselines/source-vintage-cell-differences.csv), [state comparison](data/baselines/source-vintage-state-controls.csv) and [chronology investigation](data/baselines/source-vintage-investigation.json) reproduce this finding. No counts were rescaled to match another source.

The signed [Maine December 9 presidential certificate](https://www.archives.gov/files/electoral-college/2024/ascertainment-maine.pdf) independently agrees with all five named corrected SOS presidential totals. It does not provide the workbook's Others/BLANK categories. The Legislature directory lists workbook a/b timestamps on December 9, timezone unspecified. Embedded modification clocks are December 9 13:04:33Z / 13:05:30Z for the retained president/Senate files, versus December 6 14:55:08Z / December 9 15:31:56Z for current SOS. The nonmonotonic presidential clocks show why these are not a reliable release timeline. `FINAL-Corrected 20241205` is a filename label, not proof of first publication on December 5. The [December 18 SOS final-results notice](https://legislature.maine.gov/uploads/visual_edit/s-20250108.pdf), printed page 28 of the January 8 Senate record, points to state tabulations without explaining Alfred's change.

**Resolved:** the complete numerical origin of the conflicting totals is Alfred's replacement row. **Unresolved:** the underlying correction mechanism, municipal amended-return evidence, exact release sequence and why the later Clerk publication used the retained-vintage figures. Alfred's current [elections page](https://www.alfredme.gov/departments/town_clerk/elections.php) links a scanned “Election Results” file; visual inspection identifies its first page as June 9, 2026 primary, so it is rejected as 2024 correction evidence. No causal conclusion follows from the row differences.

## Current ranked-choice rules and historical stages

Checked against the [SOS RCV page, updated October 6, 2026](https://www3.maine.gov/sos/elections-voting/upcoming/ranked-choice-voting-tabs), its linked [November 2026 Senate sample ballot](https://www3.maine.gov/sos/sites/maine.gov.sos/files/inline-files/Sample%201.pdf), and current [21-A §723-A](https://legislature.maine.gov/statutes/21-A/title21-Asec723-A.html), including 2025 amendments. The sample demonstrates Senate ranked choices; historical candidate identities in this report are not asserted to be the current ballot field.

For the statutory first-choice majority test, **more than 50% of all ballots cast for the office** is required, including first-choice blanks, overvotes and excluded-candidate ballots. This differs from candidate-vote share. Without that majority, count continuing ballots by highest continuing rank, remove last place while more than two candidates remain, and declare the higher total when at most two continue. Excluded candidates and exhaustion require separate treatment. Final continuing-ballot shares exclude exhausted ballots. The SOS glossary calls election-night tallies Round 0 and explains that Round 1 can promote a later choice past an initial blank. A final tie follows the statutory tie procedure; it is not a win in these calculators.

The 2024 archive places Senate and president under its non-central-RCV heading; only CD2 has separately published central rounds there. King 427,570 and Harris 435,652 each exceed half of 842,447 TBC. Collins 417,645 exceeds half of 828,305 TBC in 2020. These files are initial municipal tallies that were sufficient for the historical winners, **not fabricated elimination-round or transferred final totals**. The 2022 governor comparator is a plurality general election. Current rules are documented for 2026, not retroactively substituted for each historical rule vintage.

The [12 conditional transfer examples](data/baselines/conditional-rcv-examples.csv) and [28 allocation rows](data/baselines/conditional-transfer-allocations.csv) keep identities separate and conserve ballots. They assume a named final pair, all other listed candidates removed, and BLANK exhausted; an illustrative 60%/30%/10% transfer split is an **unobserved assumption**. They are labeled **unreachable from unchanged historical first choices**, because the majority winner stops the count first. They are stress arithmetic, not predictions or observed rounds. For 2020, even assigning all 54,315 non-pair candidate votes to Gideon leaves Collins ahead 16,107; adding all 9,122 BLANK to Gideon still leaves 6,985. King remains ahead 34,068 even if all Costello+Cherry votes go to Kouzounas, or 12,693 if every BLANK also goes there. A future multicandidate outcome needs the future field, elimination order, ranked-ballot evidence, exhaustion and uncertainty.

An [explicit coalition example](data/baselines/explicit-coalition-example.json) combines **King 427,570 + Costello 88,875 = 516,445** versus Kouzounas 284,434, with Cherry separate and assumed exhausted. That is a named coalition bookkeeping scenario, **not Democratic votes**, observed transfers or a 2026 forecast.

## Native-unit labels, contributions and pair targets

Historical D/R labels compare only the named D and R candidates. Closeness bands use absolute pair margin: ≤5 pp, >5–10 pp and >10 pp. Initial all-candidate leaders remain a separate column. In 2024 Senate, King leads alone in 286 rows, Kouzounas 220, Costello 1, and King/Kouzounas tie in 5; this is distinct from the D-R pair labels below.

'''+class_table+'''
For a conditional named final pair, let `T_u` be expected pair votes and `s_u` the baseline A share. `M = sum T_u*(2*s_u-1)`, `T = sum T_u`, and the algebraic uniform share shift for target fractional margin `g` is `delta=(g-M/T)/2`. A tie uses `g=0`; **A+1 margin point uses g=0.01**, not one vote. A +1 pp A-share gain adds **2 margin pp** and **0.02*T_u net votes** when turnout is fixed and the transfer comes from B. These are conditional pair denominators; other candidates and BLANK remain outside them.

'''+pair_table+'''
Negative shifts describe already-winning baselines. The literal uniform rule falls outside [0,1] in the displayed number of positive-weight units. Such a rule is marked infeasible. The delivered target rows also solve `q_u=clip(s_u+lambda,0,1)` with a common lambda chosen to hit the exact statewide tie or cushion; capped units receive a different actual share change. Sakom Twp has zero 2020 pair votes; T15 R6 WELS Twp has zero 2024 Costello-R pair votes. Their shares stay undefined and their weights zero. A positive blank candidate cell is never manufactured for them.

For the 2020 native base, D+1 margin means **7,648.68 expected net votes**, not one vote. Moving from an algebraic tie to that margin adds 0.5 aggregate share pp. An expected +1 net vote adds `100/(2*T)` share pp (0.0000653708 for T=764,868), but fixed integer pair totals obey parity: with that even T, the smallest integer winning lead is **two**. Scenario fractional votes are expectations; historical counts remain integers. Bounded common-lambda differences can differ slightly from 0.5 because of caps.

These selected 2024 units illustrate why net contribution and opportunity matter. All **512** units, including the **348** outside the priority set, enter the state arithmetic. This table uses the 2024 Senate's own native rows only:

'''+contribution_table+'''
The [independent full ranking](data/baselines/independent-priority-ranking.csv) reproduces top 15 **215,627 / 821,072** and minimum 80% **164 units / 658,029 votes**. The first 163 have 656,778; **Pownal 1,251** crosses. Its [ordered key bytes](data/baselines/priority-keys.txt) match the turnout worker exactly, SHA-256 `086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407`. All 512 ordered keys, four candidates, BLANK, TBC and source rows independently reconcile in [turnout-reconciliation.json](data/baselines/turnout-reconciliation.json). Priority is a research workload definition, not a subset used for statewide calculations.

## Turnout and preference sensitivity

The observed low-volume anchor is **676,819 all-candidate votes, 2022 governor**; the high-volume anchor is **831,375, corrected 2024 president**. The base is each named baseline's **native observed** volume, not a common 2024 total: 2020 Senate 819,183 contest / 764,868 D-R; 2024 Senate 821,072 contest / 712,004 King-R or 373,309 Costello-R. Each anchor is converted to pair volume by that baseline's fixed pair/contest participation ratio. For contextual governor/president pairs, native base coincides with one endpoint. These researched historical anchors are sensitivity settings, **not lower/upper 2026 turnout forecasts**, and do not estimate future third-candidate participation.

Three mixes keep each baseline's native preferences fixed:

1. **native:** observed unit pair weights.
2. **2022-section:** observed governor all-candidate shares across its 16 printed county sections plus STATE UOCAVA; allocate within each section in proportion to the baseline's native pair votes. This tests parent-section composition, keeps all native rows, and uses the explicitly retained printed section rather than silently fixing T3 ND Twp's code.
3. **2022-lexical:** compare county code + narrowly normalized source label (case, whitespace, apostrophe/period, Plantation/Plt, Township/Twp, St/Saint). This matches 469 of 517 2020 native rows, or 481 of 512 2024 Senate rows. Matched 2022 label volumes determine weights; the **24,614 / 14,860 unmatched 2022 candidate votes** are a collective residual allocated over unmatched baseline units proportionally to baseline pair votes. Two Cranberry rows remain disjoint, with any matched group volume distributed by baseline pair proportions. This is an explicitly assumed complete sensitivity, not a verified municipal geographic join or a claim about where the residual voters live.

The [label crosswalk and residual allocation](data/baselines/mix-label-crosswalk.csv) expose every weight. Exact spelling agreement cannot establish boundary continuity. Changes in method mix and native constituent coverage remain unknown. The printed-section proxy is coarser than the native topology; it never replaces the baseline table with counties.

'''+mix_table+'''
Scaling every unit together changes net-vote magnitudes and one-vote thresholds, but leaves shares and percentage-point tie thresholds unchanged. Changing composition can alter them. [State scenarios](data/baselines/state-scenarios.csv) cover all three researched volume anchors. [Preference sensitivity](data/baselines/preference-sensitivity.csv) separately recenters the 2020 unit shape to observed low **45.396461% Gideon-Collins**, base **53.544306% Harris-Trump**, and high **56.746829% Mills-LePage** statewide D-R shares using bounded shifts. These are explicitly different-contest preference anchors, not interchangeable Senate measurements or calibrated candidate effects. Full settings and candidate identities are in [scenario-settings.json](data/baselines/scenario-settings.json).

## Selected-unit calculator and live use

For selected unit c, hold other shares fixed and solve `q_c = [T_c + target_net - sum_other T_j*(2*q_j-1)]/(2*T_c)`. Below 0% is already secured under those assumptions; above 100% is impossible. Zero remaining pair votes is undefined, not a zero requirement. Other-unit share changes are bounded and clipping is reported.

With 2020 native pair weights and every other unit unchanged, **Portland would need 172.325125% D share to tie statewide**, so that single-unit condition is impossible. If every other positive-weight unit instead gains 4.5 D-share pp, bounded to [0,1], Portland needs **83.0710%**, versus its observed 76.413707%. A +1 pp Portland pair-share gain is worth **734.24 net votes**. This illustrates tradeoffs; no town has a standalone necessary winning target.

```sh
python3 senate/2026/maine/data/baselines/scenarios.py --pair gideon-collins --unit Portland --target-margin-pp 0
python3 senate/2026/maine/data/baselines/scenarios.py --pair gideon-collins --unit Portland --others-share-shift-pp 4.5 --target-margin-pp 0
python3 senate/2026/maine/data/baselines/scenarios.py --pair king-kouzounas --unit 'ME:SOS:2024-11-05:STATE:STATE%20UOCAVA' --target-margin-pp 1
```

All-unit target and selected-unit rows are supplied for [Gideon-Collins](data/baselines/gideon-collins-unit-targets.csv), [King-Kouzounas](data/baselines/king-kouzounas-unit-targets.csv), [Costello-Kouzounas](data/baselines/costello-kouzounas-unit-targets.csv), [Cherry-Kouzounas](data/baselines/cherry-kouzounas-unit-targets.csv), [Harris-Trump](data/baselines/harris-trump-unit-targets.csv), and [Mills-LePage](data/baselines/mills-lepage-unit-targets.csv). Each retains baseline counts, native row identity, assumed turnout/weight, preference, unconstrained feasibility, bounded target share/margin/net contribution, +1-share-pp net opportunity and the one-selected-unit solve. Main Senate pairs have three mixes; contextual pairs have native mix.

In live use, **counted votes stay fixed**. With counted A-minus-B lead L and remaining pair votes U, the aggregate tie threshold is `(U-L)/(2*U)`. Add a target net cushion to the numerator when requested. The selected-unit formula subtracts L as well as the other remaining units' expected net. The [synthetic fixture](data/baselines/live-calculator-example.csv) and [outputs](data/baselines/calculator-examples.json) verify counted A=100, B=120 stay fixed: with 200 pair votes remaining, aggregate tie requires 55% A; if the other 100 are 50% A, the selected 100 need 60%. A +1 final margin point uses the full 420-vote final pair denominator and requires 56.05% of the remainder.

```sh
python3 senate/2026/maine/data/baselines/scenarios.py --remaining senate/2026/maine/data/baselines/live-calculator-example.csv --counted-a 100 --counted-b 120 --target-margin-pp 0
```

This live pair calculator is conditional on the named finalists and a compatible round. It cannot infer remaining votes from “precincts reporting,” transfer a counted first-choice vote by a swing adjustment, or resolve unknown RCV eliminations. Official changes between rounds or corrected snapshots must retain stage, source and revision history. Forecast only remaining ballots within a specified model; do not multiply a statewide shift into already-counted totals.

## Reproduction, validation and limits

```sh
# Offline from retained primary bytes; collection is a separate refresh operation.
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/extract_evidence.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/build.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/vintages.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/scenarios.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/render_report.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/data/baselines/validate.py
```

`collect.py` records each URL, tested request/final URL, retrieval UTC, headers, redirects, HTTP status, original-byte length/SHA-256 and gzip length/SHA-256. Refreshing current URLs may obtain a new vintage; compare manifests before replacing evidence. `read_xlsx.py` is an independent standard-library OOXML reader preserving cached values, row coordinates and formula text; no spreadsheet values are recalculated or edited. `pdftotext -layout` creates the PDF text derivatives. The scanned 2018 rules PDF has no usable embedded text; the current statute and current SOS page establish the 2026 rule summary. Primary PDF pages and the sample ballot were rendered for visual checks.

The [validation result](data/baselines/validation.json) verifies source hashes, all native/candidate controls, BLANK/TBC balances, distinct row IDs, preserved anomalies, weights summing to one, **72 state scenarios / 36,948 native target rows**, exact tie and +1 margin sums, bounded shares, zero/impossible/secured selected-unit cases, immutable counted-vote arithmetic, transfer conservation, vintage controls, priority bytes, relative links and asset sizes. The [asset manifest](data/baselines/asset-manifest.json) records delivered evidence and calculation-file hashes. Every individual asset is below **40,000,000 bytes**. Coordinator and turnout independently reconciled source rows/candidate counts/priority keys; the coordinator also independently checked the target arithmetic. No Git operations were performed by this worker.

Remaining implementation gaps: establish the Alfred amendment's cause and release history; obtain/verify November 2026 native boundaries and method/ward crosswalks; resolve historical composite coverage before treating lexical matches as comparable electorate slices; obtain actual ranked-ballot/round evidence when needed; research 2026 participation, candidate and transfer assumptions; and calibrate a live probability model against genuine timestamped returns. The completed deliverable supports audited scenarios while those uncertainties stay visible.
'''
    (ROOT.parent.parent/'county-partisanship.md').write_text(report)
    print('Rendered county-partisanship.md from frozen baselines/scenarios')

if __name__=='__main__':main()
