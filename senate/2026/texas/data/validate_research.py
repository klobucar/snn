#!/usr/bin/env python3
"""Offline coordinator integration audit; worker source/map audits are prerequisites."""
from pathlib import Path
from collections import Counter
from itertools import zip_longest
from urllib.parse import unquote
import csv, datetime, gzip, hashlib, json, re, runpy

ROOT = Path(__file__).resolve().parents[1]

def load(rel):
    return json.loads((ROOT / rel).read_text())

def rows(rel):
    path = ROOT / rel
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', newline='') as stream:
        return list(csv.DictReader(stream))

def verify(path, entry):
    body = path.read_bytes()
    assert len(body) == entry['bytes'] < 40_000_000, path
    assert hashlib.sha256(body).hexdigest() == entry['sha256'], path

for script in ('reconcile_baselines.py', 'validate_targets.py',
               'review_setup_sources.py', 'review_map_subsets.py',
               'news/inspect_evidence.py'):
    runpy.run_path(str(ROOT / 'data' / script))

manifests = {}
for name, expected in (
    ('data/turnout/asset-manifest.json', 486),
    ('data/baselines/asset-manifest.json', 80),
    ('data/results-sources/asset-manifest.json', 620),
    ('maps/asset-hashes.json', 862),
):
    entries = load(name)['assets']
    assert len(entries) == len({e['path'] for e in entries}) == expected, name
    for entry in entries:
        verify(ROOT / entry['path'], entry)
    manifests[name] = len(entries)

contract = load('data/turnout/priority-set.json')
groups = contract['groups']
assert len(groups) == 254
keys = [g['dispatch_key'] for g in groups]
priority = (ROOT / 'data/coordinator-priority-keys.txt').read_text().splitlines()
assert len(priority) == 34 and keys[:34] == priority == contract['priority_keys']
assert len(set(keys)) == 254
assert sum(g['votes'] for g in groups) == 11_291_854
assert sum(g['votes'] for g in groups[:15]) == 7_369_697
assert sum(g['votes'] for g in groups[:33]) == 9_018_686
assert sum(g['votes'] for g in groups[:34]) == 9_076_868
assert groups[33]['county_fips'] == '48329' and groups[33]['votes'] == 58_182

sources = rows('data/official-results-sources.csv')
mapped = rows('maps/inventory/all-counties.csv')
assert [r['dispatch_key'] for r in sources] == [r['dispatch_key'] for r in mapped] == keys
assert [r['dispatch_key'] for r in load('data/results-sources/priority-index.json')] == priority
for group, source, mapping in zip(groups, sources, mapped):
    for field in ('county_fips', 'dispatch_key'):
        assert source[field] == mapping[field] == group[field]
    assert int(source['rank']) == int(mapping['rank']) == group['rank']
    assert source['priority'] == mapping['priority80'] == str(int(group['priority80']))
    assert int(mapping['senate_2024_total']) == group['votes']
    assert source['research_scope'] == ('individual_priority_inspection' if group['priority80'] else 'discovery_inventory_only')
    assert source['state_election_id'] == '53815' and source['state_contest_id'] == '5075'
    for field in ('november_native_units', 'remaining_valid_senate_votes',
                  'measured_update_interval_seconds', 'count_timestamp_timezone'):
        assert source[field] == '', (group['dispatch_key'], field)
    assert mapping['current_November_boundary_approval'] == 'not established'

compat = rows('maps/inventory/reporting-unit-compatibility.csv.gz')
native = rows('data/results-sources/native-unit-identities.csv.gz')
inputs = [
    ('historical-OE', rows('data/baselines/native-units.csv.gz'), 31_702),
    ('primary-historical', rows('data/turnout/primary-native-units.csv.gz'), 4_276),
    ('official-discovery', native, 12_701),
]
assert len(compat) == 48_679
offset = 0
statuses = Counter()
for kind, originals, expected in inputs:
    assert len(originals) == expected
    for original, retained in zip(originals, compat[offset:offset + expected]):
        assert retained['inventory'] == kind
        assert json.loads(retained['input_row_json']) == original
        assert retained['source_id'] == original['source_id']
        assert retained['county_fips'] == original['literal_county_fips' if kind == 'historical-OE' else 'county_fips']
        assert retained['native_id'] == original['native_id' if kind == 'official-discovery' else 'native_unit_id']
        assert retained['status'] in ('unknown', 'administrative/no-polygon', 'ambiguous', 'source conflict')
        statuses[retained['status']] += 1
        if kind == 'official-discovery':
            assert retained['observation_class'] == original['observation_class']
    offset += expected
assert dict(statuses) == {'unknown': 33_462, 'administrative/no-polygon': 623,
                         'ambiguous': 6_527, 'source conflict': 8_067}
