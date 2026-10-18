#!/usr/bin/env python3
"""Offline Alaska turnout rebuild from retained official publications.

Requires Python stdlib and pdftotext (Poppler). Does not access the network.
Districts are election-specific keys. No district/precinct joins across years.
"""
import collections
import csv
import gzip
import hashlib
import io
import json
import pathlib
import re
import subprocess
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT.parent.parent
HDS = list(range(1, 41)) + [99]
YEARS = [2024, 2022]
CANDIDATES = {
    2024: ['Harris/Walz', 'Kennedy/Shanahan', 'Oliver/Maat', 'Sonski/Onak',
           'Stein/Ware', 'Terry/Broden', 'Trump/Vance', 'West/Abdullah'],
    2022: ['Chesbro, Patricia R.', 'Kelley, Buzz A.', 'Murkowski, Lisa',
           'Tshibaka, Kelly C.', 'Write-in'],
}
COLS = {
    2024: ['harris_walz', 'kennedy_shanahan', 'oliver_maat', 'sonski_onak',
           'stein_ware', 'terry_broden', 'trump_vance', 'west_abdullah'],
    2022: ['chesbro', 'kelley', 'murkowski', 'tshibaka', 'write_in'],
}
EXPECTED = {2024: [140026, 5670, 3040, 702, 2342, 812, 184458, 1127],
            2022: [27145, 7557, 113495, 111480, 2028]}
METHODS = ['Election Day', 'Absentee', 'Early Voting', 'Question', 'Remote']


def integer(value):
    return int(value.replace(',', ''))


def source_bytes(name):
    path = ROOT / name
    if path.exists():
        return path.read_bytes()
    return gzip.decompress((ROOT / (name + '.gz')).read_bytes())


def norm(value):
    return ' '.join(value.split())


def hd_key(year, hd):
    return f'{str(year)[2:]}GENR:HD{hd:02d}'


def pdf_text(name):
    pdf = ROOT / name
    target = pdf.with_suffix('.extracted.txt')
    subprocess.run(['pdftotext', '-layout', str(pdf), str(target)], check=True)
    return target.read_text()


