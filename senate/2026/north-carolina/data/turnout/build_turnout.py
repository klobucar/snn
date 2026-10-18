#!/usr/bin/env python3
"""Offline NC turnout rebuild and primary-source reconciliation (stdlib).

python3 senate/2026/north-carolina/data/turnout/build_turnout.py
Add --extract-pdfs to recreate saved text with Poppler pdftotext -layout.
Fetch original evidence separately with fetch_evidence.py. Writes only the
assigned turnout.md, data/county-turnout.csv and data/turnout/ paths.
"""
import argparse
import collections
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent.parent
VERSION = 'nc-turnout-1'
YEARS = {'2024': ('20241105', '11/05/2024', 'US PRESIDENT', '1393'),
         '2022': ('20221108', '11/08/2022', 'US SENATE', '1378')}
ALIASES = {'Claudia De la Cruz': 'Claudia De la Cruz (Write-In)',
           'Michelle Estelle Lewis': 'Michelle Estelle Lewis (Write-In)'}
COUNTS = ['total_votes', 'election_day', 'early_voting', 'absentee_by_mail', 'provisional']
PRIMARY_TOTALS = {
    '2024': {'Kamala D. Harris': 2715378, 'Chase Oliver': 22125,
             'Jill Stein': 24762, 'Randall Terry': 6863, 'Donald J. Trump': 2898424,
             'Cornel West': 12099, 'Write-In (Miscellaneous)': 18938,
             'Claudia De la Cruz (Write-In)': 526, 'Shiva Ayyadurai (Write-In)': 30},
    '2022': {'Matthew Hoh': 29934, 'Cheri Beasley': 1784049, 'Shannon W. Bray': 51640,
             'Ted Budd': 1905786, 'Write-In (Miscellaneous)': 2378,
             'Michelle Estelle Lewis (Write-In)': 137},
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def write_csv(path, rows):
    assert rows
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def pct(n, denominator, places=8):
    with localcontext() as ctx:
        ctx.prec = 40
        return f'{Decimal(100) * Decimal(n) / Decimal(denominator):.{places}f}'

def canonical(name):
    return ALIASES.get(name, name)

def pdf_extracts(refresh):
    path = ROOT / 'extraction-manifest.json'
    if refresh:
        result = {}
        version = subprocess.run(['pdftotext', '-v'], capture_output=True, text=True, check=True)
        for year in YEARS:
            for kind in ['county', 'contest']:
                stem = f'certified-{year}-{kind}'
                pdf, txt = ROOT / (stem + '.pdf'), ROOT / (stem + '.txt')
                subprocess.run(['pdftotext', '-layout', str(pdf), str(txt)], check=True)
                result[txt.name] = dict(input_file=pdf.name, input_sha256=digest(pdf),
                    sha256=digest(txt), command='pdftotext -layout INPUT.pdf OUTPUT.txt',
                    tool_version=(version.stdout + version.stderr).strip().splitlines()[0])
        dump(path.name, result)
    result = json.loads(path.read_text())
    for name, info in result.items():
        assert digest(ROOT / name) == info['sha256'], ('text hash mismatch', name)
        assert digest(ROOT / info['input_file']) == info['input_sha256']

def parse_pdf(year, kind, county_names):
    """Infer column starts from each page header; preserve context across pages.

    Only numeric data rows update context: footers must never replace the
    current contest. Wrapped write-in names have explicit audited aliases.
    Page numbers below are 1-based PDF pages, including any signature cover.
    """
    rows, county, contest = [], None, None
    office = YEARS[year][2]
    text = (ROOT / f'certified-{year}-{kind}.txt').read_text()
    for page_number, page in enumerate(text.split('\f'), 1):
        lines = page.splitlines()
        header = next((s for s in lines if s.startswith('County' if kind == 'county' else 'Contest')
                       and 'Choice' in s and 'Total Votes' in s), None)
        if header is None:
            continue
        fields = (['County'] if kind == 'county' else []) + [
            'Contest', 'Choice', 'Party', 'Total Votes', 'Election Day',
            'Early Voting' if year == '2024' else 'One Stop', 'Abs Mail', 'Provisional']
        starts = [header.index(s) for s in fields]
        for line in lines[lines.index(header) + 1:]:
            cells = [line[a:b].strip() for a, b in zip(starts, starts[1:] + [len(line)])]
            # Numeric values are right-aligned; a seven-digit One Stop value
            # can begin left of its column label. Parse the five trailing
            # integers rather than slicing by numeric header starts.
            numeric_match = re.search(r'(?<!\S)([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s+([0-9,]+)\s*$', line)
            if numeric_match is None:
                continue
            values = numeric_match.groups()
            c = dict(zip(fields, cells))
            if kind == 'county' and c['County']:
                assert c['County'] in county_names, (page_number, c)
                county = c['County']
            if c['Contest']:
                contest = c['Contest']
            if contest != office:
                continue
            integers = [int(v.replace(',', '')) for v in values]
            assert integers[0] == sum(integers[1:]), (year, page_number, c)
            rows.append(dict(year=year, contest=office, county_native=county if kind == 'county' else 'STATE',
                candidate=canonical(c['Choice']), source_choice_first_line=c['Choice'], party=c['Party'],
                **dict(zip(COUNTS, integers)), source_file=f'certified-{year}-{kind}.pdf',
                pdf_page=page_number))
    keys = [(r['county_native'], r['candidate']) for r in rows]
    assert len(keys) == len(set(keys)), ('duplicate PDF candidate key', year, kind)
    return rows

def parse_zip(year, county_names):
    date, election_date, office, group = YEARS[year]
    aggregate = collections.defaultdict(lambda: [0] * 5)
    seen, parties, precincts, flags, unit_flags = set(), {}, set(), collections.Counter(), {}
    all_rows = selected = 0
    with zipfile.ZipFile(ROOT / f'results_pct_{date}.zip') as z:
        assert z.namelist() == [f'results_pct_{date}.txt']
        info = z.getinfo(z.namelist()[0])
        with z.open(info) as stream:
            r = csv.DictReader(io.TextIOWrapper(stream, encoding='utf-8-sig'), delimiter='\t')
            for row in r:
                all_rows += 1
                assert row['Election Date'] == election_date
                if year == '2024':
                    assert row['Contest Name'] != 'US SENATE', 'Unexpected 2024 US Senate contest'
                if row['Contest Name'] != office:
                    continue
                selected += 1
                assert row['County'] in county_names
                assert row['Contest Group ID'] == group and row['Vote For'] == '1'
                choice = canonical(row['Choice'])
                key = (row['County'], row['Precinct'], group, choice)
                assert key not in seen, ('duplicate ZIP key', year, key)
                seen.add(key)
                precincts.add((row['County'], row['Precinct']))
                flags[row['Real Precinct']] += 1
                unit = (row['County'], row['Precinct'])
                if unit in unit_flags:
                    assert unit_flags[unit] == row['Real Precinct']
                unit_flags[unit] = row['Real Precinct']
                methods = [int(row[k]) for k in ['Total Votes', 'Election Day',
                    'Early Voting' if year == '2024' else 'One Stop', 'Absentee by Mail', 'Provisional']]
                assert min(methods) >= 0 and methods[0] == sum(methods[1:])
                k = (row['County'], choice)
                aggregate[k] = [a + b for a, b in zip(aggregate[k], methods)]
                if choice in parties:
                    assert parties[choice] == row['Choice Party'].strip()
                parties[choice] = row['Choice Party'].strip()
    rows = [dict(year=year, contest=office, county_native=c, candidate=n, party=parties[n],
                 **dict(zip(COUNTS, values))) for (c, n), values in sorted(aggregate.items())]
    return rows, dict(all_rows=all_rows, selected_rows=selected, county_candidate_rows=len(rows),
        county_count=len({c for c, _ in aggregate}), unique_county_precinct_pairs=len(precincts),
        selected_rows_by_real_precinct_flag=dict(flags), group_id=group,
        selected_units_by_real_precinct_flag=dict(collections.Counter(unit_flags.values())),
        zip_member=info.filename, zip_member_uncompressed_bytes=info.file_size,
        duplicate_county_precinct_group_choice_keys=0)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--extract-pdfs', action='store_true')
    args = ap.parse_args()
    manifest = json.loads((ROOT / 'input-manifest.json').read_text())
    for name, metadata in manifest['sources'].items():
        assert digest(ROOT / name) == metadata['sha256'], ('source hash mismatch', name)
        assert (ROOT / name).stat().st_size == metadata['bytes']
    pdf_extracts(args.extract_pdfs)
    census = [r for r in csv.DictReader((ROOT / 'national_county2020.txt').open(), delimiter='|')
              if r['STATEFP'] == '37']
    assert len(census) == 100
    fips = {r['COUNTYNAME'].removesuffix(' County').upper(): r for r in census}
    assert len(fips) == 100 and len({r['COUNTYFP'] for r in census}) == 100
    dashboards, native_ids, certified, state_results, zip_results, zip_checks = {}, {}, {}, {}, {}, {}
    diffs, reconciliation, extracted = [], [], []
    checks = dict(parser_version=VERSION, research_date_local='2026-10-17', county_count=100,
                  retrieval_utc_min=min(v['retrieved_utc'] for v in manifest['sources'].values()),
                  retrieval_utc_max=max(v['retrieved_utc'] for v in manifest['sources'].values()))
    for year in YEARS:
        a = json.loads((ROOT / f'dashboard-{year}-county.json').read_text(encoding='utf-8-sig'))
        assert len(a) == 101 and len({r['cid'] for r in a}) == 101
        statewide = next(r for r in a if r['cid'] == '0')
        counties = {r['cnm']: r for r in a if r['cid'] != '0'}
        assert len(counties) == 100 and set(counties) == set(fips)
        assert {int(r['cid']) for r in counties.values()} == set(range(1, 101))
        assert all('OFFICIAL GENERAL ELECTION RESULTS' in r['tle'] for r in a)
        dashboards[year] = counties
        native_ids[year] = {c: r['cid'] for c, r in counties.items()}
        for field in ['bct', 'rtl']:
            assert sum(int(r[field]) for r in counties.values()) == int(statewide[field])
        state_results[year] = parse_pdf(year, 'contest', set(fips))
        certified[year] = parse_pdf(year, 'county', set(fips))
        zip_results[year], zip_checks[year] = parse_zip(year, set(fips))
        extracted += certified[year] + state_results[year]
        assert {r['county_native'] for r in certified[year]} == set(fips)
        by_candidate = {r['candidate']: r for r in state_results[year]}
        assert {k: r['total_votes'] for k, r in by_candidate.items()} == PRIMARY_TOTALS[year]
        ballot_candidates = {k for k, r in by_candidate.items() if r['party']}
        for c in fips:
            rr = [r for r in certified[year] if r['county_native'] == c]
            assert ballot_candidates <= {r['candidate'] for r in rr}
            assert sum(r['total_votes'] for r in rr) <= int(counties[c]['bct'])
        for candidate, statewide_row in by_candidate.items():
            selected = [r for r in certified[year] if r['candidate'] == candidate]
            assert {r['party'] for r in selected} == {statewide_row['party']}
            for method in COUNTS:
                county_sum = sum(r[method] for r in selected)
                assert county_sum == statewide_row[method], (year, candidate, method, county_sum, statewide_row)
            zip_sum = sum(r['total_votes'] for r in zip_results[year] if r['candidate'] == candidate)
            reconciliation.append(dict(year=year, contest=YEARS[year][2], candidate=candidate,
                party=statewide_row['party'], certified_county_sum=sum(r['total_votes'] for r in selected),
                primary_certified_statewide=statewide_row['total_votes'], difference=0,
                election_results_zip_sum=zip_sum, zip_minus_certified=zip_sum-statewide_row['total_votes']))
        pdf_map = {(r['county_native'], r['candidate']): r for r in certified[year]}
        zip_map = {(r['county_native'], r['candidate']): r for r in zip_results[year]}
        assert set(zip_map) <= {(c, k) for c in fips for k in by_candidate}
        for c, candidate in sorted(set(pdf_map) | set(zip_map)):
            p, z = pdf_map.get((c, candidate), {}), zip_map.get((c, candidate), {})
            for method in COUNTS:
                x, y = p.get(method, 0), z.get(method, 0)
                if x != y:
                    diffs.append(dict(year=year, county_native=c, candidate=candidate, count_field=method,
                        certified_county_pdf=x, election_results_zip=y, zip_minus_certified=y-x,
                        certified_pdf_page=p.get('pdf_page', 'omitted zero-count choice')))
        checks[year] = dict(contest=YEARS[year][2], certified_county_candidate_rows=len(certified[year]),
            statewide_candidates=len(by_candidate), all_candidate_contest_votes=sum(PRIMARY_TOTALS[year].values()),
            ballots_cast=int(statewide['bct']), registered_voters=int(statewide['rtl']),
            dashboard_statewide_source_updated_literal=statewide['imp'],
            dashboard_statewide_source_submitted_literal=statewide['sub'],
            source_timestamp_timezone='not specified in downloaded JSON', zip_checks=zip_checks[year],
            statewide_candidate_and_method_reconciliation='all exact',
            zip_contest_total=sum(r['total_votes'] for r in zip_results[year]))
        exact_weight_sum = sum((Fraction(sum(r['total_votes'] for r in certified[year]
                                      if r['county_native'] == c), sum(PRIMARY_TOTALS[year].values()))
                                for c in fips), Fraction(0))
        assert exact_weight_sum == 1
        checks[year]['exact_contest_weight_fraction_sum'] = str(exact_weight_sum)
    assert native_ids['2024'] == native_ids['2022']
    assert not [r for r in diffs if r['year'] == '2022'], '2022 PDF/ZIP disagreement'
    checks['county_matching'] = dict(census_counties=100, dashboard_2024_counties=100,
        dashboard_2022_counties=100, certified_2024_counties=100, certified_2022_counties=100,
        zip_2024_counties=100, zip_2022_counties=100, unmatched=0,
        duplicated_fips=0, duplicated_native_ids=0, native_id_changes_between_years=0,
        name_normalization='Census suffix County removed; uppercase comparison; no fuzzy matches')
    rows = []
    for c, census_row in fips.items():
        r = dict(county=census_row['COUNTYNAME'].removesuffix(' County'), county_native=c,
                 county_fips=census_row['STATEFP'] + census_row['COUNTYFP'],
                 ncsbe_county_id=native_ids['2024'][c])
        for year, prefix in [('2024', 'president_2024'), ('2022', 'senate_2022')]:
            rr = [v for v in certified[year] if v['county_native'] == c]
            r[prefix + '_d'] = sum(v['total_votes'] for v in rr if v['party'] == 'DEM')
            r[prefix + '_r'] = sum(v['total_votes'] for v in rr if v['party'] == 'REP')
            r[prefix + '_total'] = sum(v['total_votes'] for v in rr)
            r[prefix + '_other'] = r[prefix + '_total']-r[prefix + '_d']-r[prefix + '_r']
            r['ballots_cast_' + year] = int(dashboards[year][c]['bct'])
            r['registered_voters_' + year] = int(dashboards[year][c]['rtl'])
            r['ballots_minus_contest_' + year] = r['ballots_cast_' + year]-r[prefix + '_total']
            r['ballots_cast_source_updated_' + year] = dashboards[year][c]['imp']
            r['ballots_cast_source_submitted_' + year] = dashboards[year][c]['sub']
            r['source_' + prefix] = f'NC SBE certified county abstract {year}; all candidate choices including write-ins'
        rows.append(r)
    total = checks['2024']['all_candidate_contest_votes']
    rows.sort(key=lambda r: (-r['president_2024_total'], r['county_fips']))
    cumulative, cutoff = 0, None
    for rank, r in enumerate(rows, 1):
        cumulative += r['president_2024_total']
        r.update(rank_2024=rank, statewide_president_2024_pct=pct(r['president_2024_total'], total),
            cumulative_president_2024_total=cumulative, cumulative_president_2024_pct=pct(cumulative, total),
            top15=int(rank <= 15))
        if cutoff is None and 5*cumulative >= 4*total:
            cutoff = rank
    assert cumulative == total and cutoff
    for r in rows:
        r['smallest_80pct_set'] = int(r['rank_2024'] <= cutoff)
        r['research_priority'] = int(r['top15'] or r['smallest_80pct_set'])
        r['statewide_senate_2022_pct'] = pct(r['senate_2022_total'], checks['2022']['all_candidate_contest_votes'])
    def ranking(column):
        ranked = sorted(rows, key=lambda r: (-r[column], r['county_fips']))
        n, acc, before, state = 0, 0, 0, sum(r[column] for r in ranked)
        for n, r in enumerate(ranked, 1):
            before, acc = acc, acc+r[column]
            if 5*acc >= 4*state:
                break
        return ranked, dict(top15_total=sum(r[column] for r in ranked[:15]),
            top15_pct=pct(sum(r[column] for r in ranked[:15]), state), smallest_80pct_count=n,
            smallest_80pct_total=acc, smallest_80pct_pct=pct(acc, state),
            before_cutoff_total=before, before_cutoff_pct=pct(before, state),
            smallest_80pct_set=[r['county'] for r in ranked[:n]], statewide_total=state)
    _, priority = ranking('president_2024_total')
    priority['top15'] = [r['county'] for r in rows[:15]]
    assert priority['before_cutoff_total']*5 < total*4 <= priority['smallest_80pct_total']*5
    for column, key in [('senate_2022_total', 'midterm_2022'), ('ballots_cast_2024', 'ballots_2024'),
                        ('ballots_cast_2022', 'ballots_2022')]:
        ranked, stats = ranking(column)
        for n, r in enumerate(ranked, 1):
            r['rank_' + key] = n
        checks[key + '_concentration'] = stats
    priority['2022_senate_votes_in_2024_priority_set'] = sum(r['senate_2022_total'] for r in rows[:cutoff])
    priority['2022_senate_pct_in_2024_priority_set'] = pct(priority['2022_senate_votes_in_2024_priority_set'], checks['2022']['all_candidate_contest_votes'])
    checks['priority_2024'] = priority
    checks['zip_discrepancies'] = diffs
    checks['zip_discrepancy_note'] = 'PDF is authoritative for both baselines; no rescaling or silent ZIP edits. Differences explain neither cause nor revision chronology.'
    fields = ['rank_2024', 'county', 'county_native', 'county_fips', 'ncsbe_county_id',
        'president_2024_d', 'president_2024_r', 'president_2024_other', 'president_2024_total',
        'statewide_president_2024_pct', 'cumulative_president_2024_total', 'cumulative_president_2024_pct',
        'top15', 'smallest_80pct_set', 'research_priority', 'senate_2022_d', 'senate_2022_r',
        'senate_2022_other', 'senate_2022_total', 'rank_midterm_2022']
    fields += [k for k in rows[0] if k not in fields]
    write_csv(STATE / 'data/county-turnout.csv', [{k: r[k] for k in fields} for r in rows])
    write_csv(ROOT / 'certified-candidate-extract.csv', extracted)
    write_csv(ROOT / 'zip-county-candidate-extract.csv', zip_results['2024'] + zip_results['2022'])
    write_csv(ROOT / 'candidate-reconciliation.csv', reconciliation)
    write_csv(ROOT / 'zip-discrepancies.csv', diffs)
    table = '| Rank | County | FIPS | SBE ID | President votes 2024 | State % | Cumulative % | Senate votes 2022 | Ballots 2024 |\n'
    table += '| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
    table += ''.join(f"| {r['rank_2024']} | {r['county']} | {r['county_fips']} | {r['ncsbe_county_id']} | {r['president_2024_total']:,} | {pct(r['president_2024_total'],total,4)} | {pct(r['cumulative_president_2024_total'],total,4)} | {r['senate_2022_total']:,} | {r['ballots_cast_2024']:,} |\n" for r in rows)
    (ROOT / 'ranking-table.md').write_text(table)
    report_path = STATE / 'turnout.md'
    if report_path.exists():
        report = report_path.read_text()
        start, end = '<!-- GENERATED_RANKING_START -->', '<!-- GENERATED_RANKING_END -->'
        assert report.count(start) == report.count(end) == 1
        before, rest = report.split(start)
        _, after = rest.split(end)
        report_path.write_text(before + start + '\n\n' + table + '\n' + end + after)
    dump('checks.json', checks)
    outputs = ['../county-turnout.csv', 'certified-candidate-extract.csv', 'zip-county-candidate-extract.csv',
               'candidate-reconciliation.csv', 'zip-discrepancies.csv', 'checks.json', 'ranking-table.md']
    if report_path.exists():
        outputs.append('../../turnout.md')
    dump('output-hashes.json', {name: digest(ROOT/name) for name in outputs})
    print(json.dumps(dict(priority_2024=priority, zip_discrepancy_fields=len(diffs),
        statewide_2024=checks['2024'], statewide_2022=checks['2022']), indent=2))

if __name__ == '__main__':
    main()
