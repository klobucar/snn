#!/usr/bin/env python3
"""Render the report from controlled county integers and explicit source gaps."""
import csv,gzip,json,collections,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.parent.parent

def run():
    c=list(csv.DictReader(open(S/'data/county-turnout.csv')));p=json.load(open(P/'priority-set.json'));p['acceptance_status']='County counts and exact34-key priority accepted by coordinator; finer layers source-scoped and not2026 geographic approval';units=list(csv.DictReader(gzip.open(P/'tlc-derived-vtd-units.csv.gz','rt')));vtd=[r for r in units if r['source_id']=='tlc-2024-senate-vtd']
    for g in p['groups']:g['derived_vtd_constituents']=[{'CNTYVTD':r['CNTYVTD'],'VTDKEY':r['VTDKEY'],'layer':'TLC historical derived VTD; not native precinct'} for r in vtd if r['county_fips']==g['county_fips']]
    (P/'priority-set.json').write_text(json.dumps(p,indent=2)+'\n')
    def pc(n):return f'{100*n/p["source_denominator"]:.8f}%'
    names=', '.join(r['county'] for r in c[:p['minimum80_count']]);cand=list(csv.DictReader(open(P/'county-candidates-2024.csv')))+list(csv.DictReader(open(P/'county-candidates-comparators.csv')))
    totals={}
    for contest in ['senate','president','governor_2022','senate_2020']:
        rows=[r for r in cand if r['contest']==contest];totals[contest]=collections.Counter()
        for r in rows:totals[contest][r['source_candidate_name']]+=int(r['votes'])
    def meta(name,base=P):return json.load(open(base/'raw'/(name+'.meta.json')))
    so=meta('sos2024-county-archive-20250422200023');st=meta('sos-2024-canvass-archive');b22=meta('sos2022-county-20241003',P.parent/'baselines');b20=meta('sos2020-county-20241003',P.parent/'baselines')
    report=f'''# Texas: where the statewide votes come from

Observed **October 17, 2026 Central / October 18 UTC**. Rank **all 254 counties by valid votes for every reported candidate in the November 5, 2024 U.S. Senate election**, including both named write-ins. This was **Class I, the other Senate seat**; the 2026 race is for Class II, the seat last elected in 2020. Counts measure contest volume, not population, registration or turnout rate.

The **top 15** supply **{p['top15_votes']:,} / {p['source_denominator']:,} = {pc(p['top15_votes'])}**. In descending order: {', '.join(r['county'] for r in c[:15])}.

The **minimum largest-first set reaching 80% is 34 counties**, with **{p['minimum80_votes']:,} / {p['source_denominator']:,} = {pc(p['minimum80_votes'])}**. The preceding 33 total **{p['preceding_set_votes']:,} = {pc(p['preceding_set_votes'])}**. **Midland, 58,182 votes, crosses the threshold**. The other 220 counties supply **{p['remainder_votes']:,} = {pc(p['remainder_votes'])}**. No set of 33 can reach 80%, because these are the 33 largest county totals; integer arithmetic checks `5*previous < 4*state <= 5*crossing_set`.

Exact accepted priority order: **{names}**. [Full county table](data/county-turnout.csv), [all 254 dispatch keys, constituents and remainder](data/turnout/priority-set.json), and [schema](data/turnout/SCHEMA.md). Keys are `TX:<five-digit county FIPS>`. The coordinator accepted the county counts and exact 34-key order after independent extraction; that acceptance does not approve finer reporting geography or 2026 boundaries.

## Actual primary originals and clocks

The current [SOS historical index](https://www.sos.state.tx.us/elections/historical/elections-results-archive.shtml) separates 2025-current, 2019-2024 and the older classic archive. Direct requests to the linked 2019-2024 app, its root, and the actual 2024/2022 canvass URLs returned HTTP 403. The classic HTTP-200 page stops at 2019; it does not supply these elections. These are bounded automated-access observations, not a claim about human-browser access.

The successful baseline is the **actual SOS county-by-county canvass**, not a VTD substitute: [2024 archived original]({so['requested_url']}) and [statewide canvass]({st['requested_url']}). A retained Wayback CDX response identifies the exact original report paths and captures. The three downloaded county captures, December 15, 2024 (two URLs) and April 22, 2025, agree in **every county and every Senate/presidential candidate**, with zero differences. Their full extraction is retained in [primary-county-extraction.json](data/turnout/primary-county-extraction.json). The selected April capture supplies all 254 native county labels, 1,270 Senate cells and 2,540 presidential cells.

**Printed clocks differ:** visual inspection of the actual county PDF page 1 confirms **`07/01/2025 10.42 AM`**; the statewide summary page 1 prints **`01/07/2025 10:42 AM`**. These literal formats are preserved separately from archive capture/Memento timestamps, original HTTP Last-Modified, response Date and retrieval UTC. No certification or release chronology is inferred from the ambiguous numeric dates. [County page image](data/turnout/raw/sos2024-county-page1.png), [state page image](data/turnout/raw/sos-2024-canvass-page1.png).

SOS native county labels `COLLINGSWOR` and `THROCKMORT` are preserved and explicitly mapped to Collingsworth 48087 and Throckmorton 48447. The PDF does not publish county codes; that column stays blank. FIPS mapping is sourced from the pinned MEDSL county file. All **1,270 county/candidate integers** in that independent derivative match the downloaded primary original exactly. This is stronger than a statewide-only reconciliation. MEDSL's individual-state precinct ZIP instead reproduces TLC VTD values and is not a native precinct return. The primary [House Clerk 2024 statistics](https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf), retained read-only in the Ohio package, also agree with every statewide Senate candidate.

## Candidate controls and comparators

Every table below sums all 254 county rows exactly to the separate original statewide canvass; D/R/other and all write-ins balance. Source status is the publisher's **official canvass** label, preserved through the archive. Archive retrieval is not evidence that the source is the newest possible correction.

| Contest | Democrat | Republican | Other valid candidates | All candidate votes |
| --- | ---: | ---: | ---: | ---: |
'''
    specs=[('2024 Senate, Class I','senate_2024'),('2024 President','president_2024'),('2022 Governor, actual midterm','governor_2022'),('2020 Senate, Class II/same seat','senate_2020')]
    for label,prefix in specs:report+=f"| {label} | {sum(int(r[prefix+'_d']) for r in c):,} | {sum(int(r[prefix+'_r']) for r in c):,} | {sum(int(r[prefix+'_other']) for r in c):,} | {sum(int(r[prefix+'_total']) for r in c):,} |\n"
    report+='\nAll candidate controls, including each named write-in:\n\n| Contest | Candidate/slate as reported | Votes |\n| --- | --- | ---: |\n'
    for contest,cc in totals.items():
        for name,num in cc.items():report+=f'| {contest} | {name} | {num:,} |\n'
    report+=f'''
The [2022 original county canvass]({b22['requested_url']}) and separately downloaded statewide canvass give **8,102,908 governor votes**, including Jacqueline Abernathy 1,243 and Mark V Goloby 394. The independently retained Texas Legislature joint canvass agrees on the major/third candidates and 1,637 other votes. **There was no 2022 Texas Senate election.** The [2020 original county canvass]({b20['requested_url']}) gives **11,144,040 Senate votes**. Its December 2020 and October 2024 archived county copies agree on all 1,270 Senate cells. Hegar is **4,888,764** here; an unexplained secondary figure of 4,889,384 is 620 higher and is not adopted. These original comparator dependencies remain read-only in the partisanship worker's directory and are hashed in the turnout ledger.

| Contest | State valid votes | Votes in the same 2024 Senate top 15 | Share | Votes in the same 34 | Share |
| --- | ---: | ---: | ---: | ---: | ---: |
'''
    for label,prefix in specs:
        den=sum(int(r[prefix+'_total']) for r in c);a=sum(int(r[prefix+'_total']) for r in c[:15]);b=sum(int(r[prefix+'_total']) for r in c[:34]);report+=f'| {label} | {den:,} | {a:,} | {100*a/den:.8f}% | {b:,} | {100*b/den:.8f}% |\n'
    report+='''
These hold the selected county set fixed; they do not claim that the set is each comparator's independently ranked minimum. Year, contest, candidate appeal and vote universe change together. This is historical concentration, not a 2026 turnout forecast.

## Ballots, registration, methods and remaining-vote limits

The [SOS historical turnout page](https://www.sos.state.tx.us/elections/historical/70-92.shtml) labels 2024 turnout **11,388,674**, 2022 **8,102,908**, and 2020 **11,315,056**, with registration **18,623,931**, **17,672,143**, and **16,955,519**. Those turnout numbers equal the corresponding presidential/governor candidate totals in these canvasses. The page does not establish an independent statewide all-ballot count or split blank/under/overvotes. Its 96,820 difference from 2024 Senate votes is a **contest-denominator difference**, not a measured Senate undervote count. No statewide ballot total or county ballot ranking is fabricated from it.

Actual original **Harris County** precinct controls are stronger: **1,567,610 ballots**, **1,548,914 valid Senate votes**, **18,623 Senate undervotes**, **73 Senate overvotes**; these balance exactly across all **1,584** native units and all five named candidates. Ballot methods are **63,792 mail**, **1,180,154 early**, **321,109 Election Day**, **1,997 early provisional** and **558 Election Day provisional**, also balancing exactly in each unit. Source registration totals **2,664,202**. The method columns describe ballots; candidate-method allocations are not inferred. [All Harris primary unit controls](data/turnout/primary-harris-senate-units.csv.gz), [checks](data/turnout/primary-unit-controls.json).

Original Dallas vendor statistics give **858,562 ballots / 1,469,952 registered**; Travis gives **587,090 / 925,858**. Every selected original workbook numeric column reconciles to its own source Total row. These source-scoped ballot/registration observations populate the county CSV with explicit source IDs. Their active/suspense composition and registration snapshot dates are unestablished, so those fields remain qualified/blank. Other counties' ballot, under/over and registration cells remain blank where this research has not validated exact controls. County figures cannot be added into a complete statewide ballot or registration total.

A physical precinct, ballot-style subdivision, countywide vote center, central early/mail unit and TLC/Census VTD can be different things. A method column is not a polygon. Names such as `0001 - 1`, `1001 BS 1`, `101A`, `Limited Travis` and central/method categories remain source identities. No unit is removed because it lacks a Senate row or a map: original Angelina `Precinct 11B` and `Precinct 17B` are retained even though absent from the derivative roster. No November 2026 boundary/roster approval or cross-year unit crosswalk has been established. Historical `precincts reporting`, archive timestamps and HTTP cache metadata do not measure votes remaining or demonstrate a live publication cadence.

## Finer-unit coverage and source disagreements

The separately pinned OpenElections files retain **31,702 source-file/county/unit identities** across all offices: 2024 **10,786**, 2022 **5,055**, 2020 **15,861**. The selected contest/control extracts faithfully preserve **302,233 raw rows**: 2024 **157,929**, 2022 **35,995**, 2020 **108,309**. Full source rows, native IDs, exact office variants, district/party/candidate labels, source-row numbers and every method field are retained; no deduplication or residual allocation occurs. [Native roster](data/turnout/native-reporting-units.csv.gz), [coverage](data/turnout/native-coverage-summary.json), [source diagnostics](data/turnout/native-source-diagnostics.json).

Coverage is **184 source files but only 182 literal county identities in 2024**, **101 counties in 2022**, **248 in 2020**. “Done” in the upstream README does not establish all-county coverage in these particular statewide files. The 2024 file named Hardin labels rows Hunt; the file named Jeff Davis labels them Grayson. Both the filenames and literal row identities are preserved as conflicts; no votes are moved to the filename county. Angelina lacks a county column, explicitly mapped from its source filename. `Hildalgo` and `La Salle` remain native strings with documented aliases. Two repeated Eastland header rows are preserved as nondata evidence. Four 2024 files have duplicate candidate keys; 22 have nonadditive numeric method fields. Those diagnoses qualify the layer; they do not change the primary county ranking.

Actual downloaded county originals additionally retain **4,276 source/unit identities in six counties**: Harris **1,584**, Dallas **1,542**, Bexar **776**, Travis **287**, Midland **46**, Angelina **41**. All pages/worksheets were scanned for native identities, including units without Senate rows. [Original unit inventory](data/turnout/primary-native-units.csv.gz), [selected Dallas/Travis row arrays](data/turnout/primary-native-records.csv.gz), [original-source diagnostics](data/turnout/primary-native-diagnostics.json). Complete original PDF candidate/method validation is achieved for Harris; Bexar/Midland/Angelina are native identity inventories rather than independently validated all-cell candidate tables. Each layer remains separate in the priority contract.

**Originals themselves disagree by universe/vintage.** Dallas vendor Senate has **842,940**, versus SOS **842,425**: its generic write-in **818** exceeds valid named Andrus **52** plus Roche **170** (**222**) by **596**; Cruz/Allred/Brown are respectively **31/42/8 lower**, netting **515** more total votes. Travis has **578,885** versus **578,541**: generic write-in **601** versus valid named **78+161=239**, a **362** gap, while Cruz/Allred are **6/12 lower** and Brown equal, net **344** excess. These figures do not prove which votes were invalid, corrected or omitted. Generic totals are not allocated to named candidates. The original snapshots and exact [candidate/group comparisons](data/turnout/original-vendor-county-comparison.csv) remain intact.

The [TLC election-data documentation](https://data.capitol.texas.gov/topic/about/elections) explicitly describes a redistricting derivative that may differ from official returns. All five retained CSVs contain **9,712** unique CNTYVTD/VTDKEY rows across **254 county prefixes**, using one historical VTD roster. The separate [VTD identities and complete source rows](data/turnout/tlc-derived-vtd-units.csv.gz) are not native precinct results. [County/candidate differences](data/turnout/tlc-county-reconciliation.csv) preserve the full signed gaps. No VTD is dropped or rescaled.

| TLC measure | Derived total | Selected primary control | Derived minus primary |
| --- | ---: | ---: | ---: |
| 2024 Senate Allred | 5,031,142 | 5,031,249 | -107 |
| Senate Cruz | 5,990,637 | 5,990,741 | -104 |
| Senate Brown | 266,944 | 267,039 | -95 |
| Senate Andrus named write-in | 534 | 919 | -385 |
| Senate Roche named write-in | 976 | 1,906 | -930 |
| **2024 Senate all** | **11,290,233** | **11,291,854** | **-1,621** |
| 2024 President Harris | 4,835,134 | 4,835,250 | -116 |
| President Trump | 6,393,403 | 6,393,597 | -194 |
| President Oliver | 68,563 | 68,557 | +6 |
| President Stein | 82,698 | 82,701 | -3 |
| President generic versus valid named write-ins | 24,730 | 8,569 | +16,161 |
| **2024 President all** | **11,404,528** | **11,388,674** | **+15,854** |
| 2022 Governor Abbott | 4,437,097 | 4,437,099 | -2 |
| Governor O'Rourke | 3,554,772 | 3,553,656 | +1,116 |
| Governor Tippetts | 81,942 | 81,932 | +10 |
| Governor Barrios | 28,590 | 28,584 | +6 |
| Governor generic versus valid named write-ins | 4,367 | 1,637 | +2,730 |
| **2022 Governor all** | **8,106,768** | **8,102,908** | **+3,860** |

TLC voter-data registration is **18,686,517** in 2024 (**62,586 above** the SOS control) and **17,713,365** in 2022 (**41,222 above**). Its `Turnout` sums are **11,460,798** (**72,124 above**) and **8,143,047** (**40,139 above**). Definitions, source vintages, generic write-in scope and conversion effects are not fully resolved. Rates are not summed or multiplied into counts. Nothing here assigns an unexplained residual, prefers a newer-looking date without evidence or fabricates independent validation for 254 county precinct returns.

## Reproduction and retained evidence

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/texas/data/turnout/build_turnout.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/texas/data/turnout/reconcile_peer.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/texas/data/turnout/write_report.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/texas/data/turnout/validate_turnout.py
```

The build is offline and deterministic given the retained dependencies. It requires Python standard libraries and Poppler `pdftotext`; only the optional [fetcher](data/turnout/fetch_evidence.py) uses `requests`. Raw sources remain compressed; original ZIP members are parsed in memory. Harris's 52,427,785-byte PDF is stored losslessly as a complete gzip stream split into **32,000,000** and **11,773,799** byte parts, with part hashes and whole-original/stored hashes. Concatenate parts before decompressing; the build does this automatically. Every retained file is strictly below **40,000,000 bytes**.

The [source ledger](data/turnout/source-ledger.json) records exact requested/final URLs, UTC, status/headers, original/stored hashes and read-only shared dependencies. The [asset manifest](data/turnout/asset-manifest.json) covers owned paths, lengths and SHA-256. The [offline validator](data/turnout/validate_turnout.py) independently checks primary statewide candidate sums, county identities/coverage, D/R/other/write-ins, source-row replay, source-unit uniqueness/coverage, precise ranking/minimum80/remainder, Harris ballot/method controls, all hashes, report links and asset bounds. [Validation results](data/turnout/validation.json) and [independent peer reconciliation](data/turnout/peer-reconciliation.json) retain the checks; the latter compares **57,404 shared fields**, all 6,604 candidate/county cells, full order and exact priority keys. Optional ballot availability remains source-scoped.

The completed result is an all-county historical vote-volume ranking backed by actual official originals, with faithful finer-source inventories and explicit disagreements. Complete statewide native precinct validation, approved 2026 reporting geography, collector/replay implementation, observed live cadence, remaining-vote estimates and forecast calibration remain open.

## Full county ranking

Shares use the same 11,291,854 valid Senate-vote denominator. All 254 counties remain included; the first 34 form the accepted research priority. Optional ballot counts and source-specific candidate details remain in the CSV.

| Rank | County | FIPS | Senate 2024 | State % | Cumulative % | President 2024 | Governor 2022 | Senate 2020 |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
'''
    for r in c:report+=f"| {r['rank']} | {r['county']} | {r['county_fips']} | {int(r['senate_2024_total']):,} | {100*float(r['share_state_senate_2024']):.6f} | {100*float(r['cumulative_share_state_senate_2024']):.6f} | {int(r['president_2024_total']):,} | {int(r['governor_2022_total']):,} | {int(r['senate_2020_total']):,} |\n"
    report=report.replace('Actual original **Harris County** precinct controls', 'Actual original **Harris County** [precinct canvass]('+meta('original-harris-2024')['requested_url']+') controls')
    report=report.replace('Original Dallas vendor statistics', 'Original [Dallas vendor export]('+meta('original-dallas-2024')['requested_url']+') statistics')
    report=report.replace('Travis gives **587,090 / 925,858**', '[Travis original export]('+meta('original-travis-2024')['requested_url']+') gives **587,090 / 925,858**')
    report=report.replace('Actual downloaded county originals additionally retain', 'Actual downloaded county originals, including [Bexar]('+meta('original-bexar-2024')['requested_url']+'), [Midland]('+meta('original-midland-2024')['requested_url']+') and [Angelina]('+meta('original-angelina-2024')['requested_url']+'), additionally retain')
    (S/'turnout.md').write_text(report)
    print('Report written; priority groups preserve',sum(len(g['native_constituents']) for g in p['groups']),'native constituent entries and',sum(len(g['derived_vtd_constituents']) for g in p['groups']),'separate derived VTD identities')
if __name__=='__main__':run()
