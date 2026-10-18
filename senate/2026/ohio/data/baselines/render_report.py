#!/usr/bin/env python3
"""Render the assigned Markdown report from saved CSVs; offline, no Git."""
import collections,csv,json,pathlib,re
P=pathlib.Path(__file__).resolve().parent
def read(n):return list(csv.DictReader((P/n).open()))
bs=read('../county-baselines.csv');by={k:{r['county']:r for r in bs if r['comparison']==k} for k in {r['comparison'] for r in bs}}
cs=read('candidate-universe.csv');states=read('state-scenarios.csv');targets=read('county-target-scenarios.csv');pr=json.loads((P/'priority-set.json').read_text());validation=json.loads((P/'validation.json').read_text())
def n(x):return f'{int(float(x)):,}'
def pp(x):return f'{float(x)*100:+.3f}'
def stats(k):
 rs=by[k].values();d=sum(int(r['d_votes']) for r in rs);r=sum(int(x['r_votes']) for x in by[k].values());o=sum(int(x['other_votes']) for x in by[k].values());return d,r,o
staterows=[]
for k in ['2024_senate','2022_senate','2024_president','2018_senate_original','2018_senate_amended']:
 d,r,o=stats(k);staterows.append(f'| {k} | {d:,} | {r:,} | {o:,} | {d+r+o:,} | {d+r:,} | {100*d/(d+r):.4f} | {100*(d-r)/(d+r):+.4f} |')
candidate_rows=[]
for k in ['2024_senate','2022_senate','2024_president','2018_senate_amended']:
 for r in cs:
  if r['comparison']!=k:continue
  label={'D':'Democratic','R':'Republican','L':'Libertarian','WI':'write-in; party not published','not_displayed':'party not displayed in canvass'}[r['party_source']]
  candidate_rows.append(f"| {k} | {r['candidate_name_normalized']} | {label} | {n(r['statewide_votes'])} |")
county_rows=[]
rank=read('priority-reconciliation.csv')
for row in rank:
 c=row['county'];r=by['2024_senate'][c];p=by['2024_president'][c];m=by['2022_senate'][c];q=[x for x in targets if x['scenario']=='2024_senate_own_observed' and x['target_two_party_margin']=='0.01' and x['county']==c][0]
 county_rows.append(f"| {row['rank']}{'*' if row['priority_top15_union_min80']=='1' else ''} | {c} ({r['county_fips']}) | {float(r['d_share_two_party'])*100:.2f} | {pp(r['d_minus_r_margin_two_party'])} | {pp(p['d_minus_r_margin_two_party'])} | {pp(m['d_minus_r_margin_two_party'])} | {float(r['statewide_major_party_weight'])*100:.3f} | {int(r['net_d_minus_r_votes']):+,} | {float(q['target_d_share_two_party'])*100:.3f} |")
sensitivity=[]
for s in states:
 if s['target_two_party_margin']!='0':continue
 if s['preference_comparison']!='2024_senate':continue
 sensitivity.append(f"| {s['turnout_mix_comparison']} | {n(s['scenario_major_party_votes'])} | {float(s['baseline_d_minus_r_net_votes']):+,.2f} | {float(s['uniform_d_share_shift_pp']):+.6f} | {float(s['uniform_d_share_shift_pp'])+.5:+.6f} |")
