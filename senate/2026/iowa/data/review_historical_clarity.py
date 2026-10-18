#!/usr/bin/env python3
"""Coordinator audit of actual historical2024 county XML contexts and controls."""
from pathlib import Path
from collections import Counter
import csv, datetime, gzip, hashlib, io, json, zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
metadata = {r['id']: r for r in json.loads((ROOT / 'turnout/source-manifest.json').read_text())}
dependencies = {}
def original(source):
    meta = metadata[source]; stored = (ROOT / 'turnout' / meta['path']).read_bytes()
    assert meta['status'] == 200 and meta['retrieval_utc'] and meta['parent_url']
    assert len(stored) == meta['stored_bytes'] and hashlib.sha256(stored).hexdigest() == meta['stored_sha256']
    body = gzip.decompress(stored)
    assert len(body) == meta['original_bytes'] and hashlib.sha256(body).hexdigest() == meta['original_sha256']
    dependencies[source] = {'path': 'turnout/' + meta['path'], 'original_sha256': meta['original_sha256'],
                            'stored_sha256': meta['stored_sha256'], 'original_bytes': len(body), 'stored_bytes': len(stored)}
    return body
def xml(source):
    with zipfile.ZipFile(io.BytesIO(original(source))) as archive:
        assert archive.namelist() == ['detail.xml'] and archive.testzip() is None
        return ET.fromstring(archive.read('detail.xml'))
with (ROOT / 'baselines/canvass-candidate-method.csv').open(newline='') as stream:
    primary = {(r['county_fips'], r['candidate_or_metric_label'], r['native_method']): int(r['votes'])
               for r in csv.DictReader(stream) if r['year'] == '2024' and r['metric'] == 'candidate_votes'}
with (ROOT / 'county-turnout.csv').open(newline='') as stream:
    counties = list(csv.DictReader(stream))
assert len(counties) == 99
scopes = []; checked_cells = native_cells = 0; native_total = Counter()
state_method_totals = Counter()
for county in counties:
    fips = county['county_fips']; source = 'sos-2024-county-xml-' + fips
    root = xml(source)
    assert root.findtext('ElectionDate') == '11/5/2024'
    contests = [r for r in root.findall('Contest') if r.get('text') == 'President and Vice President']
    assert len(contests) == 1
    contest = contests[0]; choices = contest.findall('Choice'); assert len(choices) == 8
    candidate_names = None
    for choice in choices:
        label = choice.get('text'); candidate_total = int(choice.get('totalVotes'))
        assert candidate_total == primary[fips, label, 'Total']; checked_cells += 1
        methods = Counter()
        for vote_type in choice.findall('VoteType'):
            method = vote_type.get('name'); assert method in ('Election Day', 'Absentee')
            names = [r.get('name') for r in vote_type.findall('Precinct')]
            if candidate_names is None:
                candidate_names = names
                assert len(names) == len(set(names))
            assert candidate_names == names
            votes = [int(r.get('votes')) for r in vote_type.findall('Precinct')]
            assert sum(votes) == int(vote_type.get('votes')) == primary[fips, label, method]
            checked_cells += 1; native_cells += len(votes)
            methods[method] += sum(votes); state_method_totals[label, method] += sum(votes)
        assert set(methods) == {'Election Day', 'Absentee'} and sum(methods.values()) == candidate_total
    context = root.find('VoterTurnout')
    turnout_rows = context.findall('Precincts/Precinct')
    turnout_names = [r.get('name') for r in turnout_rows]
    status = json.loads(original('sos-2024-county-status-' + fips))
    settings = json.loads(original('sos-2024-county-settings-' + fips))
    status_names = status['P']
    assert candidate_names == status_names
    assert len(turnout_names) == len(set(turnout_names))
    assert set(turnout_names) <= set(candidate_names)
    assert len(status['B']) == len(status_names)
    missing = [name for name in candidate_names if name not in turnout_names]
    detail = {'county': county['county'], 'county_fips': fips, 'candidate_units': len(candidate_names),
              'turnout_context_units': len(turnout_names), 'status_units': len(status_names),
              'candidate_not_turnout': missing,
              'turnout_native_ballots': sum(int(r.get('ballotsCast')) for r in turnout_rows),
              'turnout_county_ballots': int(context.get('ballotsCast')),
              'status_native_ballots': sum(status['B']),
              'XML_source_clock': root.findtext('Timestamp'),
              'settings_websiteupdatedat': settings.get('websiteupdatedat')}
    assert detail['turnout_county_ballots'] == detail['status_native_ballots']
    if missing:
        assert fips == '19117' and len(missing) == 2
        assert all(name.startswith('Chariton ') and name.endswith(' ') for name in missing)
        assert detail['candidate_units'] == detail['status_units'] == 7 and detail['turnout_context_units'] == 5
        assert detail['turnout_native_ballots'] == 2_733 and detail['turnout_county_ballots'] == 4_676
    else:
        assert detail['turnout_native_ballots'] == detail['turnout_county_ballots']
    for name in ('candidate_units', 'turnout_context_units', 'status_units'):
        native_total[name] += detail[name]
    scopes.append(detail)
assert checked_cells == 2_376 and native_cells == 26_448
assert dict(native_total) == {'candidate_units': 1_653, 'turnout_context_units': 1_651, 'status_units': 1_653}
for (label, method), value in state_method_totals.items():
    assert value == primary['', label, method]
assert sum(value for (label, method), value in state_method_totals.items()) == 1_663_506
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'scope': 'Actual historical2024 XML/settings/status original-byte audit; not November2026 or a geographic crosswalk.',
          'counties': 99, 'verified_county_HTTP_entities': len(dependencies), 'primary_candidate_method_controls': checked_cells,
          'native_candidate_method_cells': native_cells, 'source_context_unit_counts': dict(native_total),
          'Lucas_scope_exception': next(r for r in scopes if r['county_fips'] == '19117'),
          'county_contexts': scopes, 'dependencies': dependencies,
          'under_over': 'Not published at native candidate-unit level in this XML; no residual allocation.'}
output = ROOT / 'coordinator-historical-clarity-checks.json'
if output.exists():
    previous = json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = previous['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('county_contexts', 'dependencies')}, indent=2))
