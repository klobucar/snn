#!/usr/bin/env python3
"""Coordinator integration audit; --first-wave does not claim a complete package."""
from pathlib import Path
from urllib.parse import unquote
import datetime, hashlib, json, re, runpy, sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
first_wave = '--first-wave' in sys.argv
for name in ('review_native_contract.py', 'reconcile_baselines.py',
             'review_historical_clarity.py', 'validate_targets.py', 'news/inspect_evidence.py'):
    runpy.run_path(str(DATA / name))
def load(name):
    return json.loads((ROOT / name).read_text())
def verify(path, entry):
    body = path.read_bytes()
    assert len(body) == entry['bytes'] < 40_000_000, path
    assert hashlib.sha256(body).hexdigest() == entry['sha256'], path

hashes = {}
for folder, expected in [('turnout', 625), ('baselines', 275)]:
    manifest = load('data/' + folder + '/asset-manifest.json')
    entries = manifest['assets']
    assert len(entries) == len({e['path'] for e in entries}) == expected
    for entry in entries:
        verify(DATA / folder / entry['path'], entry)
    hashes[folder] = expected
for reference in load('data/baselines/review-evidence.json')['references']:
    verify(DATA / 'baselines' / reference['path'], reference)
for reference in load('data/baselines/peer-reconciliation.json')['peer_artifact_hashes']:
    verify(DATA / 'baselines' / reference['path'], reference)
for reference in load('data/baselines/statistics-verification.json')['peer_artifacts']:
    verify(DATA / 'baselines' / reference['path'], reference)
turnout = load('data/turnout/validation.json')
assert turnout['status'] in ('pass_with_source_gaps', 'completed_with_retained_discrepancies')
assert turnout['county_controls']['counties_per_election'] == 99
assert turnout['county_controls']['all_county_candidate_column_sums_and_method_balances_exact']
assert turnout['native_candidate_scope']['source_differences'] == 0
assert turnout['native_candidate_scope']['per_unit_method_imbalances'] == 0
assert turnout['peer']['status'] == 'pass' and not turnout['peer']['differences']
assert turnout['sources']['count'] == 534 and turnout['sources']['all_hashes_and_sizes_verified']
assert turnout['pdf_text_derivatives']['fresh_primary_extractions_verified'] == 17
baseline = load('data/baselines/validation.json')
assert baseline['status'] == 'pass' and baseline['original_source_references_verified'] == 534
assert baseline['statistics_numeric_cells_checked'] == 2_620_128
contract = load('data/turnout/priority-set.json')
for name in ('coordinator_county_review', 'coordinator_native_review'):
    assert 'sha256' not in contract[name], 'Acceptance path must not reverse-hash its own audit.'
    assert (DATA / 'turnout' / contract[name]['path']).exists()
priority_sha = hashlib.sha256((DATA / 'turnout/priority-set.json').read_bytes()).hexdigest()
assert priority_sha == load('data/coordinator-native-contract-checks.json')['input_hashes']['turnout/priority-set.json']
assert priority_sha == '579b22b8d4f35f12d085ef8402a1bcab14e135a1577daf3ddc4f7d3f66460822'
assert load('data/coordinator-native-contract-checks.json')['constituent_objects_exactly_conserved'] == 13_558
for entry in load('data/coordinator-pdf-review.json')['previews']:
    verify(ROOT / entry['path'], entry)

documents = [ROOT / name for name in ('turnout.md', 'county-partisanship.md',
                                     'data/turnout/SCHEMA.md', 'data/baselines/SCHEMA.md')]
if not first_wave:
    runpy.run_path(str(DATA / 'review_second_wave.py'), run_name='__main__')
    source_validation = load('data/results-sources/validation.json')
    assert source_validation['status'] == 'completed_with_retained_source_gaps_and_discrepancies'
    assert source_validation['asset_manifest_sha256'] == hashlib.sha256((DATA / 'results-sources/asset-manifest.json').read_bytes()).hexdigest()
    for name, check in source_validation['checks'].items():
        assert check == 'pass' or check['status'] in ('pass', 'pass_with_explicit_conflicts'), name
    map_validation = load('maps/validation.json')
    assert map_validation['status'] == 'pass_with_retained_source_defects_and_unapproved_crosswalks'
    assert not map_validation['errors']
    assert all(check['pass_'] for check in map_validation['checks'].values())
    for entry in load('data/coordinator-second-wave-visual-review.json')['previews']:
        verify(ROOT / entry['path'], entry)
    hashes.update({'official_results':1292, 'maps':3254})
    documents.extend(ROOT / name for name in ('official-results.md', 'precinct-maps.md',
                     'data/results-sources/SCHEMA.md', 'maps/SCHEMA.md', 'local-news-results.md',
                     'live-polling-strategy.md', 'research-review.md', 'research-dispatch.md', 'README.md'))
links = 0
for document in documents:
    for dest in re.findall(r'\]\(([^)]+)\)', document.read_text()):
        dest = dest.strip().strip('<>')
        if not dest or dest.startswith(('#', 'http:', 'https:', 'mailto:', 'data:')):
            continue
        target = document.parent / unquote(dest.split('#')[0])
        declared_output = DATA / 'coordinator-integration-checks.json'
        assert target.exists() or (not first_wave and target.resolve() == declared_output.resolve()), (document, dest)
        links += 1
assert links > 0 and len(documents) == (4 if first_wave else 13)
for folder in (('turnout', 'baselines') if first_wave else ('turnout', 'baselines', 'results-sources')):
    for path in (DATA / folder).rglob('*'):
        if path.is_file():
            assert path.stat().st_size < 40_000_000 and '__pycache__' not in path.parts and path.suffix != '.pyc'
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'First-wave baselines/targets/native contract only; official-results/maps/publication pending.',
          'counties': 99, 'primary_county_contests': 297, 'candidate_method_cells': 7_484,
          'priority_counties': 41, 'constituent_objects_exactly_conserved': 13_558,
          'historical_county_HTTP_entities': 297, 'native2024_candidate_method_cells': 26_448,
          'state_scenarios': 36, 'county_targets': 3_564, 'selected_county_targets': 3_564,
          'separate_other_candidate_rows': 3_960, 'synthetic_fixed_counted_remainder_cases': 3,
          'worker_asset_hashes': hashes, 'worker_asset_hashes_total': sum(hashes.values()),
          'first_wave_relative_links': links, 'priority_contract_sha256': priority_sha,
          'turnout_validation_status': turnout['status'], 'source_discrepancies': 'Retained explicitly; numerical candidate controls match.',
          'implemented_collector': False, 'calibrated_forecast': False}
if not first_wave:
    result.update(scope='Complete four-question research package with explicit source defects and unapproved geographic crosswalks.',
                  source_validation_status=source_validation['status'], map_validation_status=map_validation['status'],
                  worker_asset_hashes=hashes, worker_asset_hashes_total=sum(hashes.values()),
                  complete_package_relative_links=links, maps=load('data/coordinator-second-wave-checks.json'))
    result.pop('first_wave_relative_links')
output = DATA / ('coordinator-first-wave-checks.json' if first_wave else 'coordinator-integration-checks.json')
if output.exists():
    previous = json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = previous['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
assert all((document.parent / unquote(dest.strip().strip('<>').split('#')[0])).exists()
           for document in documents for dest in re.findall(r'\]\(([^)]+)\)', document.read_text())
           if dest.strip() and not dest.strip().startswith(('#', 'http:', 'https:', 'mailto:', 'data:')))
print(json.dumps(result, indent=2))
