#!/usr/bin/env python3
"""Regenerate the partisanship report from reconciled outputs; no downloads."""
import collections,csv,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
BASE=list(csv.DictReader((ROOT.parent/'county-baselines.csv').open()))
G=collections.defaultdict(dict)
for r in BASE:G[int(r['election_year']),r['stage'],int(r['source_unit_id'])][r['candidate']]=int(r['votes'])
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
def f(v,d=0):return f'{v:,.{d}f}'
def mdunits(ns):return ', '.join(str(n) for n in ns)
FIRST={y:{n:G[y,'first_choices',n] for n in list(range(1,41))+[99]} for y in [2020,2022,2024]}
ST=list(csv.DictReader((ROOT/'state-target-scenarios.csv').open()))
CHECK=list(csv.DictReader((ROOT/'validation-checks.csv').open()))
VERIFY=json.loads((ROOT/'verification.json').read_text())
# Full candidate support ranking, including HD99 explicitly as nongeographic.
support=[];support_report=[]
for y,units in FIRST.items():
 for c in units[1]:
  ranks=sorted([(n,units[n][c]/sum(units[n].values())) for n in range(1,41)],key=lambda x:x[1],reverse=True)
  for rank,(n,share) in enumerate(ranks,1):support.append(dict(year=y,house_district=n,candidate=c,candidate_votes=units[n][c],contest_votes=sum(units[n].values()),all_candidate_share=share,geographic_share_rank=rank,unit_type='house_district'))
  support.append(dict(year=y,house_district=99,candidate=c,candidate_votes=units[99][c],contest_votes=sum(units[99].values()),all_candidate_share=units[99][c]/sum(units[99].values()),geographic_share_rank='',unit_type='nongeographic_administration'))
  if c!='Write-in':support_report.append([y,c,'; '.join(f'HD{n}: {100*s:.2f}%' for n,s in ranks[:3])])
with (ROOT/'candidate-support-rankings.csv').open('w',newline='') as out:
 w=csv.DictWriter(out,fieldnames=list(support[0]));w.writeheader();w.writerows(support)
rounds=list(csv.DictReader((ROOT/'rcv-statewide-round-checks.csv').open()));rd={(int(r['round']),r['category']):int(r['votes']) for r in rounds}
C,K,M,T='Chesbro, Patricia R.','Kelley, Buzz A.','Murkowski, Lisa','Tshibaka, Kelly C.'
rcvtable=table(['Stage','Chesbro (DEM)','Kelley (REP)','Murkowski (REP)','Tshibaka (REP)','Continuing / candidate votes','Blanks','Exhausted','Overvotes'],[[f'RCV {i}',*[f(rd[i,c]) for c in [C,K,M,T]],f(sum(rd[i,c] for c in [C,K,M,T])),f(rd[i,'Blanks']),f(rd[i,'Exhausted']),f(rd[i,'Overvotes'])] for i in [1,2,3]])
firstcounts=table(['Contest','Candidate: official statewide votes','All candidate votes','Ballots / contest times cast'],[
 ['2020 Senate','Gross 146,068; Howe 16,806; Sullivan 191,112; write-in 601','354,587','361,400 statewide ballots; 361,291 Senate times cast'],
 ['2022 Senate first choices','Chesbro 27,145; Kelley 7,557; Murkowski 113,495; Tshibaka 111,480; write-in 2,028','261,705','267,047'],
 ['2024 president','Harris/Walz 140,026; Kennedy/Shanahan 5,670; Oliver/Maat 3,040; Sonski/Onak 702; Stein/Ware 2,342; Terry/Broden 812; Trump/Vance 184,458; West/Abdullah 1,127','338,177','340,981']])
rows22=[]
for n in list(range(1,41))+[99]:
 d=FIRST[2022][n];total=sum(d.values());r=G[2022,'rcv_round_3',n];continuing=r[M]+r[T]
 rows22.append([f'HD{n}',*[f'{100*d[c]/total:.2f}' for c in [C,K,M,T]],f'{100*r[M]/continuing:.2f}',f(r[M]-r[T])])
