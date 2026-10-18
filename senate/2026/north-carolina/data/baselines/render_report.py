#!/usr/bin/env python3
"""Regenerate the assigned report from archived, reconciled county data."""
import collections,csv,json,pathlib
from calculate import load,scenario,conditional,levels
BASE=pathlib.Path(__file__).resolve().parent

def read(name):
 with (BASE/name).open() as f:return list(csv.DictReader(f))
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']+['---:']*(len(headers)-1))+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])
def main():
 data=load();lv=levels(data);srcs=json.loads((BASE/'manifest.json').read_text())['sources'];src={s['file']:s for s in srcs};states=read('state-scenarios.csv');candidates=read('candidate-reconciliation.csv');ass=read('sensitivity-assumptions.csv')
 native={y:next(r for r in states if r['preference_baseline_year']==str(y) and r['turnout_level']=='native_historical' and r['target']=='tie') for y in data}
 mains={y:next(r for r in states if r['preference_baseline_year']=='2022' and r['turnout_weight_year']==str(y) and r['turnout_level']=='base_2022_senate' and r['target']=='tie') for y in [2022,2024]}
 totals={}
 for y,rs in data.items():
  totals[y]={k:sum(int(r[k]) for r in rs.values()) for k in ['dem_votes','rep_votes','other_votes','contest_votes','major_party_votes','net_d_minus_r']}
 sameD=[r['county'] for f,r in data[2022].items() if all(data[y][f]['winner']=='D' for y in data)]
 sameR=[r['county'] for f,r in data[2022].items() if all(data[y][f]['winner']=='R' for y in data)]
 mixed=[r['county'] for f,r in data[2022].items() if len({data[y][f]['winner'] for y in data})>1]
 summary=table(['Election / candidates','D','R','Other','Contest votes','D+R','D share %','D−R margin pp','D counties'],[[f'{y} '+('president' if y==2024 else 'Senate'),f"{totals[y]['dem_votes']:,}",f"{totals[y]['rep_votes']:,}",f"{totals[y]['other_votes']:,}",f"{totals[y]['contest_votes']:,}",f"{totals[y]['major_party_votes']:,}",f"{100*totals[y]['dem_votes']/totals[y]['major_party_votes']:.6f}",f"{100*totals[y]['net_d_minus_r']/totals[y]['major_party_votes']:+.6f}",sum(r['winner']=='D' for r in data[y].values())] for y in [2022,2024,2020]])
 candidate_table=table(['Election','Candidate / published party','Certified county sum','Certified statewide','Difference'],[[r['year'],r['candidate']+' / '+(r['party'] or 'blank'),f"{int(r['certified_county_sum']):,}",f"{int(r['certified_statewide_total']):,}",r['county_minus_state']] for r in candidates])
 sensitivity_table=table(['Level / historical volume anchor','Expected D+R votes','Scale vs 2022 Senate'],[[r['level'],f"{int(r['expected_state_major_party_votes']):,}",f"{float(r['scale_relative_to_2022_senate']):.6f}"] for r in ass])
 primary_table=[]
 for mix in [2022,2024]:
  for label,total in lv.items():
   row=next(r for r in states if r['preference_baseline_year']=='2022' and r['turnout_weight_year']==str(mix) and r['turnout_level']==label and r['target']=='tie')
   shift=float(row['required_dem_share_shift_pp'])
   primary_table.append([f'{mix} mix / '+label.split('_')[0],f'{total:,.0f}',f"{float(row['baseline_net_d_minus_r']):+,.2f}",f"{float(row['baseline_d_minus_r_margin_pp']):+.6f}",f'{shift:+.6f}',f'{shift+.5:+.6f}',f'{total*.01:,.2f}'])
 primary_table=table(['County mix / volume','D+R votes','Unshifted D−R net','Unshifted margin pp','Tie D-share shift pp','D+1 D-share shift pp','D+1 target net'],primary_table)
 alt_table=table(['Preference baseline','Mix weights','Unshifted margin pp','Tie share shift pp','D+1 share shift pp'],[[('2024 president' if y==2024 else '2020 Senate'),mix,f"{float(r['baseline_d_minus_r_margin_pp']):+.6f}",f"{float(r['required_dem_share_shift_pp']):+.6f}",f"{float(r['required_dem_share_shift_pp'])+.5:+.6f}"] for y in [2020,2024] for mix in [2022,2024] for r in states if r['preference_baseline_year']==str(y) and r['turnout_weight_year']==str(mix) and r['turnout_level']=='base_2022_senate' and r['target']=='tie'])
 rows=[]
 for f,b in sorted(data[2022].items(),key=lambda item:-int(item[1]['major_party_votes'])):
  s=int(b['dem_votes'])/int(b['major_party_votes']);delta=float(mains[2022]['required_dem_share_shift_pp'])/100
  rows.append([b['county'],f,f"{100*float(b['d_minus_r_two_party_margin']):+.2f}",f"{100*float(data[2024][f]['d_minus_r_two_party_margin']):+.2f}",f"{100*float(data[2020][f]['d_minus_r_two_party_margin']):+.2f}",f"{100*float(b['major_party_turnout_weight']):.3f}",f"{int(b['net_d_minus_r']):+,}",f"{.02*int(b['major_party_votes']):,.2f}",f"{100*(s+delta):.3f}",f"{100*(s+delta+.005):.3f}"])
 county_table=table(['County','FIPS','2022 Sen margin pp','2024 Pres margin pp','2020 Sen margin pp','2022 D+R weight %','2022 net D−R','+1pp D-share net gain','Tie D share %','D+1 D share %'],rows)
 examples=[]
 for county,mix,g,shift in [('Wake',2022,0,0),('Wake',2024,0,0),('Mecklenburg',2024,.01,0),('Tyrrell',2022,0,0),('Tyrrell',2022,0,.02)]:
  f=next(f for f,r in data[2022].items() if r['county']==county);rs,M=scenario(data,2022,mix,lv['base_2022_senate']);r=conditional(rs,f,g,shift);r.update({'county':county,'county_fips':f,'mix_year':mix,'other_share_shift_pp':100*shift,'baseline_year':2022});examples.append(r)
 (BASE/'conditional-examples.json').write_text(json.dumps(examples,indent=2)+'\n')
 example_table=table(['Selected county','Mix','Other D-share shift pp','State target margin pp','Required county D share %','Status'],[[r['county'],r['mix_year'],f"{r['other_share_shift_pp']:+.2f}",f"{r['target_margin_pp']:+.1f}",f"{r['required_dem_share_pct']:.6f}",r['status']] for r in examples])
 source_rows=[]
 for y in [2022,2024,2020]:
  a=src[f'{y}-certified-contest.pdf'];b=src[f'{y}-certified-county.pdf'];z=src[f'{y}-results.zip']
  source_rows.append([y,f"[state]({a['url']}) / [counties]({b['url']}) / [Election Results ZIP]({z['url']})",a['retrieved_at_utc'],b['retrieved_at_utc']])
 source_table=table(['Year','Direct primary sources','State PDF retrieval UTC','County PDF retrieval UTC'],source_rows)
 text=f'''# North Carolina county partisanship and conditional targets

Research completed **2026-10-17 America/Chicago**; primary data retrieved **2026-10-18 UTC** (full timestamps below). This is a historical research package and deterministic scenario calculator. No live forecast or calibrated win probability is implemented.

With **2022 Senate preferences and 2022 major-party county turnout**, Beasley trails Budd by **121,737 votes**. The uniform shift for a tie is **+1.649627 percentage points of Democratic two-party share**; an illustrative **D+1 two-party margin** requires **+2.149627 D-share points**. Holding those preferences fixed but using **2024 presidential county turnout weights**, scaled to the same 3,689,835 major-party votes, raises the tie shift to **+1.967094 D-share points** and D+1 shift to **+2.467094**. These are alternative statewide combinations, not individual county requirements.

## Election identity, denominators and provenance

The primary preference baseline is **November 8, 2022 U.S. Senate**, Cheri Beasley (DEM) versus Ted Budd (REP), contest group **1378**: the most recent North Carolina Senate election and a midterm baseline. **November 5, 2024 president**, Kamala D. Harris (DEM) versus Donald J. Trump (REP), group **1393**, is a separate comparison and turnout-composition proxy. **November 3, 2020 U.S. Senate**, Cal Cunningham (DEM) versus Thom Tillis (REP), group **1374**, supplies previous-election context for the 2026 Class II seat. Budd's seat is Class III; see the primary [Senate Class II](https://www.senate.gov/senators/Class_II.htm) and [Class III](https://www.senate.gov/senators/Class_III.htm) rosters, saved with retrieval metadata. **There is no 2024 North Carolina Senate baseline here.** No contemporary candidate preference is inferred from these historical candidates.

Use the [NCSBE historical results archive](https://www.ncsbe.gov/results-data/election-results/historical-election-results-data), retrieved {src['ncsbe-historical-index.html']['retrieved_at_utc']}. Its Election Results ZIP files preserve voting-method reporting units; its separate **Precinct Sorted** files contain statistical noise and explicitly are not official counts. No Precinct Sorted file enters this package. The archive labels the downloaded statements as certified; PDF dates are **2022-11-29**, **2024-11-26**, and **2020-11-24**. The 2022 URLs retain the directory name `Canvass - Unofficial Abstracts`; status is attributed to the archive's certified-results section, not guessed from the URL. The 2024 county PDF contains the signed composite authentication page. HTTP Last-Modified times are file metadata, not a revision history or a certification date.

{source_table}

Original ZIP and PDF bytes, archive HTML, the [NCSBE field layout](https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/layout_results_pct.txt), source headers, retrieval times, file sizes and SHA-256 hashes are in [manifest.json](data/baselines/manifest.json). [Census county codes](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt), retrieved {src['census-national-county2020.txt']['retrieved_at_utc']}, provide all 100 five-digit FIPS through an exact county-name join. County totals combine geographic and administrative early/absentee reporting units; an administrative unit may lack a polygon. This calculation makes no precinct-boundary or 2026 reporting-unit claim.

**Certified county PDFs are the selected source for all three baselines.** Each candidate's county sum, and each of the four voting-method sums, matches its independent certified statewide statement exactly. The ZIPs separately validate county allocation for 2020 and 2022. In 2024 there are four differing county/candidate entries, detailed below; the selected county PDF also sums to every certified statewide candidate total exactly. [county-candidates.csv](data/baselines/county-candidates.csv) retains 1,685 published county/candidate rows, party codes, total/method counts, PDF pages, URLs and retrieval timestamps. Some zero write-in entries are omitted in the PDFs; these remain omitted, rather than invented as source rows. Blank source party stays blank. No independent or minor-party candidate is relabeled Democratic.

All displayed totals are **votes in the named contest**, not ballots cast. Shares, scenario turnout and weights use **D+R votes** unless explicitly labeled all-vote. [county-baselines.csv](data/county-baselines.csv) has 300 rows (100 × 3 contests), D/R/other counts, candidate names, FIPS, other-candidate JSON, cross-election outcome patterns, both all-vote and two-party margins/weights, source status and timestamps. Ballots cast, undervotes, overvotes and registration are **unavailable in this extract and blank**, never zero or inferred. CSV shares are fractions; report shares are percentages and margins are percentage points.

## State totals and every-candidate reconciliation

{summary}

Every one of the **19** statewide candidate/category totals reconciles exactly:

{candidate_table}

Published party codes: DEM Democratic, REP Republican, LIB Libertarian, GRE Green, CST Constitution and JFA Justice for All. Blank identifies the published blank party for write-in categories, not an inferred affiliation. “Other” includes all these nonmajor categories: **84,089** in 2022 Senate (2.2282% of contest votes), **85,343** in 2024 president (1.4975%), and **239,389** in 2020 Senate (4.3724%). See [candidate-reconciliation.csv](data/baselines/candidate-reconciliation.csv), [certified-state-candidates.csv](data/baselines/certified-state-candidates.csv), and [county-reconciliation.csv](data/baselines/county-reconciliation.csv). A two-party margin uses a different denominator from a published all-vote margin; the CSV preserves both.

## Resolved source discrepancy, retained as evidence

The **2024 Election Results ZIP** has Harris **2,715,375**, Trump **2,898,423**, De la Cruz **528**, and miscellaneous write-ins **18,936**. The certified statements have **2,715,378**, **2,898,424**, **526**, and **18,938**. The other five candidates agree. ZIP total **5,699,141** is four below certified **5,699,145**. Exact differences are:

- **Mitchell (37121)**: ZIP Harris **1,915** vs certified **1,918**; ZIP Trump **6,843** vs certified **6,844**. See county PDF physical page **162**, printed page 161, and [saved preview](data/baselines/2024-mitchell-certified-preview.png).
- **Rowan (37159)**: ZIP De la Cruz **2** vs no De la Cruz entry in the certified complete presidential table; ZIP miscellaneous **156** vs certified **158**. The certified statewide De la Cruz sum confirms the zero contribution from Rowan. See physical page **211**, printed page 210, and [saved preview](data/baselines/2024-rowan-certified-preview.png).

The certified county source resolves baseline selection; **the cause and chronology of these differences remain unknown**. Neither download time nor Last-Modified proves why counts changed. All four differences remain in [zip-certified-differences.csv](data/baselines/zip-certified-differences.csv); no raw file is edited. The 2022 and 2020 ZIPs have **zero** differing candidate/county entries against their certified statements.

## Reconciliation with the completed turnout assignment

The independent [turnout package](turnout.md) and this partisanship baseline agree **exactly for all 100 counties** in **2024 president and 2022 Senate**. The saved [200-row comparison](data/baselines/turnout-reconciliation.csv) checks **800 D/R/other/contest-total cells with zero differences**. Independently parsed candidate extracts also agree on all **1,285 county/candidate rows and 6,425 total/voting-method cells**, plus **15 statewide candidate rows / 75 cells**; PDF page references match. The [reconciliation record](data/baselines/turnout-reconciliation.json) preserves both packages' retrieval timestamps, dependency hashes and all four certified PDF hashes: **the underlying 2022 and 2024 county/state PDF bytes are identical**, establishing the same source vintage rather than just matching totals.

Both assignments use certified 2024 **Harris 2,715,378 / Trump 2,898,424 / other 85,343 / all-choice total 5,699,145**. Both retain the Mitchell and Rowan ZIP differences described above, without substituting those ZIP counts. Independently ranking our certified 2024 all-choice county totals reproduces the turnout assignment's **38-county 80% set**, **4,576,486 / 5,699,145 = 80.30127326%**, with exactly the same county FIPS. Scenario weights use **D+R**, while that research priority uses **all contest choices**; these denominators intentionally differ. Turnout files were read only. That package separately supplies ballot and registration counts; the blank fields in this baseline refer to their absence from its selected contest-PDF extract, not absence from every official source.

## Historical county outcomes and mixed results

The 2022 Senate Democrat won **21** counties and Republican **79**. All 21 Democratic counties also voted Democratic in the other two comparisons: {', '.join(sameD)}. **{len(sameR)} counties** voted Republican in all three comparisons. The **{len(mixed)} mixed-winner counties** are **{', '.join(mixed)}**: all three voted Democratic in 2020 Senate; Wilson also voted Democratic for 2024 president; all three voted Republican in 2022 Senate. These are historical outcomes across different candidates and offices, not permanent labels or voter-transition estimates.

The CSV additionally marks absolute two-party margin bands **≤5 pp**, **>5–10 pp**, and **>10 pp** independently by election. Marginal counties matter through their volume as well as closeness. The all-county table below is sorted by 2022 Senate major-party volume. Positive margins mean D leads; negative mean R leads. The two target-share columns use only **2022 Senate preferences / 2022 weights / base volume**, and illustrate a uniform statewide combination. A county need not meet its listed target if gains elsewhere offset it. Full expected turnout, target margins, changes and county net contributions for every combination are in the scenario CSV.

{county_table}

## Share shift, margin shift and net votes

For county c, `s_c = D_c/(D_c+R_c)`, scenario major-party votes `T_c`, statewide `T=ΣT_c`, and unshifted net `M0=ΣT_c(2s_c−1)`:

```text
delta_share_for_tie = -M0/(2*T)
# Native historical weights give (R-D)/(2*(D+R)).
delta_share_for_target_margin_g = (g*T-M0)/(2*T)
county_target_share = s_c + delta_share
county_target_margin = 2*county_target_share - 1
county_target_net = T_c*county_target_margin
plus_1pp_D_share_net_gain = 0.02*T_c
```

A **+1 pp D-share** shift transfers share from R to D at fixed D+R turnout, so it yields **+2 pp D-minus-R margin**, not +1 pp. An illustrative **D+1 margin** (`g=0.01`) therefore needs **another +0.5 pp D share** beyond a tie. At base volume it means **+36,898.35 expected net votes**, rather than a one-vote win. Fractional scenario votes are expectations, while historical counts stay integers. A uniform shift is feasible only if every county target stays in [0,1]; all 42 current scenarios pass that bound. The calculator rejects infeasible other-county shares instead of silently clipping them. Ties themselves are thresholds, not a Democratic win.

## Researched turnout sensitivity and composition

Three **observed historical volume anchors** supply researched low/base/high sensitivity assumptions. They are an empirical stress range, **not probability bounds or predicted 2026 participation**:

{sensitivity_table}

Low is November 4, 2014 Senate **Kay Hagan + Thom Tillis** D+R volume, from the NCSBE Election Results ZIP (group **1152**) and independently reconciled for **all seven candidate/write-in categories** to the [House Clerk 2014 statistics](https://clerk.house.gov/member_info/electionInfo/2014/114-statistics.pdf), published March 9, 2015, physical page 38 / printed page 36, downloaded {src['house-2014-statistics.pdf']['retrieved_at_utc']}. See [2014 extract](data/baselines/2014-senate-state-zip-extract.csv) and [seven exact checks](data/baselines/2014-anchor-reconciliation.csv). That ZIP contains one negative correction: **Cabarrus / ONESTOP / miscellaneous write-in −13**, retained in aggregation. Three uppercase write-in aliases are canonicalized only for the supplemental 2014 candidate sums; the source bytes remain intact. Base is 2022 Senate observed D+R; high is 2024 president observed D+R. High tests presidential-scale volume, while the old 2014 low carries population/registration-vintage differences. These anchors do not establish plausible confidence limits for 2026, and are not a constant-registration turnout-rate model.

For each level, the **2022-like county mix** is each county's 2022 Senate D+R / statewide 2022 Senate D+R; the **2024-like mix** uses 2024 presidential D+R / statewide presidential D+R. Multiply each weight by the stated statewide total to obtain scenario `T_c`. Thus volume and composition can change independently. No presidential preference is substituted into the primary Senate scenario. Uniformly scaling county volumes changes net-vote amounts, **not share thresholds**.

Hold **2022 Senate preferences** fixed:

{primary_table}

At base volume, the 2024 mix makes D's net **23,428.07 votes worse**, or **0.634936 margin points** more Republican, than the 2022 mix. This is a composition calculation, not evidence that any county changed preference. The full [42 statewide scenarios](data/baselines/state-scenarios.csv) and [4,200 county target rows](data/baselines/county-target-scenarios.csv) include three separate preference baselines × two mixes × three volume levels × tie/D+1, plus native historical weights for each baseline. No rounding is used in calculations.

Preference sensitivity, holding statewide volume at 3,689,835 and changing which historical shares are repeated:

{alt_table}

2020 Senate's native mix ties at **+0.913302 D-share pp**, and native 2024 president at **+1.630321**; each D+1 threshold is 0.5 share pp higher. The president rows remain presidential comparisons. Candidate appeal, incumbency, 2020's campaign environment, 2024 presidential coalitions, turnout and minor-party choice cannot be separated from these aggregate results. The historical other share is particularly larger in 2020 Senate; none of its 239,389 minor-party votes is allocated to a major party in these calculations. A different 2026 minor-party/candidate configuration needs a separate assumption before converting ballots or all-contest votes into D+R turnout. Uniform swing does not estimate persuasion, turnout composition within counties, migration, demographic behavior or individual ticket splitting.

## Selected-county conditional calculator

Holding the other counties at specified shares `q_j`, solve the selected county c:

```text
required_q_c = (T_c + g*T - Σ_other T_j*(2*q_j-1))/(2*T_c)
```

Requirements below 0% mean the target is **already secured even at 0% D share** in that county, under the fixed assumptions. Requirements above 100% are **impossible even at 100%**. A feasible value is a tie/target threshold, not a probability or an unconditional requirement. By default other counties stay at the chosen historical preference shares. `--others-share-shift-pp` shifts them uniformly; `--other-shares-json` accepts specific FIPS → fractional D shares for named other counties. Those overrides apply after the uniform shift and remain bounded. The selected county cannot also be fixed by an override.

All examples below use **2022 Senate preferences**, base 3,689,835 D+R volume and the stated mix:

{example_table}

For example, Wake's unchanged 2022 baseline is **63.631059% D share**; if it alone supplies all needed improvement, its required tie share is **77.396452%** with 2022 weights. This is far above the **65.280686%** all-county uniform tie target because all other counties were held unchanged. A +1 pp D-share gain in Wake is worth **8,843.70 net votes** at that county's 442,185 base major-party votes. Equivalent gains elsewhere offset an equal net loss in Wake. [conditional-examples.json](data/baselines/conditional-examples.json) retains the numerical examples.

```sh
# Offline rebuild from retained primary evidence; requires Python 3 and Poppler.
python3 senate/2026/north-carolina/data/baselines/build_baselines.py
python3 senate/2026/north-carolina/data/baselines/calculate.py
python3 senate/2026/north-carolina/data/baselines/reconcile_turnout.py
python3 senate/2026/north-carolina/data/baselines/render_report.py
python3 senate/2026/north-carolina/data/baselines/validate.py

# Conditional examples (stdout only; no file changes).
python3 senate/2026/north-carolina/data/baselines/calculate.py --county Wake
python3 senate/2026/north-carolina/data/baselines/calculate.py --county Mecklenburg --mix-year 2024 --target-margin-pp 1
python3 senate/2026/north-carolina/data/baselines/calculate.py --county Tyrrell --others-share-shift-pp 2
# Supply any positive total with --state-major-party-votes; select 2020 or
# 2024 preferences explicitly with --baseline-year (2024 stays president).
```

[collect.py](data/baselines/collect.py) re-downloads observed archive links and rewrites source snapshots/manifest only when intentionally invoked; later source revisions must be compared before replacing this evidence. Offline scripts do not require refetching. `reconcile_turnout.py` reads the completed turnout assignment for exact cross-checks and writes only this assignment's reconciliation files; `render_evidence.py` recreates the six saved PDF previews and their derivation metadata. All writes are within this assignment's paths. No Git command was run.

## Validation and remaining gaps

[extraction-checks.json](data/baselines/extraction-checks.json), [scenario-checks.json](data/baselines/scenario-checks.json) and [validation.json](data/baselines/validation.json) record the checks. They cover exact 100-county/FIPS coverage in every baseline, unique candidate/county records, all **19 candidate and four-method statewide reconciliations**, the **7-candidate 2014 anchor**, D/R/other balances, reported-method totals, zero duplicate selected ZIP rows, weights summing to one, **42** statewide tie/cushion reconciliations and conditional reconstruction. Cross-assignment checks confirm 800 county summary cells and 6,500 county/state candidate-method cells agree exactly with turnout. Boundary checks exercise already-secured, impossible and invalid-input cases. [artifact-manifest.json](data/baselines/artifact-manifest.json) records derived file hashes, parser/runtime provenance and validation time. Saved PNGs visually check the three statewide contest statements, the differing 2024 county tables and the 2014 anchor.

- The 2024 ZIP/certification **difference cause and revision chronology** are unestablished. The certified baseline is resolved and reconciled; the discrepant ZIP stays available for audit.
- These historical turnout anchors are **not a researched demographic or registration projection for 2026**. County-specific growth, method mix, ballot participation and minor-party assumptions need current evidence before live use.
- Candidate/coalition effects are not identified by aggregate county returns; 2020 and 2022 are different candidates and seats, and 2024 is a different office. No 2026 ballot, turnout distribution or win probability is inferred.
- Baseline county totals cannot identify which geographic or administrative units remain uncounted. Administrative absentee/early units may lack polygons. No 2026 precinct crosswalk, remaining-vote model, feed/cadence claim, live adapter, forecast or calibrated probability is delivered by this assignment.
'''
 (BASE.parent.parent/'county-partisanship.md').write_text(text)
 print('report written',len(text),'characters')
if __name__=='__main__':main()
