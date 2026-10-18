#!/usr/bin/env python3
"""Generate the turnout report from exact source-scoped extracts (no network)."""
import csv,json
from decimal import Decimal,localcontext
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def read(n):
    with (ROOT/n).open(newline='') as f:return list(csv.DictReader(f))
def pct(n,d):
    with localcontext() as c:c.prec=40;return f'{Decimal(n)*100/Decimal(d):.10f}%'
def main():
    rows=read('../county-turnout.csv');controls=json.loads((ROOT/'state-controls.json').read_text());den=int(rows[0]['state_candidate_generic_writein_denominator']);top=sum(int(r['pres2024_candidate_generic_writein_votes']) for r in rows[:15]);prior=sum(int(r['pres2024_candidate_generic_writein_votes']) for r in rows[:40]);cross=prior+int(rows[40]['pres2024_candidate_generic_writein_votes'])
    primary=lambda y:f'https://sos.iowa.gov/elections/pdf/{y}/general/canvsummary.pdf'
    text=f'''# Iowa turnout volume and exact county priority

Research retrieval: October 18, 2026 UTC (October 17 in Iowa). **All 99 counties are included.** Iowa's actual 2024 baseline is **president**, not Senate: the SOS 2024 general canvass contains the presidential contest and no U.S. Senate contest. Ranking measures vote volume, not turnout rate. The exact source universe is the seven named presidential tickets plus generic Write-in, **1,663,506**; individual generic marks are not identified as valid named candidates. [Primary 2024 canvass, pp.2-15]({primary(2024)}).

**Top 15 in descending order:** {', '.join(r['county'] for r in rows[:15])}. Their **{top:,} / {den:,} = {pct(top,den)}** is calculated from the primary canvass. [All-county extract](data/county-turnout.csv), [candidate/method cells](data/turnout/canvass-candidate-method.csv), [primary source]({primary(2024)}).

**Minimum largest-first set reaching 80%: 41 counties, {cross:,} / {den:,} = {pct(cross,den)}.** The preceding 40 contribute **{prior:,} = {pct(prior,den)}**. Henry, **FIPS 19087**, contributes **9,600** and crosses the threshold. Exact integer proof: `5 * 1,322,507 = 6,612,535 < 4 * 1,663,506 = 6,654,024 <= 5 * 1,332,107 = 6,660,535`. Since the first 40 are the 40 largest values, no 40-county selection can reach 80%. The remainder is **58 counties, {den-cross:,} votes = {pct(den-cross,den)}**. Ties would use ascending county FIPS; no rounding enters selection. [Machine contract with every county/native constituent](data/turnout/priority-set.json), [source]({primary(2024)}).

**Exact 41, in order:** {', '.join(r['county'] for r in rows[:41])}. The top 15 are contained within this set. The coordinator independently accepted the county arithmetic and conserved source-context research inventory; current precinct geography and crosswalks remain unapproved. [Coordinator county review](data/coordinator-baseline-reconciliation.json), [native conservation review](data/coordinator-native-contract-checks.json).

## Denominator, candidates and comparators

The 2024 source's printed Total **1,674,011** includes **8,586 under votes and 1,919 over votes**. Subtracting those explicitly printed categories gives the 1,663,506 candidate/generic denominator. The named-ticket-only subtotal is **1,656,849**; the separate generic Write-in column is **6,657**. No generic mark is assigned to an individual write-in candidate, discarded as invalid, or normalized to a different candidate universe. [Primary 2024 canvass, state footer p.15]({primary(2024)}).

| Actual election/contest | All printed named candidates/tickets and generic write-in votes | Candidate + generic denominator | Under | Over | Printed Total |
| --- | --- | ---: | ---: | ---: | ---: |
'''
    for y,label in [(2024,'2024 president'),(2022,'2022 Senate, other Class III seat / midterm'),(2020,'2020 Senate, same Class II seat as 2026')]:
        c=controls[str(y)];names='; '.join(f'{k}: {v:,}' for k,v in zip(c['column_labels'][:-3],c['state_counts'][:-3]));text+=f"| [{label}]({primary(y)}) | {names} | {c['candidate_generic_writein_votes']:,} | {c['under_votes']:,} | {c['over_votes']:,} | {c['reported_contest_total']:,} |\n"
    text+='''
The complete 2022 Senate contest is Grassley-Franken, a midterm comparison for the other Senate seat; no governor substitution is used. The 2020 Ernst-Greenfield contest is the previous election for the 2026 Class II seat. Each comparator retains every printed candidate and generic Write-in separately. [2022 canvass](https://sos.iowa.gov/elections/pdf/2022/general/canvsummary.pdf), [2020 canvass](https://sos.iowa.gov/elections/pdf/2020/general/canvsummary.pdf), [Class II roster](https://www.senate.gov/senators/Class_II.htm).

## Voters, ballots, registration and method scope

The separate turnout reports label these values voters. The candidate denominator is not substituted for voters or ballots. Registration is the source's election-date active/inactive snapshot; percentages are the source's published strings. Active-voter turnout can exceed 100% because the 2024 report explicitly includes participation by inactive voters or new county registrants. [2024 turnout report](https://sos.iowa.gov/elections/pdf/2024/general/turnout.pdf).

| Turnout-report election/date | Election Day voters | Absentee voters | Total voters | Active registered | Inactive registered | Published total-registration turnout |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
'''
    for r in read('turnout-report-counties.csv'):
        if r['county_fips']!='19':continue
        y=r['year'];text+=f"| [{r['registration_as_of']}](https://sos.iowa.gov/elections/pdf/{y}/general/turnout.pdf) | {int(r['election_day_voters']):,} | {int(r['absentee_voters']):,} | {int(r['total_voters']):,} | {int(r['active_registered']):,} | {int(r['inactive_registered']):,} | {r['published_total_turnout_pct']}% |\n"
    text+='''
**Source method disagreement retained:** the 2024 turnout report gives statewide Election Day 992,112 / absentee 681,899, while the presidential canvass gives 992,119 / 681,892. Both give 1,674,011 total. The county difference is Des Moines: turnout report 9,996 / 9,175 versus canvass 10,003 / 9,168, total 19,171. The -7/+7 is not reclassified or assigned a cause. All other shared turnout-report/canvass county totals and available method controls reconcile. [2024 turnout](https://sos.iowa.gov/elections/pdf/2024/general/turnout.pdf), [2024 canvass](https://sos.iowa.gov/elections/pdf/2024/general/canvsummary.pdf), [difference ledger](data/turnout/turnout-canvass-method-differences.json).

## Complete descending order

Every value is candidate-plus-generic contest votes, not ballots. Priority marks ranks 1-41; ranks 42-99 are the complete remainder. Native county names and Census FIPS remain separate fields. Page is a real county (19145), not pagination. Cumulative percentages below are display rounding only. [2024 primary canvass](https://sos.iowa.gov/elections/pdf/2024/general/canvsummary.pdf), [2022 primary canvass](https://sos.iowa.gov/elections/pdf/2022/general/canvsummary.pdf), [2020 primary canvass](https://sos.iowa.gov/elections/pdf/2020/general/canvsummary.pdf), [primary Census county codes](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt).

| Rank | County | FIPS | 2024 president | Cumulative share | 2022 Senate | 2020 Senate | Priority |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
'''
    for r in rows:text+=f"| {r['rank_2024']} | {r['county']} | {r['county_fips']} | {int(r['pres2024_candidate_generic_writein_votes']):,} | {pct(int(r['cumulative_candidate_generic_writein_votes']),den)} | {int(r['sen2022_candidate_generic_writein_votes']):,} | {int(r['sen2020_candidate_generic_writein_votes']):,} | {'yes' if r['in_minimum80']=='True' else ''} |\n"
    text+='''
## Native source objects and actual coverage

The [SOS index](https://sos.iowa.gov/iowans/election-results-statistics) links the canvasses, historical precinct exports and separate statistical reports. The 2024 precinct-Excel link leads to the [actual historical results app](https://electionresults.iowa.gov/IA/122322/web.345435/). Its initial 403 and later successful 200 app shell are both retained. The observed script/configuration chain exposes state election 122322/version 356043 and the actual 99-county EID/version roster. All 99 county XML report ZIPs, settings and status files downloaded successfully. This is historical 2024 evidence, with state snapshot clock December 16, 2024 8:19:40 AM CST and settings update 8:19:48 AM CST. It is not an approved November 2026 channel or a demonstrated publication cadence. [State settings and county roster](https://electionresults.iowa.gov/IA/122322/356043/json/en/electionsettings.json), [actual state XML download](https://electionresults.iowa.gov/IA/122322/356043/reports/detailxml.zip), [retained chain](data/turnout/source-manifest.json).

| Source context | Native constituent objects | Validated scope |
| --- | ---: | --- |
| 2024 presidential county XML Contest | 1,653 | All 99 counties; 26,448 unit/candidate/method cells, 2,376 county candidate/method controls; every sum exact to canvass |
| 2024 XML root VoterTurnout | 1,651 | Separate registration/ballot objects; 99 administrative county controls; Lucas omits two units |
| 2024 county status arrays | 1,653 | Literal native names/status/registration/ballot fields; candidate/status names and order agree |
| 2022 Senate county exports | 1,653 | All 99 counties, plus 99 administrative Total rows |
| 2020 Senate county exports | 1,661 | All 99 counties, plus 99 administrative Total rows; Scott uses its actual linked PDF |
| 2024/2022/2020 registration-statistics precinct labels | 1,658 / 1,651 / 1,681 | All 99 counties in each year; separate demographic-report objects, with no assumed candidate-unit crosswalk |

The 2022 [county export index](https://sos.iowa.gov/precinct-results-county-2022-general-0) contains a broken double-space Black Hawk filename. The retained [tested single-space repair](https://sos.iowa.gov/elections/pdf/precinctresults/2022general/black%20hawk.xls) succeeds; it is explicitly a filename repair, not represented as the page's actual href. The 2020 [county export index](https://sos.iowa.gov/precinct-results-county-2020-general) supplies XLSX files and [Scott's canvass PDF](https://sos.iowa.gov/elections/pdf/precinctresults/2020general/scott.pdf). Failed alternate Adair XLS and Story PDF responses remain retained alongside successful XLSX originals. Full sparse workbook cells, all worksheets, merge/formula/type metadata and source clocks are losslessly preserved; no source row is deduplicated. [Native schema](data/turnout/SCHEMA.md), [2022/2020 unit ledger](data/turnout/native-units.csv), [candidate/method cells](data/turnout/native-unit-candidate-method.csv), [2024 contexts](data/turnout/clarity-2024-native-units.csv).

**Lucas context gap:** candidate and status lists have seven units; root XML VoterTurnout has five, omitting literal `Chariton City Hall Precinct ` and `Chariton Community Center Precinct ` (trailing spaces preserved). Those five turnout rows sum to 2,733 ballots versus the printed 4,676 county control; the status array includes all seven and sums to 4,676. The -1,943 remains a source-context gap, with no allocation. Registration-unit sums also differ from county controls in 93 counties; literal zero-filled registry contexts are retained but not treated as complete registries. [Lucas original XML](https://electionresults.iowa.gov/IA/Lucas/122381/354852/reports/detailxml.zip), [Lucas status](https://electionresults.iowa.gov/IA/Lucas/122381/354852/json/status.json), [all-county context ledger](data/turnout/clarity-2024-context-reconciliation.csv).

**Candidate party-label scope:** the exact Stodden/Cholensky ticket is labeled SPA, SPU, PSI or NoP in 14 county XMLs, versus SOC in the state canvass. All counts match using the exact ticket name; all 42 candidate/method party-label conflicts are retained separately without rewriting party fields. For example, [Cedar's original XML](https://electionresults.iowa.gov/IA/Cedar/122338/355823/reports/detailxml.zip) prints SPA; [the state canvass](https://sos.iowa.gov/elections/pdf/2024/general/canvsummary.pdf) prints SOC. [Complete county/party ledger](data/turnout/clarity-2024-party-label-differences.csv).

Physical precincts, ballot-style splits, reporting rows, central absentee groups and polling places are different objects. Historical source labels that happen to say Central or Early do not establish a voting method. Native method columns are retained; no current polygon or cross-year allocation is inferred. Finer-unit under/over counts are absent from the selected 2024 XML and the 2022/2020 workbook candidate sheets; they remain blank/unavailable rather than calculated as residuals. Scott's 2020 PDF and county canvass method under/over categories are retained where actually printed. [Source exports](https://sos.iowa.gov/precinct-results-county-2020-general), [2024 sample native XML](https://electionresults.iowa.gov/IA/Adair/122323/354568/reports/detailxml.zip), [schema](data/turnout/SCHEMA.md).

The Cass official page separates local PDFs from state ENR links. Its linked 2024 PDF internally says **Unofficial Final Results**, November 12, 2024 1:04:10 PM CST. Page 1 shows countywide 7,217 presidential candidate/generic votes, 7,292 ballots, registration 9,661 and 12/12 reporting. Its Election Day heading is not used to classify these whole-county counts as an Election Day method slice. All candidate/under/over counts match the state county Total, while registration remains a separate snapshot without a stated as-of date. [Official Cass election page](https://www.casscountyia.gov/county-government/elections/), [actual local PDF](https://www.casscountyia.gov/wp-content/uploads/2019/10/2024.11.05-General-Election-Results.pdf), [checked transcription](data/turnout/cass-summary-transcription.json).

## Statistical snapshots and unresolved source differences

All **327,516 demographic/age/metric rows** and **4,990 native labels** are retained. All 7,128 precinct-to-county age/metric controls reconcile internally. These registration-statistics reports are source-dated snapshots, not substitutes for certified candidate counts or election-date turnout reports. The 2024 county report is dated January 9, 2025; state/precinct reports January 13. The 2022 reports are dated January 11, 2023, with a January 27 Harrison addendum/correction. The 2020 source dates vary by report/county, and the revised statewide report explicitly warns of time-lapse differences after Henry/Story were originally omitted. [2024 county](https://sos.iowa.gov/elections/pdf/2024/general/countystats.pdf), [2024 state](https://sos.iowa.gov/elections/pdf/2024/general/statestats.pdf), [2024 precinct](https://sos.iowa.gov/elections/pdf/2024/general/precinctstats.pdf), [2022 county](https://sos.iowa.gov/elections/pdf/2022/general/countystats.pdf), [2022 state](https://sos.iowa.gov/elections/pdf/2022/general/statestats.pdf), [2020 state](https://sos.iowa.gov/elections/pdf/2020/general/statestats.pdf).

The following totals preserve separate source scopes; the 2020 county report contains 97 counties, omitting Henry and Story, while the revised state and precinct reports cover all 99. No differences are rescaled or assigned to counties. [2020 county report](https://sos.iowa.gov/elections/pdf/2020/general/countystats.pdf), [2020 precinct report](https://sos.iowa.gov/elections/pdf/2020/general/precinctstats.pdf), [2022 precinct report](https://sos.iowa.gov/elections/pdf/2022/general/precinctstats.pdf), [full age/source controls](data/turnout/statistics-state-reconciliation.csv).

| Year | Metric | Sum of precinct-report county controls | County report own state footer | Separate statewide report |
| --- | --- | ---: | ---: | ---: |
'''
    for r in read('statistics-state-reconciliation.csv'):
        if r['age_scope']=='total':text+=f"| {r['year']} | {r['metric']} | {int(r['precinct_county_grand_total_sum']):,} | {int(r['county_report_state_footer']):,} | {int(r['state_report_footer']):,} |\n"
    text+='''
One internal source arithmetic disagreement remains: the 2020 statewide REGISTERED age bins sum to **2,203,256**, while the printed TOTAL is **2,203,254**. The original numbers and +2 are retained, verified against the rendered source page. It does not affect candidate totals or county priority. [Primary statewide report p.2](https://sos.iowa.gov/elections/pdf/2020/general/statestats.pdf), [age ledger](data/turnout/statistics-age-imbalances.json).

## Reproduction and validation

[SCHEMA.md](data/turnout/SCHEMA.md) defines every key/denominator and the acquisition/extraction sequence. [Source manifest](data/turnout/source-manifest.json) and [fresh reused-request metadata](data/turnout/reused-request-verification.json) retain actual parent/download chains, request/final URLs, status/redirects/headers, retrieval UTC, original/stored hashes and sizes. Reused statewide originals are read-only hash references; no duplicate large primary PDF is required. Fresh identical downloads reference those bytes; changed fresh responses are retained separately. Every stored artifact is strictly below 40,000,000 bytes through lossless compression, never truncation. [Owned asset manifest](data/turnout/asset-manifest.json), [offline validation](data/turnout/validation.json).

Validation re-extracts the original canvasses; checks all 99 unique FIPS/name joins, all 297 county-contests and 7,484 candidate/method cells against published state controls; verifies each native source candidate/method balance, all 99 county exports, exact order/minimum-80 arithmetic, all available statistics controls, source hashes/bytes, local links and bounds. Independent partisanship extraction agrees on every shared county/candidate/native field after documented display aliases; it independently checked all 327,516 statistical rows against the source PDFs. [Turnout peer audit](data/turnout/peer-reconciliation.json), [independent full peer audit](data/baselines/peer-reconciliation.json), [independent statistics verification](data/baselines/statistics-verification.json), [2024 native controls](data/turnout/clarity-2024-validation.json).

Remaining limits are source-scoped write-in validity/individual allocation, omitted 2024 unit under/over values, the retained method/context/party/statistics disagreements above, and unapproved current geography/crosswalks. This package is research data; it claims no implemented collector, calibrated Needle or 2026 forecast.
'''
    (ROOT.parent.parent/'turnout.md').write_text(text)
if __name__=='__main__':main()