t22=table(['2022 unit','Chesbro first %','Kelley first %','Murkowski first %','Tshibaka first %','Murkowski final continuing %','Final M−T votes, CVR scope'],rows22)
rows24=[]
for r in csv.DictReader((ROOT/'unit-target-scenarios.csv').open()):
 if r['scenario']=='2024_historical_actual' and r['target_statewide_margin_pp']=='1.0':rows24.append([f'HD{r["house_district"]}',f(int(r['opposition_votes'])),f(int(r['republican_votes'])),f(100*float(r['baseline_opposition_pair_share']),2),f(float(r['baseline_margin_pp']),2),f(int(r['baseline_net_votes'])),f(100*float(r['weight']),3),f(100*float(r['target_opposition_share']),3),f(float(r['net_gain_for_one_share_pp']),2)])
t24=table(['2024 unit','Harris','Trump','Harris pair %','H−T margin pp','Net H−T','Pair weight %','Illustrative H+1 target share %','Net value of +1 share pp'],rows24)
state_targets=[]
for y in [2020,2024]:
 r=next(r for r in ST if r['scenario']==f'{y}_historical_actual' and r['target_margin_pp']=='0');plus=next(r for r in ST if r['scenario']==f'{y}_historical_actual' and r['target_margin_pp']=='1.0')
 state_targets.append([y,f(float(r['expected_pair_votes'])),f(float(r['fixed_share_net_votes'])),f(float(r['fixed_share_margin_pp']),6),f(float(r['uniform_opposition_share_shift_pp']),6),f(float(plus['uniform_opposition_share_shift_pp']),6)])
state_target_table=table(['Historical named pair','Pair votes','Opposition−R votes','Margin pp','Tie: opposition share shift pp','Opposition+1: share shift pp'],state_targets)
turnoutrows=[]
for r in ST:
 if r['target_margin_pp']=='0' and not r['scenario'].endswith('historical_actual'):turnoutrows.append([r['baseline_year'],r['scenario'].split('_',1)[1].split('_statewide')[0],f(int(r['scenario_statewide_ballots'])),f(float(r['expected_pair_votes']),2),f(float(r['fixed_share_net_votes']),2),f(float(r['uniform_opposition_share_shift_pp']),6)])