report=f'''# Ohio county partisanship and conditional Senate targets

Research date: **2026-10-17 America/Chicago**; downloads extend into **2026-10-18 UTC**. Ohio’s 2026 race is a **special U.S. Senate election**, November 3, to fill the term ending January 3, 2029. The [official special-election directive](https://www.ohiosos.gov/assets/directive-2025-54-writ-of-special-election-for-united-states-senate-election.pdf), checked during this research, establishes that context. **2022 Ryan–Vance is the recent midterm and same-seat comparison; 2024 Brown–Moreno is the most recent Senate comparison, for the other seat. Ohio held no 2020 Senate election.** Historical candidates do not establish a current coalition or a 2026 forecast.

With **2024 Senate county major-party weights**, Brown’s 206,434-vote deficit requires a uniform **+1.873834 percentage-point Democratic two-party-share shift** to tie. An illustrative **D+1 two-party margin** requires **+2.373834 share points**, yielding **55,083.32 net D−R votes** at that observed volume. Every county’s uniform target is one sufficient joint scenario, not an individually necessary winning threshold.

## Evidence, status and independent totals

The [old 2024 archive](https://www.ohiosos.gov/elections/election-results-and-data/2024-official-election-results/) and [2022 archive](https://www.ohiosos.gov/elections/election-results-and-data/2022-official-election-results/) redirect to the new SOS portal in primary browsing. Direct requests here returned HTTP403 challenge/maintenance HTML. Those responses, status, URLs, UTC timestamps, redirect history and response hashes remain in [raw metadata](data/baselines/evidence-manifest.json). Native Chrome opened the replacement archive; its saved published JavaScript identifies the official `publicfiles.ohiosos.gov` index, but that direct endpoint also returned403. No invented API or live cadence is used.

The turnout worker recovered **original official canvass XLSX bytes through Internet Archive**. This assignment reads those originals without modifying or duplicating them: [2024 county summary](data/turnout/raw/2024-summary-archive.xlsx), [2024 precinct workbook](data/turnout/raw/2024-statewide-races-precint-level.xlsx), [2022 county summary](data/turnout/raw/2022-statewide-races-summary.xlsx), [2022 precinct workbook](data/turnout/raw/2022-statewide-races-by-precinct.xlsx). The misspelling `precint` is the real source filename. [Shared input manifest](data/baselines/shared-input-manifest.json) pins original/archive URLs, archive timestamps, retrieval UTC, HTTP200 headers, original headers and SHA-256 hashes. These are archived certified publications, not newly fetched current SOS archive revisions and not election-night returns. Original [2024 download](https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-race-summary.xlsx); successful [archived capture](https://web.archive.org/web/20241207004035if_/https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-race-summary.xlsx). Original [2022 download](https://www.ohiosos.gov/globalassets/elections/2022/gen/statewide-races-summary.xlsx); successful [archived capture](https://web.archive.org/web/20221229143511if_/https://www.ohiosos.gov/globalassets/elections/2022/gen/statewide-races-summary.xlsx).

All county/candidate cells match the separate contest sheet within each workbook. Independent downloads of the [House Clerk 2024 publication](https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf), [2022 publication](https://clerk.house.gov/member_info/electionInfo/2022/statistics2022.pdf) and [2018 publication](https://clerk.house.gov/member_info/electionInfo/2018/statistics2018.pdf) check every published Senate candidate and presidential party-group total. The House presidential table groups minor tickets; it independently checks their combined denominators, while the SOS canvass and ballot directives establish individual tickets. [Machine-readable independent reconciliation](data/baselines/house-reconciliation.csv) retains every comparison. The [2024 certification announcement](https://www.ohiosos.gov/office/media-center/categories/press-releases/2024-12-02) confirms certification on December2 and 5,851,387 ballots; the [2022 announcement](https://www.ohiosos.gov/office/media-center/categories/press-releases/2022-12-09) confirms December9 certification.

| Comparison / vintage | D | R | Other | All candidate votes | D+R | D share of D+R % | D−R two-party margin pp |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(staterows)}

“Other” retains every published minor-party and write-in count, including zero-vote candidate rows. Ballots, votes in the contest and D+R are separate denominators. The all-candidate Senate total is 146,767 below ballots in2024 and 68,026 below ballots in2022; president is83,599 below2024 ballots. Those residuals are **unclassified ballots-minus-counted-contest-votes**, not an inferred undervote or invalid-ballot count.

## Candidate universe and source labels

[candidate-universe.csv](data/baselines/candidate-universe.csv) preserves original labels/column coordinates and full statewide sums; [candidate-votes.csv](data/baselines/candidate-votes.csv) preserves **2,992 county/candidate rows across34 candidate-vintages**, covering five comparison vintages ×88 counties. Write-ins remain write-ins with unspecified party; they are not assigned to D or R.

The [2024 certified ballot directive](https://www.ohiosos.gov/assets/dir2024-23.pdf) independently lists the major Senate candidates and four valid Senate write-ins, and the original five presidential write-in tickets. [Directive2024-26](https://www.ohiosos.gov/assets/dir2024-26.pdf) adds four presidential write-in tickets, yielding nine. Source aliases are preserved: e.g. Jay J. Bowman/De D. Bowman versus canvass Jay Bowman/De D Bowman; Tariq Shabazz versus canvass Tariq K. Shabazz;2018 Jim Renacci versus House James B. Renacci. Duncan’s ballot designation is **Nonparty candidate** and Sonski’s **Other-party candidate**, despite neither having a party marker in the canvass. The House groups them together as No Party. Do not silently relabel either as a Democrat or a Green.

| Comparison | Candidate / presidential ticket | Published party or status | Counted votes |
|---|---|---|---:|
{chr(10).join(candidate_rows)}

The earlier2024 ballot sample includes **Jill Stein/Anita Rios**, while the certified canvass omits them. The [primary Warren BOE page](https://liveresults.boe.ohio.gov/ENR/warrenohenr/14/en/Index_14.html), checked in primary browsing, says the ticket withdrew and votes for it would not count, even though some displayed precinct rows retain marks. No such marks enter this certified denominator. This is a ballot-vintage exclusion, not an invented zero-vote valid candidacy. Robert F. Kennedy Jr./Nicole Shanahan appear in the [August qualification announcement](https://www.ohiosos.gov/office/media-center/categories/press-releases/2024-08-23), but are absent from the September revised certified ballot and final canvass; they likewise are not inserted as counted candidates. Exact rejected-mark totals were not established. Direct downloads of these current explanatory pages were blocked; [primary-web-observations.json](data/baselines/primary-web-observations.json) distinguishes primary browsing from saved HTTP evidence.

## Retained2018 amendment

This assignment independently recovered the [original2018 county canvass](data/baselines/raw/2018-statewidecounty.xlsx), [Miami-amended county canvass](data/baselines/raw/2018-statewidecounty-miami-recovered.xlsx) and [official archive index](data/baselines/raw/archive-2018-index.html.gz). The [archived primary index](https://web.archive.org/web/20250305100623if_/https://www.ohiosos.gov/elections/election-results-and-data/2018-official-elections-results/) explains that **6,282 early in-person absentee ballots in Miami had not been counted**, and the board certified amended results on **January22,2019**. The amendment changes only Miami in the relevant columns: Brown+2,585, Renacci+3,596, Faris+5; Senate total+6,186; total voters+6,282. Registration does not change. [2018-revisions.csv](data/baselines/2018-revisions.csv) preserves each difference. The earlier House2018 publication agrees exactly with the original vintage; its difference from the amended total is therefore explained and retained. The amended file supplies the additional volume anchor; it does not supersede2024/2022 as the recent baseline.

## Geography, coverage and priority reconciliation

[county-baselines.csv](data/county-baselines.csv) contains **440 rows**, all88 counties for each of2024 Senate,2024 president,2022 Senate,2018 original Senate and2018 amended Senate. [Census2020 national county codes](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt) provide FIPS and COUNTYNS, joined by exact county name after stripping the Census suffix. The SOS county source’s native key is **County Name**; it publishes no numeric county, election, contest or candidate ID in these workbooks. [source-schema.json](data/baselines/source-schema.json) records native contest text and workbook/worksheet/column/row coordinates; local comparison keys are explicitly derivatives.

[native-reporting-units.csv.gz](data/baselines/native-reporting-units.csv.gz) retains **8,878 precinct rows for2024** and **8,933 for2022**, with county/FIPS, native three-letter SOS Precinct Code, Precinct Name, source row, voter-registration and ballot denominators, and vintage. The2024 ballot directive independently defines those three-letter codes. **926 codes in2024 and936 in2022 recur across multiple counties**: code alone is unsafe as a key. Use election vintage + county FIPS + native code. Identical codes across years do not establish compatible boundaries. No cross-year precinct join or2026 map/reporting-unit approval is asserted;2018 precinct evidence was not acquired. County-level named/FIPS aggregation is compatible for these calculations; it is not a geometric boundary audit.

Both precinct workbooks explicitly say write-in detail is unavailable. Their write-in zero cells represent **omission**, not certified zero votes. Same-election non-write-in precinct sums match every county summary exactly; the separately retained summary supplies **640 Senate write-ins and2,771 presidential write-ins in2024, and1,739 Senate write-ins in2022**. No write-ins are allocated to precinct polygons. See [2,464 candidate/county precinct checks](data/baselines/precinct-county-checks.csv); all precinct registration and ballot sums also reconcile countywide.

The independently computed ranking agrees with turnout’s exact supplied order. Top15: **3,525,320 /5,704,620 =61.797631%**. Minimum80%: **32 counties,4,581,738 /5,704,620 =80.316270%**; first31 supply4,542,798 =79.633665%. Thus the union with top15 remains32. [priority-set.json](data/baselines/priority-set.json) and [all88 ranking](data/baselines/priority-reconciliation.csv) preserve the exact set and nonpriority remainder. In that set2024 Senate D−R is+231,974; the other56 counties contribute−438,408, producing the statewide−206,434. The priority set is a research allocation, not the entire statewide electorate. Final worker-to-worker CSV status: **{validation['turnout_reconciliation_status']}**. [Reconciliation summary with stable file hashes](data/baselines/turnout-worker-reconciliation.json) records **zero differences**: [1,936 county field comparisons](data/baselines/turnout-worker-reconciliation.csv), [all2,464 common candidate cells](data/baselines/turnout-worker-candidate-reconciliation.csv), all88 rank/FIPS/native county keys, every historical count and five comparison rank fields, priority flags, all17,811 native unit identities ([176 county/year checks](data/baselines/turnout-worker-unit-reconciliation.csv)), and the exact32-county priority order. Statewide sums are5,704,620 Senate2024;5,767,788 president2024;4,133,342 Senate2022 in both workers.

## County leaning, mixedness and contributions

The2024 Senate D counties are **Athens, Cuyahoga, Franklin, Hamilton, Lorain, Lucas, Montgomery and Summit**; the other80 voted R. Ryan won the same eight in2022; Harris won seven in2024. These labels describe the named election. “Mixed” means absolute two-party margin≤5pp: Delaware, Erie, Lake, Lorain, Mahoning and Wood. The next band>5–10pp contains Montgomery, Portage and Trumbull. Full machine data include each contest’s bands, all-vote margins, candidate counts, contributions and other shares. Brown’s two-party D share exceeded Harris’s in **all88 counties**, with statewide difference **3.782781 share points**; that observed candidate/contest difference is not a transferable2026 effect.

Table order uses2024 Senate **all-candidate vote volume**. An asterisk marks the32 priority counties. Signed margins are D−R, weight is county share of statewide2024 Senate **D+R**; net contribution is raw D−R. D+1 target is the uniform2024 Senate scenario. CSVs retain unrounded values and1pp-share net-vote effects.

| Rank | County (FIPS) | Senate D share % | Senate margin pp | President margin pp | 2022 Senate margin pp | Major-party weight % | Net D−R | D+1 target D share % |
|---|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(county_rows)}

## Share points, third candidates and conditional targets

For each county, `s=D/(D+R)` and scenario major-party volume `T_c`. With `M0=sum(T_c*(2*s_c-1))`, total `T=sum(T_c)`, the uniform tie shift is `-M0/(2*T)`; at observed weights this is `(R-D)/(2*(D+R))`. A target margin `m` uses `(m*T-M0)/(2*T)`. Set `m=.01` for D+1. One D-share point transfers1% ofT from R to D, changing the **D−R margin by2points** and net votes by`.02*T`. Fractional target votes are expected-value arithmetic; no integer ballot allocation is implied.

2024 Senate includes **196,288 other votes (3.440860% of all counted candidate votes)**, primarily195,648 for Libertarian Don Kissick. Two-party D+1 at fixed other votes equals only **0.965591 all-candidate margin points**. To demand a full1pp all-candidate margin at the same fixed third-candidate count instead requires+2.391651 D-share points and57,046.20 net votes. [third-candidate-denominators.csv](data/baselines/third-candidate-denominators.csv) makes that distinction explicit for every main comparison. Changes in third-candidate support, candidate identity or turnout composition require different assumptions; no conversion from ballots to major-party votes is assumed. A D−R tie is not a certified win, and a two-party target does not establish plurality against a potentially stronger third candidate.

The amended2018 Brown baseline already wins. At its own observed weights, its tie shift is **−3.407432 D-share points** and D+1 shift **−2.907432**. A positive improvement is unnecessary there. All historical uniform scenarios saved here remain within[0,1]; the calculator does not silently clip infeasible shares. For other inputs, a target outside[0,1] must be labeled infeasible and recomputed with bounded shares before use.

For one selected county, hold every other county at its explicit baseline D share (or supplied override), and solve:

`required_selected_share=(m*T - sum_other(T_j*(2*s_j-1)) + T_selected)/(2*T_selected)`.

At2024 Senate volume with all other counties at their Brown–Moreno shares, **Franklin alone needs85.457748% D share to tie, or90.270275% for statewide D+1**, versus67.421993% observed. These are conditional alternatives, not county-level necessary targets. [selected-county-targets.csv](data/baselines/selected-county-targets.csv) provides all88 counties for all24 scenario/target combinations, including below0% (`already_secured` under the other-county assumptions) and above100% (`impossible`) requirements. Exact0/100% are feasible boundary ties. Nonpositive selected turnout is rejected. No clipping hides impossible cases.

## Historical low/base/high volume and composition sensitivity

The labels **low=2022 Senate**, **base=2018 Miami-amended Senate**, **high=2024 Senate** are simply the ordered observed major-party volumes: **4,131,603 /4,416,067 /5,508,332**. Base is the middle observed volume, not a2026 central estimate. Corresponding historical ballots/total voters are4,201,368 /4,503,116 /5,851,387; all-candidate Senate votes are4,133,342 /4,417,084 /5,704,620. Each volume has a different candidate field and political environment. None is an invented special-election turnout projection.

The table keeps2024 Senate county D shares fixed and independently crosses three observed county weight patterns with the three observed statewide D+R volumes. Uniform statewide volume changes multiply net votes but leave the tie share shift unchanged. A1pp uniform D-share gain has82,632.06 /88,321.34 /110,166.64 net-vote effect at low/base/high volume. Geographic composition changes alter weighted leaning even at the same statewide volume: at high volume,2022 weights reduce the baseline deficit from206,434 to204,095.90; amended2018 weights reduce it to131,466.48. That is a composition experiment, not evidence that2026 will reproduce those weights.

| County turnout mix | Statewide D+R volume | Baseline D−R net | Tie D-share shift pp | D+1 D-share shift pp |
|---|---:|---:|---:|---:|
{chr(10).join(sensitivity)}

The [12 scenario definitions](data/baselines/scenario-definitions.json) include the nine2024-share volume/composition combinations plus each other main comparison at its own observed volume and shares. [state-scenarios.csv](data/baselines/state-scenarios.csv) has24 tie/cushion rows; [county-target-scenarios.csv](data/baselines/county-target-scenarios.csv) has2,112 county contribution/weight/target rows. All88 counties enter every statewide sum.

## Reproduction, validation and substantive gaps

From the repository root:

```sh
python3 senate/2026/ohio/data/baselines/calculate.py
python3 senate/2026/ohio/data/baselines/validate.py --require-turnout
python3 senate/2026/ohio/data/baselines/render_report.py
python3 senate/2026/ohio/data/baselines/finalize.py
python3 senate/2026/ohio/data/baselines/calculate.py --selected-county Franklin --target-margin .01
```

The calculator also accepts `--comparison`, `--turnout-mix`, `--total-major-votes`, and `--hold-shares-json PATH` (county→fractional D-share overrides; unlisted counties remain at their observed shares). `fetch.py NAME URL` retains exact decoded responses plus headers/status, retrieval UTC and stored/decoded hashes for new evidence; an HTTP200 alone is not proof of usable election data. All downloads above are stored originals or explicitly labeled failed responses.

The independent audit reads raw Excel XML through a separate DOM implementation, checks2,992 source cells and labels against the exports, independent House identities/totals, all440 FIPS/denominator balances, same-election precinct sums and declared write-in omissions, all county weights, minimum80%, Miami revisions, uniform and conditional target arithmetic, physically impossible/already-secured cases, and a zero-denominator rejection. Current core/final check result: **{validation['status']}**, {validation['checks_passed']:,} checks. [validation.json](data/baselines/validation.json) states scope; [SHA256SUMS](data/baselines/SHA256SUMS) pins retained assets. These checks establish deterministic historical/scenario readiness, not calibration of live probabilities.

Substantive limits: current SOS historical endpoints are blocked for direct fetching; archived originals may precede a later unobserved revision. Known2018 revision is retained explicitly; no unexplained county-total discrepancy was found in the selected2024/2022 captures. Precinct-level write-in distribution remains unavailable; finer-unit partial returns therefore cannot automatically be compared with complete county shares. No validated cross-year/November2026 precinct crosswalk, approved current map, voting-method-specific partisan baseline, exact outstanding-vote estimate, live collection cadence, current candidate coalition, calibrated probability or live Needle is supplied. The coordinator’s MOCK/test/primary source warnings remain applicable; none of those products supplies the historical certified counts here.
'''
# Keep dates readable without changing source-native strings in CSVs.
report=report.replace('all88','all 88').replace('all440','all 440').replace('every88','every 88')
# Readable prose spacing, while preserving URLs and literal calculator/source keys.
parts=re.split(r'(\[[^\]]*\]\([^)]*\)|```[\s\S]*?```|`[^`]*`)',report)
for i,part in enumerate(parts):
 if part.startswith('[') or part.startswith('`'):continue
 part=re.sub(r'(?<=[A-Za-z])(?=[0-9])',' ',part)
 part=re.sub(r'(?<=[0-9])(?=[A-Za-z])',' ',part)
 part=re.sub(r',(?=20[0-9]{2}\b)',', ',part)
 part=re.sub(r'(?<=[,;])(?=[A-Za-z])',' ',part)
 parts[i]=part
report=''.join(parts)
(P.parent.parent/'county-partisanship.md').write_text(report)
print('Wrote',P.parent.parent/'county-partisanship.md',len(report.encode()),'bytes')
