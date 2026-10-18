#!/usr/bin/env python3
"""Independent coordinator county controls and exact research-dispatch priority."""
from pathlib import Path
from collections import defaultdict
import csv, datetime, gzip, hashlib, io, json, re, runpy

ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / 'preflight_primary_counties.py'))

def load(name):
    return json.loads((ROOT / name).read_text())

def records(name):
    with (ROOT / name).open(newline='') as stream:
        return list(csv.DictReader(stream))

dependencies = {}
def pin(name):
    path = ROOT / name
    dependencies[name] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

sources = load('baselines/sources.json')
census = next(r for r in sources if r['id'] == 'census-county-codes')
stored = (ROOT / 'baselines' / census['path']).read_bytes()
assert len(stored) == census['stored_bytes'] and hashlib.sha256(stored).hexdigest() == census['stored_sha256']
body = gzip.decompress(stored)
assert len(body) == census['original_bytes'] and hashlib.sha256(body).hexdigest() == census['original_sha256']
fips = {r['COUNTYNAME'].removesuffix(' County'): r['STATEFP'] + r['COUNTYFP']
        for r in csv.DictReader(io.StringIO(body.decode()), delimiter='|') if r['STATE'] == 'IA'}
assert len(fips) == 99 and fips['Page'] == '19145' and fips['Henry'] == '19087'

primary = load('coordinator-primary-preflight.json')
turnout = records('county-turnout.csv')
baselines = records('county-baselines.csv')
assert len(turnout) == len(baselines) == 99
turnout_by = {r['county_fips']: r for r in turnout}
baseline_by = {r['county_fips']: r for r in baselines}
assert set(turnout_by) == set(baseline_by) == set(fips.values())
county_cells = 0
for contest, evidence in primary['contests'].items():
    year = contest[:4]
    prefix = year + ('_president' if year == '2024' else '_senate')
    tprefix = 'pres2024' if year == '2024' else 'sen' + year
    long = records('turnout/canvass-candidate-method.csv')
    for original in evidence['counties']:
        county = original['native_county']; county_fips = fips[county]
        a = turnout_by[county_fips]; b = baseline_by[county_fips]
        assert a['county'] == b['county'] == a['native_county_label'] == b['native_county_label'] == county
        counts = original['column_counts']
        retained = sorted((r for r in long if r['year'] == year and r['county_fips'] == county_fips and r['native_method'] == 'Total'), key=lambda r: int(r['source_column']))
        assert [int(r['votes']) for r in retained] == counts
        county_cells += len(counts)
        expected = {'d': original['d'], 'r': original['r'],
                    'candidate_writein_votes': original['candidate_writein_votes'],
                    'generic_writein_votes': counts[-4], 'named_candidate_votes': sum(counts[:-4]),
                    'under_votes': counts[-3], 'over_votes': counts[-2],
                    'reported_contest_total': counts[-1]}
        for field, value in expected.items():
            assert int(b[prefix + '_' + field]) == value, (county, contest, field)
        for field, key in [('candidate_generic_writein_votes', 'candidate_writein_votes'),
                           ('generic_writein_votes', 'generic_writein_votes'),
                           ('under_votes', 'under_votes'), ('over_votes', 'over_votes'),
                           ('reported_contest_total', 'reported_contest_total')]:
            assert int(a[tprefix + '_' + field]) == expected[key]
    assert evidence['original_sha256'] == next(r for r in sources if r['id'] == 'sos-' + year + '-canvass')['original_sha256']

own = records('baselines/canvass-candidate-method.csv')
peer = records('turnout/canvass-candidate-method.csv')
def key(row):
    return row['year'], row['county_fips'] or '19', row['native_method'], row['source_column']
other = {key(r): r for r in peer}
assert len(own) == len(peer) == len(other) == 7_484
for row in own:
    check = other[key(row)]
    assert row['source_id'] == check['source_id']
    assert row['votes'] == check['votes'] and row['section_text_line'] == check['section_text_line']
    label = row['candidate_or_metric_label'] + (', ' + row['party_header'] if row['party_header'] else '')
    assert label == check['candidate_or_metric_label']
    assert re.sub(r'Page\s+\d+\s+of\s+\d+.*$', '', row['raw_line']) == check['raw_line']
method_cells = defaultdict(dict)
for row in peer:
    method_cells[row['year'], row['county_fips'], row['source_column']][row['native_method']] = int(row['votes'])
for (year, county, column), methods in method_cells.items():
    if county == '19' and year == '2020':
        assert set(methods) == {'Total'}
    else:
        assert set(methods) == {'Election Day', 'Absentee', 'Total'}
        assert methods['Election Day'] + methods['Absentee'] == methods['Total']
