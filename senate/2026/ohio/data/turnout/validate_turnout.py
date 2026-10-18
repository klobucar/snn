#!/usr/bin/env python3
"""Offline source, reconstruction and independent tabular validation."""
import csv
from collections import Counter, defaultdict
import datetime as dt
from fractions import Fraction
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile
from build_turnout import ROOT, STATE, build, js, csv_bytes

def read_csv(path):
    op = gzip.open if str(path).endswith('.gz') else open
    with op(path, 'rt', newline='') as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    checks = {}
    manifest = json.loads((ROOT/'source-manifest.json').read_text())
    assert len({r['path'] for r in manifest}) == len(manifest)
    for r in manifest:
        p = ROOT/r['path']
        assert p.stat().st_size == r['bytes'] and sha(p) == r['sha256'], p
        b = gzip.decompress(p.read_bytes()) if p.name.endswith('.gz') else p.read_bytes()
        assert len(b) == r['uncompressed_bytes']
        assert hashlib.sha256(b).hexdigest() == r['sha256_original'], p
        assert dt.datetime.fromisoformat(r['retrieved_utc']).utcoffset() == dt.timedelta(0)
        assert r['headers'] and r['requested_url'] and r['final_url']
        if r['status'] == 200 and p.suffix == '.xlsx':
            with ZipFile(p) as z:
                assert z.testzip() is None
        if r['status'] in [403, 404]:
            assert b'html' in b[:200].lower()
    checks['source_bytes_hashes_http_utc'] = {'passed': True, 'sources': len(manifest),
        'status_counts': dict(Counter(str(r['status']) for r in manifest))}
    products = build()
    for path, body in products.items():
        assert (ROOT/path).read_bytes() == body, path
    checks['deterministic_reconstruction'] = {'passed': True, 'products': len(products)}
    rows = read_csv(STATE/'data/county-turnout.csv')
    assert len(rows) == 88 and len({r['county_fips'] for r in rows}) == 88
    assert all(re.fullmatch(r'39\d{3}', r['county_fips']) for r in rows)
    assert all(r['county'] == r['county_native_id'] for r in rows)
    assert [int(r['rank_2024_senate']) for r in rows] == list(range(1,89))
    assert rows == sorted(rows, key=lambda r: (-int(r['senate_2024_votes']), r['county_fips']))
    total = sum(int(r['senate_2024_votes']) for r in rows)
    assert total == 5704620
    assert sum(Fraction(r['senate_2024_state_share_fraction']) for r in rows) == 1
    assert sum(int(r['in_top15']) for r in rows) == 15
    assert sum(int(r['in_minimum80']) for r in rows) == 32
    cumulative = 0
    for r in rows:
        cumulative += int(r['senate_2024_votes'])
        assert int(r['senate_2024_cumulative_votes']) == cumulative
        assert int(r['in_top15']) == (int(r['rank_2024_senate']) <= 15)
        assert int(r['in_minimum80']) == (int(r['rank_2024_senate']) <= 32)
        for field, value in r.items():
            if field.startswith(('voting_method_', 'undervotes_', 'overvotes_')):
                assert value == ''
    assert sum(int(r['senate_2024_votes']) for r in rows[:15]) == 3525320
    n31 = sum(int(r['senate_2024_votes']) for r in rows[:31])
    n32 = n31+int(rows[31]['senate_2024_votes'])
    assert n31 == 4542798 and n32 == 4581738
    assert 5*n31 < 4*total <= 5*n32
    checks['all88_exact_weights_order_top15_minimum80'] = {'passed': True, 'top15_votes':3525320,
        'first31_votes':n31, 'minimum80_votes':n32, 'minimum80_count':32, 'denominator':total}
    candidates = read_csv(ROOT/'county-candidate-votes.csv')
    assert len(candidates) == 2464
    grouped = defaultdict(Counter)
    by_county = defaultdict(Counter)
    candidate_keys = set()
    for r in candidates:
        key = (r['election_date'],r['contest_key'],r['county_fips'],r['candidate_native_label'])
        assert key not in candidate_keys
        candidate_keys.add(key)
        grouped[(r['election_date'][:4],r['contest_key'])][r['candidate_native_label']] += int(r['votes'])
        by_county[r['county_fips']][f"{r['contest_key']}_{r['election_date'][:4]}_votes"] += int(r['votes'])
    for r in rows:
        assert all(int(r[k]) == v for k,v in by_county[r['county_fips']].items())
    controls = read_csv(ROOT/'state-candidate-reconciliation.csv')
    assert len(controls) == 28
    for r in controls:
        assert int(r['county_sum']) == int(r['certified_statewide_votes'])
        assert int(r['county_minus_state']) == 0
        assert grouped[(r['year'],r['contest_key'])][r['candidate_native_label']] == int(r['county_sum'])
    clerk_checks = []
    for year in [2024,2022]:
        clerk_text = STATE/f'data/baselines/house-{year}.txt'
        text = clerk_text.read_text()
        for r in controls:
            if r['year'] != str(year) or r['contest_key'] != 'senate':
                continue
            name = re.sub(r'\s*\([^)]*\)\*?$', '', r['candidate_native_label']).strip()
            pattern = r'\s+'.join(re.escape(t) for t in name.split()) + r',[^\n]*?([\d,]+)\s*$'
            match = re.search(pattern, text, re.M)
            assert match, (year, name)
            value = int(match.group(1).replace(',',''))
            assert value == int(r['county_sum']), (year,name,value,r['county_sum'])
            clerk_checks.append({'year':year,'candidate_native_label':r['candidate_native_label'],
                'county_sum':int(r['county_sum']),'house_clerk_votes':value,'difference':0})
    (ROOT/'house-clerk-senate-reconciliation.csv').write_bytes(csv_bytes(clerk_checks))
    checks['independent_house_clerk_senate_controls'] = {'passed':True,'candidate_controls':len(clerk_checks),
        'source_files':{str((STATE/f'data/baselines/house-{y}.txt').relative_to(STATE)):sha(STATE/f'data/baselines/house-{y}.txt') for y in [2024,2022]},
        'source_urls':['https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf',
                       'https://clerk.house.gov/member_info/electionInfo/2022/statistics2022.pdf'],
        'note':'Read-only reuse of primary PDFs and pdftotext extractions retained by partisanship worker; original PDF retrieval/status/hash metadata is adjacent to its PDF.'}
    precinct_checks = read_csv(ROOT/'county-precinct-candidate-reconciliation.csv')
    assert len(precinct_checks) == 2464
    for r in precinct_checks:
        wi = '(WI)' in r['candidate_native_label']
        if wi:
            assert r['precinct_observed_sum'] == '' and int(r['precinct_native_export_sum']) == 0
        else:
            assert int(r['precinct_observed_sum']) == int(r['summary_votes'])
            assert int(r['native_export_minus_summary']) == 0
    checks['all_county_candidate_state_reconciliation'] = {'passed':True, 'county_candidate_rows':len(candidates),
        'state_candidate_controls':len(controls), 'writein_residuals':{'2024_senate':640,'2024_president':2771,'2022_senate':1739}}
    priority = json.loads((ROOT/'priority-set.json').read_text())
    assert priority['ordered_county_keys_all88'] == [r['county_fips'] for r in rows]
    assert priority['ordered_priority_county_keys'] == [r['county_fips'] for r in rows[:32]]
    unit_counts = {}
    for year, expected, ballot_control, reg_control in [(2024,8878,5851387,8159946),(2022,8933,4201368,8029950)]:
        units = read_csv(ROOT/f'reporting-units-{year}.csv.gz')
        assert len(units) == expected
        unit_keys = {r['unit_key'] for r in units}
        assert len(unit_keys) == len(units)
        assert len({r['county_fips'] for r in units}) == 88
        assert sum(int(r['ballots_counted']) for r in units) == ballot_control
        assert sum(int(r['registered_voters']) for r in units) == reg_control
        unit_counties = defaultdict(Counter)
        for r in units:
            assert r['unit_key'] == f"{r['election_date']}|{r['county_fips']}|{r['precinct_code_native']}"
            unit_counties[r['county_fips']]['ballots'] += int(r['ballots_counted'])
            unit_counties[r['county_fips']]['registration'] += int(r['registered_voters'])
            unit_counties[r['county_fips']]['units'] += 1
            assert r['voting_method'] == r['undervotes'] == r['overvotes'] == ''
        for r in rows:
            assert unit_counties[r['county_fips']]['ballots'] == int(r[f'ballots_counted_{year}'])
            assert unit_counties[r['county_fips']]['registration'] == int(r[f'registered_voters_{year}'])
            assert unit_counties[r['county_fips']]['units'] == int(r[f'native_reporting_units_{year}'])
        saved_keys = {u['unit_key'] for c in priority['county_records'] for u in c['reporting_units'][str(year)]['units']}
        assert saved_keys == unit_keys
        detail = read_csv(ROOT/f'precinct-candidates-{year}.csv.gz')
        expected_candidate_count = 21 if year == 2024 else 7
        assert len(detail) == expected*expected_candidate_count
        counts = Counter()
        for r in detail:
            assert r['unit_key'] in unit_keys
            counts[r['unit_key']] += 1
            if '(WI)' in r['candidate_native_label']:
                assert r['votes_observed'] == '' and int(r['native_export_value']) == 0
            else:
                assert int(r['votes_observed']) == int(r['native_export_value'])
        assert set(counts.values()) == {expected_candidate_count}
        unit_counts[str(year)] = {'reporting_units':expected, 'precinct_candidate_records':len(detail),
                                 'ballots_counted':ballot_control,'registered_voters':reg_control}
    checks['native_units_full_candidate_coverage_and_no_double_counting'] = {'passed':True,'years':unit_counts}
    comparisons = json.loads((ROOT/'ranking-comparisons.json').read_text())
    for metric, info in comparisons.items():
        assert len(info['rows']) == 88
        assert sum(r['votes'] for r in info['rows']) == info['statewide_denominator']
        k = info['minimum80_count']
        assert 5*sum(r['votes'] for r in info['rows'][:k-1]) < 4*info['statewide_denominator']
        assert 5*sum(r['votes'] for r in info['rows'][:k]) >= 4*info['statewide_denominator']
        assert set(info['minimum80_county_keys']) == set(priority['ordered_priority_county_keys'])
    checks['independent_volume_rankings'] = {'passed':True,'metrics':list(comparisons),'same80_geography':True}
    # Read-only reconciliation with the other worker. No sibling outputs are edited.
    sibling = STATE/'data/county-baselines.csv'
    sibling_candidates = STATE/'data/baselines/candidate-votes.csv'
    diffs = []
    if sibling.exists() and sibling_candidates.exists():
        other = read_csv(sibling)
        table = {(r['comparison'],r['county_fips']):r for r in other}
        for r in rows:
            for metric in ['2024_senate','2024_president','2022_senate']:
                q = table[(metric,r['county_fips'])]
                fields = {f"{metric.split('_')[1]}_{metric[:4]}_votes": 'all_candidate_votes',
                          f'ballots_counted_{metric[:4]}':'ballots_counted_or_total_voters',
                          f'registered_voters_{metric[:4]}':'registered_voters',
                          f'native_reporting_units_{metric[:4]}':'native_precinct_count'}
                for our_field, their_field in fields.items():
                    delta = int(r[our_field])-int(q[their_field])
                    diffs.append({'comparison':metric,'county_fips':r['county_fips'],'county':r['county'],
                        'field':our_field,'turnout_value':r[our_field],'partisanship_value':q[their_field],'difference':delta})
                    assert delta == 0, diffs[-1]
                assert r['county_native_id'] == q['native_county_name']
        theirs = {(r['comparison'],r['county_fips'],r['source_candidate_label']):r for r in read_csv(sibling_candidates)}
        for r in candidates:
            key = (r['election_date'][:4]+'_'+r['contest_key'],r['county_fips'],r['candidate_native_label'])
            assert int(r['votes']) == int(theirs[key]['votes'])
        other_priority = json.loads((STATE/'data/baselines/priority-set.json').read_text())
        assert other_priority['counties'] == [r['county'] for r in rows[:32]]
        (ROOT/'partisanship-reconciliation.csv').write_bytes(csv_bytes(diffs))
        checks['read_only_partisanship_reconciliation'] = {'passed':True, 'count_comparisons':len(diffs),
            'candidate_cells':len(candidates),'same_ordered32':True,'different_cells':0,
            'source_hashes':{str(p.relative_to(STATE)):sha(p) for p in [sibling,sibling_candidates,STATE/'data/baselines/priority-set.json']}}
    else:
        raise AssertionError('Required independent partisanship files not yet present')
    links = re.findall(r'\]\(([^)]+)\)', (STATE/'turnout.md').read_text())
    local_links = [l for l in links if not re.match(r'\w+://',l) and not l.startswith('#')]
    assert all((STATE/l.split('#')[0]).exists() or l == 'data/turnout/validation.json' for l in local_links)
    assets = list(ROOT.rglob('*'))+[STATE/'turnout.md',STATE/'data/county-turnout.csv']
    assets = [p for p in assets if p.is_file() and '__pycache__' not in p.parts]
    assert all(p.stat().st_size < 40*1024*1024 for p in assets)
    checks['relative_links_and_asset_bounds'] = {'passed':True, 'local_links':len(local_links),
        'files':len(assets), 'largest_bytes':max(p.stat().st_size for p in assets)}
    report = {'validation_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'passed':True,'checks':checks,
        'substantive_gaps':['precinct write-in allocation unavailable','voting-method and under/over counts not published in these statewide workbooks',
                            '2026 reporting-unit and approved boundary crosswalk unverified','no tested 2026 live feed']}
    (ROOT/'validation.json').write_bytes(js(report))
    assert all((STATE/l.split('#')[0]).exists() for l in local_links)
    artifacts = list(ROOT.rglob('*'))+[STATE/'turnout.md',STATE/'data/county-turnout.csv']
    artifacts = [p for p in artifacts if p.is_file() and '__pycache__' not in p.parts and p.name != 'artifact-manifest.json']
    (ROOT/'artifact-manifest.json').write_bytes(js({'files':[
        {'path':str(p.relative_to(STATE)), 'bytes':p.stat().st_size, 'sha256':sha(p)}
        for p in sorted(artifacts)], 'scope':'Turnout-owned files only; this manifest excludes itself.'}))
    assert all(p.stat().st_size < 40*1024*1024 for p in artifacts+[ROOT/'artifact-manifest.json'])
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
