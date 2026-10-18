#!/usr/bin/env python3
"""Check every accepted historical constituent against its source-scoped inventory."""
from pathlib import Path
from collections import Counter, defaultdict
import csv, datetime, hashlib, json

ROOT = Path(__file__).resolve().parent
def load(name):
    return json.loads((ROOT / name).read_text())
def rows(name):
    with (ROOT / name).open(newline='') as stream:
        return list(csv.DictReader(stream))
paths = ('turnout/native-units.csv', 'turnout/statistics-units.csv',
         'turnout/clarity-2024-native-units.csv', 'turnout/clarity-2024-status-units.csv',
         'turnout/clarity-2024-county-candidate-method.csv', 'turnout/clarity-county-roster.json')
native = rows(paths[0]); stats = rows(paths[1]); xml = rows(paths[2]); status = rows(paths[3]); controls = rows(paths[4])
roster = {r['county_fips']: r for r in load(paths[5])}
assert len(native) == 3_512 and len(stats) == 4_990 and len(xml) == 3_304 and len(status) == 1_653
assert len(roster) == 99 and len(controls) == 2_376
contract = load('turnout/priority-set.json')
assert len(contract['all_counties']) == 99 and len(contract['priority_county_fips']) == 41
counts = Counter(); objects = 0
for county in contract['all_counties']:
    fips = county['county_fips']
    assert set(county['native_constituents']) == {'2024', '2022', '2020'}
    for year, contexts in county['native_constituents'].items():
        expected_stats = [r for r in stats if r['county_fips'] == fips and r['year'] == year]
        assert contexts['registration_statistics_units'] == expected_stats
        counts['statistics_' + year] += len(expected_stats); objects += len(expected_stats)
        if year != '2024':
            expected_units = [r for r in native if r['county_fips'] == fips and r['year'] == year]
            ordinary = [r for r in expected_units if r['unit_kind'] != 'source_county_total']
            administrative = [r for r in expected_units if r['unit_kind'] == 'source_county_total']
            assert contexts['candidate_reporting_units'] == ordinary
            assert contexts['candidate_administrative_controls'] == administrative
            counts['candidate_' + year] += len(ordinary); counts['administrative_' + year] += len(administrative)
            objects += len(expected_units)
        else:
            ordinary = [r for r in xml if r['county_fips'] == fips and r['source_xml_path'].startswith('Contest')]
            turnout = [r for r in xml if r['county_fips'] == fips and r['source_xml_path'].startswith('VoterTurnout/')]
            status_context = [r for r in status if r['county_fips'] == fips]
            assert contexts['candidate_reporting_units'] == ordinary
            assert contexts['turnout_context_units'] == turnout
            assert contexts['status_context_units'] == status_context
            assert all(r['source_contest_key'] == '' for r in turnout)
            assert contexts['native_source_roster'] == roster[fips]
            assert contexts['candidate_administrative_controls'] == [{'source_id': 'sos-2024-county-xml-' + fips,
                'scope': 'county Choice totalVotes and VoteType votes', 'extract': 'clarity-2024-county-candidate-method.csv'}]
            assert len([r for r in controls if r['county_fips'] == fips]) == 24
            counts['candidate_2024'] += len(ordinary); counts['turnout_context_2024'] += len(turnout)
            counts['status_context_2024'] += len(status_context); counts['administrative_2024'] += 1
            objects += len(ordinary) + len(turnout) + len(status_context) + 1
        assert contexts['crosswalk_to_2026_status'] == 'unavailable/unapproved'
assert counts['candidate_2024'] == counts['status_context_2024'] == counts['candidate_2022'] == 1_653
assert counts['turnout_context_2024'] == 1_651 and counts['candidate_2020'] == 1_661
assert all(counts['administrative_' + year] == 99 for year in ['2024', '2022', '2020'])
assert sum(value for key, value in counts.items() if key.startswith('statistics_')) == 4_990
assert objects == 13_558
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'counties': 99, 'priority_counties': 41, 'constituent_objects_exactly_conserved': objects,
          'source_scoped_counts': dict(counts), 'native_county_rosters_exactly_conserved': 99,
          'approved_crosswalks': 0, 'input_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
              for p in paths + ('turnout/priority-set.json',)},
          'scope': 'Exact inventory-object conservation only. Distinct historical contexts and root turnout blank contest keys retained; no deduplication, spatial allocation or current approval.'}
output = ROOT / 'coordinator-native-contract-checks.json'
if output.exists():
    old = json.loads(output.read_text())
    if {k:v for k,v in old.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = old['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'input_hashes'}, indent=2))