turnout_table=table(['Preference/unit vintage','Volume case','Statewide ballot volume','Expected named-pair votes','Opposition−R net','Tie shift share pp'],turnoutrows)
rcvsc=list(csv.DictReader((ROOT/'rcv-state-scenarios.csv').open()));rcvsc_table=table(['Conditional transfer/preference assumption','Murkowski final','Tshibaka final','M−T net'],[[r['scenario'],f(float(r['murkowski_final']),1),f(float(r['tshibaka_final']),1),f(float(r['murkowski_minus_tshibaka']),1)] for r in rcvsc])
rcvt=list(csv.DictReader((ROOT/'rcv-native-turnout-scenarios.csv').open()));rcvt_table=table(['2022 CVR turnout composition','Expected CVR ballots','M−T net','Continuing-ballot margin pp'],[[r['scenario'],f(float(r['expected_cvr_ballots']),1),f(float(r['net_murkowski_minus_tshibaka']),1),f(float(r['margin_pp']),4)] for r in rcvt])
gaps=list(csv.DictReader((ROOT/'cvr-ballot-coverage-gaps.csv').open()));gap_table=table(['Native unit','Full ballots','CVR ballots','Absent from CVR','Missing first-choice candidate votes'],[[r['unit_name'],r['full_ballots'],r['cvr_ballots'],r['missing_ballots'],r['missing_candidate_votes']] for r in gaps])
report=f'''# Alaska native-area partisanship and conditional targets

Research date: **2026-10-17 America/Chicago**; original downloads and checks dated **2026-10-18 UTC** in the evidence manifest. These are historical counts and deterministic scenarios, not a 2026 forecast.

**The 2022 Senate final was Republican versus Republican: Lisa Murkowski 136,330, Kelly Tshibaka 117,534.** The complete first-choice baseline and the published RCV report have different scopes. Keep them separate. Alaska had **no 2024 U.S. Senate election**; 2024 below means president. The previous election for the seat contested in 2026 is **2020 Sullivan–Gross**, while 2022 Senate supplies recent midterm and RCV context for a different seat. See the official [2022 RCV report](https://elections.alaska.gov/results/22GENR/US%20SEN.pdf), [2024 results](https://www.elections.alaska.gov/election-results/e/?id=24genr), and [2020 archive](https://www.elections.alaska.gov/results/20GENR/).

## Coverage, units and evidence

[County-baselines CSV](data/county-baselines.csv) is a compatibility filename: **none of its units are fabricated borough/census-area counties**, and county FIPS are blank. Its 1,558 long-form rows contain 697 first-choice candidate cells plus 861 candidate/inactive-category RCV cells. Filter by `election_year`, `stage`, and `ballot_scope`; never sum different stages. Every election retains **40 native house districts plus HD99 federal overseas administration**. HD99 is nongeographic and remains in all statewide arithmetic.

The original [2024 precinct CSV](https://www.elections.alaska.gov/results/24GENR/ENRbyPrecinct.csv) has **523 units × 8 candidates**. The original [2022 first-choice export](https://elections.alaska.gov/results/22GENR/Results_per_Precinct_2022_11_30T14_17_52_To%20Excel.txt) has **522 units × 5 choices**. The [2020 text](https://www.elections.alaska.gov/results/20GENR/resultsbyprecinct.txt) has **580 native units** with all three named Senate candidates but omits every write-in. All **41 official 2020 district statements** were downloaded; their complete candidate totals restore the 601 write-ins. The [HD1 statement](https://www.elections.alaska.gov/results/20GENR/data/sovc/HD1p.pdf) illustrates the format. At the finer 580-unit level, 2020 write-in allocation is not reconstructed: the district baseline is complete, the text-only native detail is explicitly partial for write-ins.

District aggregation uses each source precinct's explicit district prefix and the separately labeled district absentee/early/question units. It is checked against published district totals, including HD99. **533 of 533 2022/2024 district-candidate cells agree with the turnout worker's independent extraction of all official district statements**; [verification.json](data/baselines/verification.json) records the input hash. For 2020 all three named candidates match text versus PDF in every district, and all four statewide sums match the official summary.

Preserve election-specific vintages: 2020 is before the 2022 redistricting; 2022 and 2024 are their respective election reporting units. A district number does not establish spatial equivalence across years. No 2020→2024, 2022→2024 or 2026 precinct crosswalk is implemented here. The 2024 turnout inventory additionally identifies the May 2023 Final Proclamation/April 2024 precinct vintage; these are historical reporting baselines, not a claim of November 2026 precinct approval. Native IDs, source labels and sequence numbers are retained in [native-first-choices.csv](data/baselines/native-first-choices.csv), original exports, and CVR manifests. In 2024 `Pct_Id` can be blank or reused: `Pct_seq_nbr` within contest 4 distinguishes administrative units. Never join on `Pct_Id` alone. Named administrative units can contain multiple voting methods; actual CSV method columns are authoritative.

Source status is explicit. The 2022 precinct text's internal heading says **Unofficial**, but every first-choice candidate and method total matches the **OFFICIAL RESULTS** statewide publication. The [2022 archive](https://www.elections.alaska.gov/election-results/e/?id=22genr) marks the election official and links its [State Review Board certificate](https://elections.alaska.gov/results/22GENR/2022_GEN_SRB_Certificate.pdf). The [2020 summary](https://www.elections.alaska.gov/results/20GENR/data/sovc/ElectionSummaryReportRPT24.pdf), [2022 summary](https://elections.alaska.gov/results/22GENR/ElectionSummaryReportRPT.pdf), and [2024 summary](https://www.elections.alaska.gov/results/24GENR/ElectionSummaryReport.pdf) explicitly identify official results. Do not infer a historical revision timeline from the download date.

The [manifest](data/baselines/manifest.json) retains direct URLs, UTC retrieval, response headers, SHA-256, HTTP status/effective URL and TLS verification metadata. System curl used default certificate verification. The old `index.php` aliases returned a WAF response; the directory URL worked. The attempted modern `id=20genr` route returned “No Entries Found” and is retained as rejected evidence. Original CVR bytes exceeded 40 MB, so they are retained in two lossless parts; [parts manifest](data/baselines/cvr2022-parts.json) verifies their individual and reassembled hashes. All individual files are below 40 MiB. PDF text extracts and visually checked page previews are derivatives.

## Full-state reconciliation and party identity

{firstcounts}

Every candidate difference is **zero** against the primary statewide publications in [statewide-candidate-checks.csv](data/baselines/statewide-candidate-checks.csv). The 2022 first-choice contest has **4,857 undervotes + 485 overvotes**: 261,705 + 4,857 + 485 = **267,047** ballots. The 2024 presidential candidate total plus source undervotes/overvotes is **340,981**. Contest votes, contest times cast, ballots, and registered voters are separate quantities; no RCV rounds are added as turnout.

**Al Gross is an independent/nonpartisan challenger**, not a Democratic candidate for this analysis. The official [2020 pamphlet](https://www.elections.alaska.gov/election/2020/General/OEPBooks/2020%20AK%20Region%20IV%20pamphlet_FINAL-web.pdf), printed page 14, identifies him as Nonpartisan. The results PDF/text nevertheless displays `DEM` beside Gross. Both facts are retained: `party_source=DEM`, `candidate_identity=Independent / Nonpartisan`; the conditional scenario is explicitly **Gross versus Sullivan**. Howe is Alaskan Independence (`AIP`), Sullivan Republican (`REP`). In 2022 Chesbro is `DEM`, and Kelley, Murkowski and Tshibaka are each `REP`. 2024 source labels are DEM, NOM, LIB, ASP, NOM, CON, REP and AUR in the displayed candidate order; `NOM` is kept as a source code and is not treated as a single transferable coalition.

## 2022 ranked choice: exact replay, different ballot scope

{rcvtable}

Each round sums to **266,797** after adding continuing candidates, blanks, exhaustion and overvotes. The final denominator is **253,864 continuing ballots**, not 267,047 election ballots or 261,705 published first choices. Murkowski's final continuing share is **53.701982%**, a **7.403964 pp M−T margin**, and an **18,796-vote lead**. RCV Round 1 differs from the literal first-choice publication because unresolved write-ins are excluded and eligible later rankings can advance past them or a permitted single skipped rank; the CVR scope also omits 250 ballots. It is not a second first-choice export.

The official [cast-vote record](https://elections.alaska.gov/results/22GENR/rcv/CVR_Export.zip) contains **266,797 unique sessions**, **528 precinct portions**, **517 parent reporting units**, and **484 current adjudicated/modified records**. [extract_cvr.py](data/baselines/extract_cvr.py) selects the current Original/Modified record and preserves source portion, parent precinct, candidate and counting-group IDs. It does not use the scanner's first-choice `IsVote` flag to discard later ranks. [calculate.py](data/baselines/calculate.py) handles unresolved write-ins, overvotes, repeated rankings and consecutive skipped ranks. Every candidate/inactive cell and every transfer destination reconciles exactly to the official three-round report.

The [current official rule explanation](https://www.elections.alaska.gov/election-information/) and the 2022 archive describe ranked choice, a single skipped rank, two consecutive skips, equal-rank overvotes and repeated candidates. Historical replay is validated against the actual 2022 report; the parser is not an approved 2026 tabulator. The [district-round table](data/baselines/rcv-district-rounds.csv) and [district-transfer table](data/baselines/rcv-district-transfers.csv) are **derived contributions to the statewide elimination order**, not separate district elections. Lower-level original rank-pattern counts remain in [the compressed pattern aggregate](data/baselines/cvr2022-senate-patterns.csv.gz).

The 250-ballot difference is fully localized against the official [HD37](https://www.elections.alaska.gov/results/22GENR/HD37.pdf) and [HD40](https://www.elections.alaska.gov/results/22GENR/HD40.pdf) statements:

{gap_table}

Five units are absent and Levelock is partial. These account for **237 first-choice candidate votes** (Chesbro 12, Kelley 7, Murkowski 169, Tshibaka 46, write-in 3) plus **13 undervotes**. All other native-unit scanner first choices match. All 250 are Election Day ballots by the official method totals; absentee, early and question ballot totals match the CVR exactly. The cause and missing ranks are not established by the retrieved files. Do not impute transfers or silently add first choices to final-round counts. The full first-choice baseline retains these ballots; the RCV table explicitly retains its narrower scope. [Per-unit candidate differences](data/baselines/cvr-coverage-gaps.csv) and [ballot differences](data/baselines/cvr-ballot-coverage-gaps.csv) are reproducible.

Kelley's **8,575** RCV Round 1 ballots transfer to Chesbro **901**, Murkowski **1,641**, Tshibaka **3,209**, exhaustion **2,806**, overvotes **18**. Chesbro's Round 2 pool is **29,134**, including the 901 Kelley transfers; it transfers to Murkowski **20,571**, Tshibaka **2,224**, exhaustion **6,301**, overvotes **38**. These are round-pool transfers, not a claim that every member originally ranked the eliminated candidate first.

## Which native areas supported the candidates?

Among geographic districts, Murkowski led **25 of 40** in literal 2022 first choices; Tshibaka led the other **15**. Chesbro and Kelley led none. In the CVR final contributions Murkowski led 26, including HD34, and Tshibaka 14. The complete table below retains all four candidates; write-ins remain in the first-share denominator and the CSV. HD99 remains separate administration.

{t22}

2024 Harris led HDs **2, 3, 4, 9, 12, 13, 14, 16, 17, 19, 20, 21, 22, 35, 38, 39**; Trump led the other 24 geographic districts. The strongest 2024 Republican net contributions included HD8 **−5,374**, HD26 **−5,130**, HD27 **−4,978**; Harris's HD4 contribution was **+3,470**. All signs are Harris−Trump. These labels describe this election, not permanent party identities.

On the **2020 boundaries**, Gross led HDs **4, 16, 17, 18, 19, 20, 21, 27, 33, 34, 35, 38, 39**; Sullivan led the other 27. Gross's HD33 net was **+4,389**, while Sullivan's HD8 and HD12 nets were respectively **−5,273** and **−5,053** in Gross−Sullivan notation. These numbers cannot be compared to identically numbered 2024 districts as geographic swing. [All 82 named-pair unit summaries](data/baselines/two-candidate-unit-summary.csv) preserve counts, shares, margins, weights and closeness bands (≤5, >5–10, >10 pair-margin points).

The following ranks each named candidate by **share of all contest candidate votes among the 40 geographic districts**. It shows where even minor candidates had relatively higher shares; it does not suggest they won those districts. HD99 is excluded from this geographic ranking and retained separately in [all candidate support rankings](data/baselines/candidate-support-rankings.csv).

{table(['Election vintage','Named candidate','Three highest district shares'],support_report)}

## Historical two-candidate targets, separate from RCV

Only two explicitly named conditional comparisons enter these targets: **2020 Gross–Sullivan** and **2024 Harris–Trump**. Other candidates and write-ins remain in the full baselines but are held outside the named-pair denominator. No Republican candidates are combined. The 2024 presidential threshold is contextual history, not a Senate threshold or an assumed 2026 coalition. Neither historical candidate is assumed to be on the 2026 ballot.

For unit i, `s_i = opposition/(opposition+Republican)`, expected pair votes `T_i`, statewide `T = ΣT_i`, and `M = ΣT_i(2s_i−1)`. A uniform opposition-share shift `δ = (g−M/T)/2` yields target margin `g`: g=0 is a tie; g=0.01 is an illustrative opposition+1 **margin point** cushion. Unit target net is `T_i[2(s_i+δ)−1]`. A **+1 share pp** transfer changes margin by **+2 margin pp**, adding **0.02 × T_i net votes**. An opposition+1 cushion requires only another **+0.5 share pp** beyond the tie shift. A mathematical tie does not elect anyone.

{state_target_table}

These positive changes follow from those specific losing historical baselines; they are not necessary gains in each unit. Net gains anywhere offset equal net losses elsewhere. Every target share is bounded in [0,1] for these uniform examples. The [656-row all-unit scenario table](data/baselines/unit-target-scenarios.csv) covers all 41 units, two targets, two historical comparisons, and four volume cases per comparison; [state targets](data/baselines/state-target-scenarios.csv) reconcile to zero or exactly 1% of expected pair votes before display rounding.

The following 2024 table supplies all-unit contributions and illustrative Harris+1 shares at **2024's own pair-vote weights**. Gross–Sullivan's corresponding table is in the same scenario CSV under 2020 vintages.

{t24}

## Historical turnout-volume sensitivity and selected-unit calculator

The low/base/high envelope uses **observed statewide ballots**: 2022 **267,047**, 2024 **340,981**, 2020 **361,400**. Each historical comparison keeps **its own within-year unit weights and named-pair participation rate**. For example, the 2024 named-pair total scales as `324484 × scenario_ballots / 340981`; the 2020 total scales as `337180 × scenario_ballots / 361400`. This varies statewide volume without assigning old district turnout to new district numbers. It is an observed historical volume envelope, **not researched 2026 turnout bounds**. Uniform scaling leaves the share threshold unchanged; a changed geographic composition can change it.

{turnout_table}

To hold all other units at specified shares and solve selected unit c for statewide target g, use `q_c = [T_c + gT − Σ_other T_j(2q_j−1)]/(2T_c)`. The CLI accepts an independent selected-unit turnout multiplier, the other units' uniform share change, and the target margin. It rejects out-of-range assumed shares for the others and labels a selected result above 100% impossible, below 0% already secured under those assumptions. All other units, including HD99, remain in the solve.

```sh
python3 senate/2026/alaska/data/baselines/calculate.py --year 2024 --unit 12 --others-share-shift-pp 6.8 --target-margin-pp 0
python3 senate/2026/alaska/data/baselines/calculate.py --year 2020 --unit 33 --selected-turnout-scale 0.9 --target-margin-pp 1
```

Example: 2024 HD12 had **8,228 Harris+Trump votes** and **50.668449% Harris pair share**. If every other unit improves Harris share by **6.8 pp** at historical turnout, HD12 needs **59.304716%** to tie statewide, or **79.022995%** for Harris+1 margin. Holding all other units at baseline, HD99 would need **5,827.390181%**, which is impossible. These are selected-unit conditional results, never standalone requirements or predictions. [Verification examples](data/baselines/verification.json) check the solved net arithmetic.

## Conditional RCV transfer, preference and turnout scenarios

All scenarios here explicitly retain **Murkowski versus Tshibaka, both Republicans**. Hold the observed Kelley transfers and Chesbro Round 2 pool fixed. Of the **22,795** Chesbro-pool transfers continuing to a finalist, the observed Murkowski share is **90.243474%**. With **6,339** of that pool inactive as observed, only **49.015135%** of its continuing transfers to Murkowski would tie, because she entered Round 2 with a 449-vote lead. This conditional threshold is not a Democratic-share target and cannot be transplanted to a different candidate set or elimination order.

{rcvsc_table}

The preference-switch rows move the stated number of initial Murkowski ballots to Tshibaka, holding every other preference/transfer fixed; they preserve the same eliminated candidates. The transfer rows change only the finalist destination split of the fixed continuing Chesbro pool. Fractional counts are scenario expectations.

A separate geographic turnout test reweights every **2022 CVR district's own complete rank profile**: final Tshibaka-leading districts +10% / Murkowski-leading districts −10%, then the reverse; HD99 stays fixed. These are deliberately arbitrary composition stresses, not 2026 estimates. The original five absent precincts and partial Levelock remain the documented coverage gap. The same first-round nonmajority, Kelley-first and Chesbro-second eliminations are validated in all three cases.

{rcvt_table}

[All 123 turnout-scenario unit contributions](data/baselines/rcv-native-turnout-contributions.csv) remain in arithmetic, with [state scenarios](data/baselines/rcv-native-turnout-scenarios.csv). This shows turnout composition, first preference and transfers as separate assumptions. A new candidate configuration or substantial change in elimination order requires a new ranked-ballot scenario; no D/R two-share formula is imposed on it.

## Reproduction, validation and substantive gaps

```sh
python3 senate/2026/alaska/data/baselines/extract_cvr.py
python3 senate/2026/alaska/data/baselines/calculate.py
python3 senate/2026/alaska/data/baselines/verify.py
python3 senate/2026/alaska/data/baselines/render_report.py
```

These run offline from retained original bytes and require Python 3 plus system `pdftotext`. `collect.py --refresh` re-downloads the successful manifest URLs with verified TLS and can intentionally obtain a newer publication; preserve the prior evidence package before refreshing. The CVR extraction reads and verifies the two archive parts in memory. Report tables regenerate from unrounded integers/expectations.

**{len(CHECK):,} calculation checks passed**, plus all raw evidence/response-header hashes, reassembled CVR hash, no file ≥40 MiB, 1,558 unique baseline keys, every 41-unit coverage set, and **533 independent turnout candidate/district comparisons**. Checks cover every statewide candidate, 2022 official method/candidate totals, 2024 method columns and ballots/under/over conservation, all RCV round/category and transfer cells, all source units, scenario weights, tie/+1 net sums, elimination order and selected-unit feasibility arithmetic. A discrepancy fails execution; zero is never substituted for a missing first-choice geography.

Remaining gaps are substantive: the published RCV record omits 250 ballots whose later ranks cannot be recovered here; complete 2020 write-ins are available at district rather than the text export's finer units; no validated cross-year or November 2026 unit crosswalk is supplied; no 2026 candidate/turnout/transfer model is researched or calibrated. This package makes no claim about current precinct approval, a tested live API, demonstrated publication cadence, or implemented/calibrated win probabilities.
'''
(ROOT.parent.parent/'county-partisanship.md').write_text(report)
print(f'wrote {len(report)} characters; {len(support)} support rows')