grayson = [r for r in native if r['source_id'] == 'county-48181-office-follow1-sample']
assert len(grayson) == 42 and sum(int(r['occurrences']) for r in grayson) == 546
assert all(r['county_fips'] == '48181' and r['election_id'] == '2026-03-03'
           and r['unit_kind'] == 'pdf_precinct_label'
           and r['observation_class'] == 'older_election_excluded' for r in grayson)
assert sum(int(r['occurrences']) for r in native) == 170_013

expected_components = (
    (group, kind, ordinal, component)
    for group in groups
    for field, kind in [('native_constituents', 'source-native'),
                        ('derived_vtd_constituents', 'derived-VTD')]
    for ordinal, component in enumerate(group[field])
)
accepted = rows('maps/inventory/accepted-constituents.csv.gz')
assert len(accepted) == 45_944
for expected, actual in zip_longest(expected_components, accepted):
    assert expected is not None and actual is not None
    group, kind, ordinal, component = expected
    assert actual['dispatch_key'] == group['dispatch_key']
    assert actual['county_fips'] == group['county_fips']
    assert int(actual['rank']) == group['rank']
    assert actual['priority80'] == str(group['priority80'])
    assert actual['component_class'] == kind and int(actual['component_ordinal']) == ordinal
    assert json.loads(actual['component_json']) == component
    assert actual['status'] != 'matched'

native_hashes = {
    'native-unit-identities.csv.gz': '425f67998803ab3e64be410739083f2deabc1995052f484252bd159f4e5c0b61',
    'native-unit-observations.csv.gz': '81e6a8ad4fa554303d85ef59099468ae99cd806fc3cab578567e9d29c3a3ad5c',
    'native-field-schemas.json': 'da8ca595801613076760494e89b93db0bf90c90b45805e499073c2b326fd22d2',
    'native-inventory-summary.json': '5b0f61e3621ff0c78653d2379403b8c709e3728701920b922ada2316441cc908',
}
for name, expected in native_hashes.items():
    assert hashlib.sha256((ROOT / 'data/results-sources' / name).read_bytes()).hexdigest() == expected
for entry in load('maps/read-only-references.json')['references']:
    verify(ROOT / 'maps' / entry['path'], entry)
for name in ('data/turnout/validation.json', 'data/baselines/validation.json',
             'data/results-sources/validation.json', 'maps/validation.json'):
    assert load(name)['status'].lower() == 'pass', name

links = 0
for document in ROOT.rglob('*.md'):
    for dest in re.findall(r'\]\(([^)]+)\)', document.read_text()):
        dest = dest.strip().strip('<>')
        if not dest or dest.startswith(('#', 'http:', 'https:', 'mailto:', 'data:')):
            continue
        target = (document.parent / unquote(dest.split('#')[0])).resolve()
        # This audit writes its own linked result after all checks pass.
        assert target == ROOT / 'data/coordinator-checks.json' or target.exists(), (document, dest)
        links += 1
assert links >= 200, links
files = [p for p in ROOT.rglob('*') if p.is_file()]
assert not any('__pycache__' in p.parts or p.suffix == '.pyc' for p in files)
assert all(p.stat().st_size < 40_000_000 for p in files)
result = {
    'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'scope': 'Integrated four-question research package; no collector or calibrated forecast.',
    'counties': 254, 'priority_counties': 34, 'baseline_rows': 1_016,
    'candidate_county_cells': 6_604, 'primary_state_controls': 26,
    'state_scenarios': 21, 'county_target_rows': 5_334,
    'selected_county_requirements': 5_334, 'synthetic_remainder_cases': 17,
    'artifact_hashes_checked': manifests, 'worker_artifact_hashes': sum(manifests.values()),
    'compatibility_rows_full_input_JSON_checked': len(compat),
    'accepted_constituent_objects_checked': len(accepted),
    'official_native_source_positions': 170_013,
    'compatibility_status_counts': dict(statuses), 'approved_crosswalks': 0,
    'Grayson_older_primary_labels': 42, 'Grayson_preserved_header_appearances': 546,
    'priority_map_ZIPs_binary_checked': 136, 'original_map_vertices': 18_050_402,
    'Markdown_relative_links': links, 'news_snapshots': load('data/news/inspection.json')['snapshots'],
    'all_files_below_bytes': 40_000_000,
    'limitations': 'Source discrepancies, partial finer coverage, test/older elections, local access gaps, current geography, outstanding counts, vote-arrival cadence and SB2753 applicability remain documented.'
}
output = ROOT / 'data/coordinator-checks.json'
if output.exists():
    previous = json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = previous['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