def csv_write(name, rows, fields=None):
    assert rows
    with pathlib.Path(name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def label_geography(label):
    if label == 'HD99 Fed Overseas Absentee':
        return 99, 'Absentee', 'federal_overseas_administrative'
    match = re.fullmatch(r'District (\d+)\s+- (Absentee|Early Voting|Question)', label)
    if match:
        return int(match[1]), match[2], 'district_administrative'
    match = re.match(r'(\d{2})-\d{3} ', label)
    assert match, label
    return int(match[1]), 'Election Day', 'physical_precinct'


def unit_pdf_key(label):
    match = re.match(r'(\d{2}-\d{3}) ', label)
    return match[1] if match else norm(label)


def first_choice2024():
    raw = list(csv.DictReader(io.StringIO(source_bytes('precinct2024.csv').decode())))
    # The only selected contest is the presidential contest, not a Senate race.
    selected = [(i + 2, r) for i, r in enumerate(raw) if r['Contest_Id'] == '4']
    assert {r['Contest_title'] for _, r in selected} == {'U.S. President / Vice President'}
    units = collections.defaultdict(list)
    for line, r in selected:
        units[r['Pct_seq_nbr']].append((line, r))
    assert len(units) == 523
    out = []
    for seq, rr in units.items():
        first = rr[0][1]
        assert len(rr) == 8
        assert [r['candidate_name'] for _, r in rr] == CANDIDATES[2024]
        assert len({r['candidate_id'] for _, r in rr}) == 8
        repeated = ['Precinct_name', 'Pct_Id', 'Reg_voters', 'Aggregation_ID',
                    'Reporting_flag', 'total_ballots', 'total_under_votes', 'total_over_votes']
        repeated += [f'{method}_{suffix}' for method in METHODS for suffix in ['ballots', 'under_votes', 'over_votes']]
        assert all(len({r[field] for _, r in rr}) == 1 for field in repeated)
        hd, method, kind = label_geography(first['Precinct_name'])
        votes = [int(r['total_votes']) for _, r in rr]
        assert all(v >= 0 for v in votes)
        ballots = int(first['total_ballots'])
        under, over = int(first['total_under_votes']), int(first['total_over_votes'])
        assert sum(votes) + under + over == ballots
        # Each total is a view of the five method columns; do not sum both views.
        for _, r in rr:
            for suffix, total in [('votes', 'total_votes'), ('ballots', 'total_ballots'),
                                  ('under_votes', 'total_under_votes'), ('over_votes', 'total_over_votes')]:
                assert sum(int(r[f'{m}_{suffix}']) for m in METHODS) == int(r[total])
        row = dict(election_id='24GENR', source_unit_key=f'24GENR:4:seq:{seq}',
                   source_label=first['Precinct_name'], native_pct_id=first['Pct_Id'],
                   native_pct_seq_nbr=seq, native_aggregation_id=first['Aggregation_ID'],
                   native_reporting_flag=first['Reporting_flag'], native_house_district=str(hd),
                   district_key=hd_key(2024, hd), unit_type=kind, method=method,
                   boundary_vintage='2024 election; April 2024 precincts / May 2023 Final Proclamation',
                   state_fips='02', county_fips='', contest_id='4',
                   contest='U.S. President / Vice President', count_stage='published first choices',
                   all_candidate_votes=sum(votes), ballots_cast=ballots,
                   registered_voters=int(first['Reg_voters']), undervotes=under, overvotes=over,
                   source_file='precinct2024.csv', source_record_start=rr[0][0],
                   source_record_end=rr[-1][0], ballot_source='precinct2024.csv')
        row.update(zip(COLS[2024], votes))
        active_methods = [m for m in METHODS if int(first[f'{m}_ballots'])]
        row['method_split_status'] = 'multiple methods in one named unit' if len(active_methods) > 1 else 'one or zero active methods'
        for m in METHODS:
            prefix = m.lower().replace(' ', '_')
            row[prefix + '_ballots'] = int(first[m + '_ballots'])
            row[prefix + '_votes'] = sum(int(r[m + '_votes']) for _, r in rr)
            row[prefix + '_undervotes'] = int(first[m + '_under_votes'])
            row[prefix + '_overvotes'] = int(first[m + '_over_votes'])
            assert row[prefix + '_votes'] + row[prefix + '_undervotes'] + row[prefix + '_overvotes'] == row[prefix + '_ballots']
        out.append(row)
    assert len({r['source_label'] for r in out}) == 523
    assert len({r['native_pct_id'] for r in out if r['native_pct_id']}) == 443
    assert sum(not r['native_pct_id'] for r in out) == 80
    return out


def first_choice2022():
    # Original export is UTF-16LE with BOM, not a UTF-8 CSV.
    rows = list(csv.reader(io.StringIO(source_bytes('precinct2022.txt').decode('utf-16')), delimiter='\t'))
    start = next(i for i, r in enumerate(rows) if r[0] == 'U.S. Senator (Vote for 1)')
    assert rows[start + 1] == ['Precinct', 'Chesbro, Patricia R. - DEM', 'Kelley, Buzz A. - REP',
                               'Murkowski, Lisa - REP', 'Tshibaka, Kelly C. - REP', 'Write-in']
    out = []
    for index in range(start + 2, len(rows)):
        r = rows[index]
        if r[0] == 'Total':
            assert [integer(v) for v in r[1:]] == EXPECTED[2022]
            break
        assert len(r) == 6
        label = r[0]
        hd, method, kind = label_geography(label)
        votes = [integer(v) for v in r[1:]]
        assert all(v >= 0 for v in votes)
        # This export provides labels, not separate ID/sequence fields.
        match = re.match(r'(\d{2}-\d{3}) ', label)
        row = dict(election_id='22GENR', source_unit_key=f'22GENR:Senator:record:{index + 1}',
                   source_label=label, native_pct_id=match[1] if match else '',
                   native_pct_seq_nbr='', native_aggregation_id='', native_reporting_flag='',
                   native_house_district=str(hd), district_key=hd_key(2022, hd),
                   unit_type=kind, method=method, boundary_vintage='2022 election reporting vintage; not crosswalked',
                   state_fips='02', county_fips='', contest_id='', contest='U.S. Senator',
                   count_stage='published first choices including Write-in', all_candidate_votes=sum(votes),
                   ballots_cast='', registered_voters='', undervotes='', overvotes='',
                   source_file='precinct2022.txt', source_record_start=index + 1,
                   source_record_end=index + 1, ballot_source=f'hd{hd}-2022.pdf')
        row.update(zip(COLS[2022], votes))
        out.append(row)
    assert len(out) == len({r['source_label'] for r in out}) == 522
    return out


def district_publication(year, hd):
    text = pdf_text(f'hd{hd}-{year}.pdf')
    assert 'OFFICIAL RESULTS' in text
    title = 'U.S. President / Vice President' if year == 2024 else 'U.S. Senator'
    start = text.index(title)
    first = text[:start]
    section = text[start:text.index('U.S. Representative')]
    total_lines = [line for line in section.splitlines() if 'State of Alaska - Total' in line]
    assert len(total_lines) == 2, (year, hd)
    numeric = []
    for line in total_lines:
        numeric.append([integer(s) for s in line.replace('State of Alaska - Total', '').split()
                        if re.fullmatch(r'[\d,]+', s)])
    assert len(numeric[0]) == 4
    assert len(numeric[1]) == (7 if year == 2024 else 4)
    ballots, registration, *candidates = numeric[0]
    candidates += numeric[1][:-1]
    assert sum(candidates) == numeric[1][-1]
    # Independently parse the turnout table before any contest.
    turnout_total = next(line for line in first.splitlines() if 'State of Alaska - Total' in line)
    turnover = [integer(s) for s in turnout_total.split() if re.fullmatch(r'[\d,]+', s)]
    assert turnover == ([registration, ballots] if year == 2024 else [registration, ballots, ballots])
    unit_ballots = {}
    if year == 2022:
        pending = None
        for line in first.splitlines():
            label_match = re.match(r'^\s*(\d{2}-\d{3}|District \d+\s+- (?:Absentee|Early Voting|Question))', line)
            if label_match:
                assert pending is None, (year, hd, pending)
                pending = norm(label_match[1])
            match = re.search(r'(?:^|\s)(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(?:\d+\.\d+%|N/A)\s*$', line)
            if pending and match:
                values = [integer(match[i]) for i in [1, 2, 3]]
                assert values[1] == values[2]
                assert pending not in unit_ballots
                unit_ballots[pending] = (values[1], values[0])
                pending = None
        assert pending is None
        if hd == 99:
            # The source label wraps over two lines; counts come from its unique total.
            unit_ballots = {'HD99 Fed Overseas Absentee': (ballots, registration)}
    return dict(ballots=ballots, registration=registration, candidates=candidates,
                total=sum(candidates), unit_ballots=unit_ballots)


def statewide_publication(year):
    text = pdf_text(f'summary{year}.pdf')
    assert 'OFFICIAL RESULTS' in text
    title = 'U.S. President / Vice President' if year == 2024 else 'U.S. Senator'
    section = text[text.index(title):text.index('U.S. Representative')]
    counts = []
    for candidate in CANDIDATES[year]:
        pattern = r'^' + re.escape(candidate) + r'\s+(?:[A-Z]+\s+)?([\d,]+)\s+\d+\.\d+%\s*$'
        match = re.search(pattern, section, flags=re.M)
        assert match, (year, candidate)
        counts.append(integer(match[1]))
    assert counts == EXPECTED[year]
    assert integer(re.search(r'Total Votes\s+([\d,]+)', section)[1]) == sum(counts)
    match = re.search(r'Times Cast\s+([\d,]+)\s*/\s*([\d,]+)', section)
    return dict(candidates=counts, total=sum(counts), ballots=integer(match[1]), registration=integer(match[2]))


def rank(rows, volume='all_candidate_votes'):
    rows.sort(key=lambda r: (-r[volume], r.get('source_unit_key', r.get('district_key'))))
    statewide = sum(r[volume] for r in rows)
    cumulative = 0
    cutoff = None
    for i, r in enumerate(rows, 1):
        cumulative += r[volume]
        r.update(rank=i, statewide_pct=f'{100 * r[volume] / statewide:.8f}',
                 cumulative_votes=cumulative, cumulative_pct=f'{100 * cumulative / statewide:.8f}', top15=int(i <= 15))
        if cutoff is None and 5 * cumulative >= 4 * statewide:
            cutoff = i
    for r in rows:
        r['smallest_80pct_set'] = int(r['rank'] <= cutoff)
    assert sum(r[volume] for r in rows[:cutoff - 1]) * 5 < 4 * statewide
    assert sum(r[volume] for r in rows[:cutoff]) * 5 >= 4 * statewide
    return cutoff


class MapLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = {}

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        url = dict(attrs).get('href', '')
        match = re.search(r'/HD(\d+)_May2023Final_Maps\.pdf$', url)
        if match:
            self.links[int(match[1])] = url


def main():
    candidates_check, district_checks, methods_check, method_candidate_checks = [], [], [], []
    checks = dict(parser_version='1', research_date_utc='2026-10-18',
                  research_date_america_chicago='2026-10-17', cross_year_joins=False)
    district_outputs, unit_outputs = {}, {}
    for year, units in [(2024, first_choice2024()), (2022, first_choice2022())]:
        statewide = statewide_publication(year)
        districts = []
        for hd in HDS:
            official = district_publication(year, hd)
            group = [r for r in units if r['native_house_district'] == str(hd)]
            assert group
            if year == 2022:
                assert {unit_pdf_key(r['source_label']) for r in group} == set(official['unit_ballots']), (year, hd)
                for r in group:
                    r['ballots_cast'], r['registered_voters'] = official['unit_ballots'][unit_pdf_key(r['source_label'])]
                    assert r['all_candidate_votes'] <= r['ballots_cast']
            counts = [sum(r[c] for r in group) for c in COLS[year]]
            assert counts == official['candidates'], (year, hd, counts, official)
            assert sum(r['ballots_cast'] for r in group) == official['ballots']
            assert sum(r['registered_voters'] for r in group) == official['registration']
            row = dict(election_id=f'{str(year)[2:]}GENR', district_key=hd_key(year, hd),
                       native_house_district=str(hd), reporting_geography=f'House District {hd}' if hd != 99 else 'HD99 Fed Overseas Absentee',
                       geography_type='house_district' if hd != 99 else 'federal_overseas_administrative',
                       boundary_vintage=group[0]['boundary_vintage'], state_fips='02', county_fips='',
                       contest=group[0]['contest'], count_stage=group[0]['count_stage'],
                       all_candidate_votes=sum(counts), ballots_cast=official['ballots'],
                       registered_voters=official['registration'],
                       undervotes=sum(r['undervotes'] for r in group) if year == 2024 else '',
                       overvotes=sum(r['overvotes'] for r in group) if year == 2024 else '',
                       constituent_units=len(group),
                       source_summary_url=f'https://www.elections.alaska.gov/results/{str(year)[2:]}GENR/HD{hd}.pdf',
                       source_summary_file=f'hd{hd}-{year}.pdf')
            row.update(zip(COLS[year], counts))
            for method in METHODS:
                prefix = method.lower().replace(' ', '_')
                row[prefix + '_label_category_votes'] = sum(r['all_candidate_votes'] for r in group if r['method'] == method)
                row[prefix + '_label_category_ballots'] = sum(r['ballots_cast'] for r in group if r['method'] == method)
                row[prefix + '_votes'] = sum(r[prefix + '_votes'] for r in group) if year == 2024 else ''
                row[prefix + '_ballots'] = sum(r[prefix + '_ballots'] for r in group) if year == 2024 else ''
            districts.append(row)
            for candidate, actual, expected in zip(CANDIDATES[year], counts, official['candidates']):
                district_checks.append(dict(election_id=row['election_id'], district_key=row['district_key'],
                                            measure=candidate, constituent_sum=actual, official_hd_pdf=expected, difference=actual - expected))
            for measure in ['ballots', 'registration']:
                field = {'ballots': 'ballots_cast', 'registration': 'registered_voters'}[measure]
                actual = sum(r[field] for r in group)
                district_checks.append(dict(election_id=row['election_id'], district_key=row['district_key'],
                                            measure=measure, constituent_sum=actual, official_hd_pdf=official[measure], difference=actual - official[measure]))
        assert len(districts) == len({r['district_key'] for r in districts}) == 41
        assert {int(r['native_house_district']) for r in districts} == set(HDS)
        for field, expected in [('all_candidate_votes', statewide['total']), ('ballots_cast', statewide['ballots']),
                                ('registered_voters', statewide['registration'])]:
            assert sum(r[field] for r in districts) == expected
        for candidate, col, expected in zip(CANDIDATES[year], COLS[year], statewide['candidates']):
            actual = sum(r[col] for r in units)
            assert actual == expected
            candidates_check.append(dict(election_id=f'{str(year)[2:]}GENR', candidate=candidate, unit_sum=actual,
                                         official_statewide_pdf=expected, difference=actual - expected))
        cutoff = rank(districts)
        rank(units)
        ballot_order = sorted(districts, key=lambda r: (-r['ballots_cast'], r['district_key']))
        ballot_cum, ballot_cutoff = 0, None
        for i, r in enumerate(ballot_order, 1):
            ballot_cum += r['ballots_cast']
            r['ballots_rank'] = i
            r['ballots_statewide_pct'] = f"{100 * r['ballots_cast'] / statewide['ballots']:.8f}"
            r['ballots_cumulative_total'] = ballot_cum
            r['ballots_cumulative_pct'] = f"{100 * ballot_cum / statewide['ballots']:.8f}"
            if ballot_cutoff is None and ballot_cum * 5 >= statewide['ballots'] * 4:
                ballot_cutoff = i
        for r in ballot_order:
            r['ballots_top15'] = int(r['ballots_rank'] <= 15)
            r['ballots_smallest_80pct_set'] = int(r['ballots_rank'] <= ballot_cutoff)
        assert sum(r['ballots_cast'] for r in ballot_order[:ballot_cutoff - 1]) * 5 < statewide['ballots'] * 4
        priority_keys = {r['district_key'] for r in districts[:cutoff]}
        for r in units:
            r['district_in_priority_set'] = int(r['district_key'] in priority_keys)
        district_outputs[year], unit_outputs[year] = districts, units
        checks[str(year)] = dict(statewide=statewide, district_count=41, reporting_units=len(units),
                                 unit_types=dict(collections.Counter(r['unit_type'] for r in units)),
                                 top15=[r['district_key'] for r in districts[:15]], top15_votes=sum(r['all_candidate_votes'] for r in districts[:15]),
                                 smallest_80pct_set=[r['district_key'] for r in districts[:cutoff]], cutoff_rank=cutoff,
                                 before_cutoff_votes=sum(r['all_candidate_votes'] for r in districts[:cutoff - 1]),
                                 cutoff_votes=sum(r['all_candidate_votes'] for r in districts[:cutoff]))
        checks[str(year)]['ballots_ranking'] = dict(top15=[r['district_key'] for r in ballot_order[:15]],
                                                    top15_ballots=sum(r['ballots_cast'] for r in ballot_order[:15]),
                                                    smallest_80pct_set=[r['district_key'] for r in ballot_order[:ballot_cutoff]],
                                                    cutoff_ballots=sum(r['ballots_cast'] for r in ballot_order[:ballot_cutoff]),
                                                    before_cutoff_ballots=sum(r['ballots_cast'] for r in ballot_order[:ballot_cutoff - 1]))
        if year == 2024:
            checks[str(year)]['mixed_method_units'] = [{key: r[key] for key in ['source_unit_key', 'source_label', 'election_day_ballots', 'election_day_votes', 'early_voting_ballots', 'early_voting_votes']} for r in units if r['method_split_status'].startswith('multiple')]
        for method in METHODS:
            group = [r for r in units if r['method'] == method]
            prefix = method.lower().replace(' ', '_')
            methods_check.append(dict(election_id=f'{str(year)[2:]}GENR', method=method,
                                      label_category_units=len(group), label_category_votes=sum(r['all_candidate_votes'] for r in group),
                                      label_category_ballots=sum(r['ballots_cast'] for r in group),
                                      contributing_method_units=sum(r[prefix + '_ballots'] > 0 for r in units) if year == 2024 else '',
                                      all_candidate_votes=sum(r[prefix + '_votes'] for r in units) if year == 2024 else '',
                                      ballots_cast=sum(r[prefix + '_ballots'] for r in units) if year == 2024 else '',
                                      undervotes=sum(r[prefix + '_undervotes'] for r in units) if year == 2024 else '',
                                      overvotes=sum(r[prefix + '_overvotes'] for r in units) if year == 2024 else '',
                                      label_minus_actual_votes=0, label_minus_actual_ballots=0,
                                      method_statewide_publication='precinct2024.csv (each method column checked)' if year == 2024 else 'summary2022.txt'))

    # Explicit official statewide 2022 method totals and under/overvote reconciliation.
    summary_rows = list(csv.reader(io.StringIO(source_bytes('summary2022.txt').decode('utf-16')), delimiter='\t'))
    for method in METHODS:
        source = [r for r in summary_rows if len(r) > 15 and r[4].strip() == 'U.S. Senator' and r[6] == method]
        assert len(source) == 1
        source = source[0]
        row = next(r for r in methods_check if r['election_id'] == '22GENR' and r['method'] == method)
        row['undervotes'], row['overvotes'] = integer(source[10]), integer(source[12])
        row['ballots_cast'] = integer(source[7])
        method_votes = 0
        for candidate, col in zip(CANDIDATES[2022], COLS[2022]):
            # This formatted export repeats candidate/counting-group presentations.
            # Deduplicate identical values; do not add repeated display rows.
            cells = {integer(r[24]) for r in summary_rows if len(r) > 24 and r[4].strip() == 'U.S. Senator' and r[20].strip() == candidate and r[23] == method}
            assert len(cells) == 1, (candidate, method, cells)
            published = cells.pop()
            actual = sum(r[col] for r in unit_outputs[2022] if r['method'] == method)
            assert actual == published
            method_votes += published
            method_candidate_checks.append(dict(election_id='22GENR', method=method, candidate=candidate,
                                                 unit_label_category_sum=actual, official_statewide_method=published, difference=actual - published))
        row['all_candidate_votes'] = method_votes
        assert row['all_candidate_votes'] + row['undervotes'] + row['overvotes'] == row['ballots_cast']
    for year in YEARS:
        group = [r for r in methods_check if r['election_id'] == f'{str(year)[2:]}GENR']
        for r in group:
            r['label_minus_actual_votes'] = r['label_category_votes'] - r['all_candidate_votes']
            r['label_minus_actual_ballots'] = r['label_category_ballots'] - r['ballots_cast']
        assert sum(r['all_candidate_votes'] for r in group) == checks[str(year)]['statewide']['total']
        assert sum(r['ballots_cast'] for r in group) == checks[str(year)]['statewide']['ballots']
        checks[str(year)]['methods'] = group
        checks[str(year)]['undervotes'] = sum(r['undervotes'] for r in group)
        checks[str(year)]['overvotes'] = sum(r['overvotes'] for r in group)

    # RCV is a separate publication/population; never overwrite first choices.
    rcv_text = pdf_text('senate-rcv2022.pdf')
    rounds = []
    for number in [1, 2, 3]:
        section = rcv_text.split(f'Round {number}\n', 1)[1].split('Non Transferable Total', 1)
        body = section[0]
        values = {}
        for candidate in CANDIDATES[2022][:-1]:
            match = re.search(r'^' + re.escape(candidate) + r'\s+([\d,]+)\s+[\d.]+%', body, re.M)
            assert match
            values[candidate] = integer(match[1])
        metadata = {}
        for label in ['Continuing Ballots Total', 'Blanks', 'Exhausted', 'Overvotes', 'Remainder Points']:
            metadata[label] = integer(re.search(re.escape(label) + r'\s+([\d,]+)', body)[1])
        metadata['Non Transferable Total'] = integer(re.match(r'\s*([\d,]+)', section[1])[1])
        assert sum(values.values()) == metadata['Continuing Ballots Total']
        assert metadata['Blanks'] + metadata['Exhausted'] + metadata['Overvotes'] == metadata['Non Transferable Total']
        assert metadata['Continuing Ballots Total'] + metadata['Non Transferable Total'] == 266797
        rounds.append(dict(round=number, candidates=values, **metadata))
    assert rounds[2]['candidates']['Murkowski, Lisa'] == 136330
    assert rounds[2]['candidates']['Tshibaka, Kelly C.'] == 117534
    checks['rcv2022'] = dict(source='senate-rcv2022.pdf', population=266797,
                            first_choice_publication_ballots=267047, rcv_minus_first_choice_ballots=-250,
                            coverage_difference_status='unresolved in this turnout evidence; no rescaling or splicing',
                            rounds=rounds)
    (ROOT / 'senate-rcv2022-parsed.json').write_text(json.dumps(checks['rcv2022'], indent=2) + '\n')

    maps = MapLinks()
    maps.feed(source_bytes('district-maps.html').decode())
    assert set(maps.links) == set(range(1, 41))
    priority = dict(election_id='24GENR', ranking_denominator='all eight published presidential candidate votes',
                    statewide_votes=338177, cutoff_votes=checks['2024']['cutoff_votes'],
                    cutoff_rank=checks['2024']['cutoff_rank'], boundaries='April 2024 precincts / May 2023 Final Proclamation',
                    current_november2026_map_approval='not established', districts=[])
    for r in district_outputs[2024][:checks['2024']['cutoff_rank']]:
        hd = int(r['native_house_district'])
        priority['districts'].append(dict(rank=r['rank'], district_key=r['district_key'], native_house_district=str(hd),
                                           votes=r['all_candidate_votes'], source_summary_url=r['source_summary_url'],
                                           source_summary_file=r['source_summary_file'], map_source_url=maps.links[hd],
                                           constituent_unit_keys=[u['source_unit_key'] for u in unit_outputs[2024] if u['district_key'] == r['district_key']]))
    (ROOT / 'priority-set.json').write_text(json.dumps(priority, indent=2) + '\n')
    csv_write(STATE / 'data/county-turnout.csv', district_outputs[2024])
    csv_write(ROOT / 'district-turnout-2022.csv', district_outputs[2022])
    for year in YEARS:
        csv_write(ROOT / f'reporting-units-{year}.csv', unit_outputs[year])
    csv_write(ROOT / 'candidate-reconciliation.csv', candidates_check)
    csv_write(ROOT / 'district-reconciliation.csv', district_checks)
    csv_write(ROOT / 'method-reconciliation.csv', methods_check)
    csv_write(ROOT / 'method-candidate-reconciliation-2022.csv', method_candidate_checks)
    checks['district_candidate_and_denominator_comparisons'] = len(district_checks)
    checks['statewide_candidate_comparisons'] = len(candidates_check)
    checks['statewide_2022_method_candidate_comparisons'] = len(method_candidate_checks)

    # Validate saved primary response bytes and HTTP headers, including explicit failed attempts.
    manifest = json.loads((ROOT / 'evidence-manifest.json').read_text())
    successful = 0
    failures = []
    for evidence in manifest:
        if evidence['curl_exit_code']:
            failures.append(dict(file=evidence['file'], error=evidence['error']))
            continue
        path = ROOT / evidence.get('stored_file', evidence['file'])
        assert hashlib.sha256(source_bytes(evidence['file'])).hexdigest() == evidence['sha256'], path
        if 'stored_sha256' in evidence:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['stored_sha256']
        header = ROOT / (evidence['file'] + '.headers')
        assert hashlib.sha256(header.read_bytes()).hexdigest() == evidence['headers_sha256']
        assert evidence['http']['ssl_verify_result'] == 0
        assert 200 <= evidence['http']['response_code'] < 300
        successful += 1
    checks['evidence'] = dict(successful_verified_responses=successful, retained_failures=failures)
    (ROOT / 'checks.json').write_text(json.dumps(checks, indent=2) + '\n')
    table = '| Rank | Native reporting geography | President votes 2024 | State % | Cumulative % | Ballots 2024 |\n| ---: | --- | ---: | ---: | ---: | ---: |\n'
    for r in district_outputs[2024]:
        table += f"| {r['rank']} | {r['reporting_geography']} | {r['all_candidate_votes']:,} | {float(r['statewide_pct']):.4f} | {float(r['cumulative_pct']):.4f} | {r['ballots_cast']:,} |\n"
    (ROOT / 'ranking-table.md').write_text(table)
    report = STATE / 'turnout.md'
    if report.exists():
        prose = report.read_text()
        begin, end = '<!-- BEGIN GENERATED RANKING -->', '<!-- END GENERATED RANKING -->'
        assert prose.count(begin) == prose.count(end) == 1
        prose = prose.split(begin)[0] + begin + '\n' + table + end + prose.split(end)[1]
        report.write_text(prose)
    table22 = '| Rank | Native 2022 reporting geography | Senate first choices | Ballots 2022 | Cumulative % |\n| ---: | --- | ---: | ---: | ---: |\n'
    for r in district_outputs[2022]:
        table22 += f"| {r['rank']} | {r['reporting_geography']} | {r['all_candidate_votes']:,} | {r['ballots_cast']:,} | {float(r['cumulative_pct']):.4f} |\n"
    (ROOT / 'ranking-table-2022.md').write_text(table22)
    print(json.dumps(dict(result='PASS', reporting_units_2024=len(unit_outputs[2024]), reporting_units_2022=len(unit_outputs[2022]),
                          district_groups_per_year=41, president_2024_votes=338177, senate_2022_first_choices=261705,
                          priority_2024=checks['2024']['smallest_80pct_set'], priority_votes_2024=checks['2024']['cutoff_votes'],
                          statewide_candidate_comparisons=13, district_candidate_denominator_comparisons=len(district_checks),
                          method_candidate_comparisons_2022=len(method_candidate_checks),
                          evidence=checks['evidence']), indent=2))


if __name__ == '__main__':
    main()