for (year, county, column), methods in method_cells.items():
    if county != '19':
        continue
    for method, control in methods.items():
        assert sum(v[method] for (y, c, col), v in method_cells.items() if y == year and col == column and c != '19') == control

ranked = sorted(turnout, key=lambda r: (-int(r['pres2024_candidate_generic_writein_votes']), r['county_fips']))
assert ranked == turnout
denominator = sum(int(r['pres2024_candidate_generic_writein_votes']) for r in ranked)
assert denominator == 1_663_506
assert sum(int(r['pres2024_generic_writein_votes']) for r in ranked) == 6_657
running = 0; priority = []
for rank, row in enumerate(ranked, 1):
    value = int(row['pres2024_candidate_generic_writein_votes'])
    member = running * 5 < denominator * 4
    running += value
    assert int(row['rank_2024']) == int(baseline_by[row['county_fips']]['rank_2024']) == rank
    assert int(row['cumulative_candidate_generic_writein_votes']) == running
    assert row['in_minimum80'] == baseline_by[row['county_fips']]['priority80'] == str(member)
    if member:
        priority.append(row['county_fips'])
contract = load('turnout/priority-set.json')
independent = load('baselines/priority.json')
assert len(priority) == 41 and priority == contract['priority_county_fips'] == independent['ordered_fips'][:41]
assert [r['county_fips'] for r in ranked] == independent['ordered_fips'] == [r['county_fips'] for r in contract['all_counties']]
assert sum(int(r['pres2024_candidate_generic_writein_votes']) for r in ranked[:15]) == 991_869
assert sum(int(r['pres2024_candidate_generic_writein_votes']) for r in ranked[:40]) == 1_322_507
assert sum(int(r['pres2024_candidate_generic_writein_votes']) for r in ranked[:41]) == 1_332_107
assert ranked[40]['county_fips'] == '19087' and int(ranked[40]['pres2024_candidate_generic_writein_votes']) == 9_600
assert 1_322_507 * 5 < denominator * 4 <= 1_332_107 * 5
keys = ''.join('IA:' + value + '\n' for value in priority)
(ROOT / 'coordinator-priority-keys.txt').write_text(keys)

for name in ('county-turnout.csv', 'county-baselines.csv', 'turnout/SCHEMA.md',
             'turnout/priority-set.json', 'turnout/canvass-candidate-method.csv',
             'baselines/canvass-candidate-method.csv', 'baselines/peer-reconciliation.json'):
    pin(name)
peer_checks = load('baselines/peer-reconciliation.json')
assert peer_checks['status'] == 'pass'
for field, expected in [('canvass_all_cells', 7_484), ('full_priority_order', 99),
                        ('native_candidate_cells', 42_728), ('native_unit_rows', 3_512),
                        ('native_registration_ballot_cells', 12_694), ('turnout_report_fields', 300)]:
    check = peer_checks[field]
    assert check['status'] == 'pass' and not check['differences']
    assert check['our_rows'] == check['peer_rows'] == expected

native_review = load('coordinator-native-contract-checks.json')
assert native_review['status'] == 'pass' and native_review['constituent_objects_exactly_conserved'] == 13_558
assert native_review['input_hashes']['turnout/priority-set.json'] == hashlib.sha256((ROOT / 'turnout/priority-set.json').read_bytes()).hexdigest()
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Accepted county counts/order and exact research-dispatch priority with all source-scoped historical constituents conserved. No geographic or November approval.',
          'counties': 99, 'primary_county_contests': 297, 'independent_primary_Total_cells': county_cells,
          'peer_full_candidate_method_cells': 7_484, 'denominator': denominator, 'generic_writein_marks': 6_657,
          'top15_votes': 991_869, 'priority_count': 41, 'priority_votes': 1_332_107, 'preceding_votes': 1_322_507,
          'crossing': {'county': 'Henry', 'county_fips': '19087', 'votes': 9_600},
          'ordered_priority_keys_sha256': hashlib.sha256(keys.encode()).hexdigest(),
          'peer_native_cells': 42_728, 'peer_native_units': 3_512, 'peer_registration_ballot_cells': 12_694,
          'source_scoped_gaps': ['Generic Write-in marks are not established named-valid write-ins.',
                                'Canvass vs turnout-report ED/Absentee2024 differs by +7/-7 with same total; no cause inferred.',
                                '2020 statistical age bins exceed printed statewide registration total by2.',
                                'Historical2024 Clarity recovered for all99 counties; Lucas candidate/status and turnout contexts remain distinct.'],
          'native_constituent_objects_conserved': 13_558,
          'input_hashes': dependencies}
output = ROOT / 'coordinator-baseline-reconciliation.json'
if output.exists():
    previous = json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = previous['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'input_hashes'}, indent=2))
