#!/usr/bin/env python3
"""Coordinator checks independent raw SHP parsing, source bytes and native scopes."""
from pathlib import Path
import collections, csv, datetime, gzip, hashlib, io, json, struct, zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / 'maps'
SOURCES = ROOT / 'data/results-sources'
def sha(b): return hashlib.sha256(b).hexdigest()
def j(p): return json.loads(p.read_bytes())
def lines(p): return [json.loads(s) for s in gzip.decompress(p.read_bytes()).splitlines()]
def verify(p, e):
    b = p.read_bytes()
    assert len(b) == e['bytes'] < 40_000_000 and sha(b) == e['sha256'], p
    return b
def map_body(m):
    if m.get('parts'):
        b = b''.join(verify(MAPS / p['path'], p) for p in m['parts'])
    else:
        stored = (MAPS / m['path']).read_bytes()
        assert len(stored) == m['stored_bytes'] and sha(stored) == m['stored_sha256']
        b = gzip.decompress(stored) if m['stored_encoding'] == 'gzip' else stored
    assert len(b) == m['entity_bytes'] and sha(b) == m['entity_sha256']
    return b

def main():
    assets = {}
    for folder, name, count in [(MAPS, 'asset-hashes.json', 3254),
                                (SOURCES, 'asset-manifest.json', 1292)]:
        manifest = j(folder / name)
        assert len(manifest['assets']) == count
        assert len({x['path'] for x in manifest['assets']}) == count
        for e in manifest['assets']: verify(ROOT / e['path'], e)
        assets[folder.name] = count
    contract = j(ROOT / 'data/turnout/priority-set.json')
    counties = contract['all_counties']
    expected = [(c['county_fips'], year, context, i + 1, obj)
                for c in counties for year, contexts in c['native_constituents'].items()
                for context, objects in contexts.items() if isinstance(objects, list)
                for i, obj in enumerate(objects)]
    diag = json.loads(gzip.decompress((MAPS / 'inventory/constituent-diagnostics.json.gz').read_bytes()))['ordered_exact_source_constituents']
    assert [(d['county_fips'], d['year'], d['context'], d['context_ordinal'], d['original_constituent']) for d in diag] == expected
    native = lines(SOURCES / 'native-constituent-inventory.jsonl.gz')
    assert [(d['county_fips'], d['year'], d['scope'], d['literal_object']) for d in native] == [(f, y, c, o) for f, y, c, i, o in expected]
    assert len(diag) == len(native) == 13_558
    assert all(not d['approved_polygon_matches'] and d['vote_allocation'] is None for d in diag)
    inventory = j(MAPS / 'inventory/counties.json')
    assert [c['county_fips'] for c in inventory] == [c['county_fips'] for c in counties]
    assert [c['native_source_roster'] for c in inventory] == [c['native_constituents']['2024']['native_source_roster'] for c in counties]
    assert all(c['accepted_reference_asset_ids'] and (MAPS / c['index_download']).is_file() for c in inventory[:41])

    records = j(MAPS / 'source-manifest.json')['records']
    by = {m['source_id']: m for m in records}
    assert len(by) == len(records) == 653
    for m in records: map_body(m)
    layers = features = vertices = parts = members = 0
    shapetypes = collections.Counter()
    # Read ESRI binary headers and polygon record bodies directly, independently
    # of the worker's pyshp decoder. Do not repair or reinterpret native rings.
    for a in j(MAPS / 'geometry-audit.json')['archives']:
        z = zipfile.ZipFile(io.BytesIO(map_body(by[a['source_id']])))
        assert z.testzip() is None
        names = {n.lower(): n for n in z.namelist()}
        for e in a['members']:
            b = z.read(e['name']); members += 1
            assert len(b) == e['bytes'] and sha(b) == e['sha256']
        for l in a['layers']:
            layers += 1; base = l['shp_member'][:-4]
            shp, shx, dbf = [z.read(names[(base + '.' + ext).lower()]) for ext in ('shp','shx','dbf')]
            assert struct.unpack_from('>i', shp, 0)[0] == 9994
            assert struct.unpack_from('>i', shp, 24)[0] * 2 == len(shp)
            assert struct.unpack_from('<i', shp, 28)[0] == 1000
            out = json.loads(gzip.decompress((MAPS / l['native_derivative']).read_bytes()))
            position = 100; rows = []; index = []
            while position < len(shp):
                recno, words = struct.unpack_from('>2i', shp, position)
                data = shp[position+8:position+8+words*2]
                st = struct.unpack_from('<i', data)[0]; shapetypes[st] += 1
                assert st == 5, (l['layer_key'], st)
                nparts, npoints = struct.unpack_from('<2i', data, 36)
                rings = list(struct.unpack_from('<'+'i'*nparts, data, 44))
                xy = [list(struct.unpack_from('<2d', data, 44+nparts*4+i*16)) for i in range(npoints)]
                assert len(data) == 44 + nparts*4 + npoints*16
                rows.append((recno, rings, xy)); index.append((position//2, words))
                position += 8 + words*2; vertices += npoints; parts += nparts
            assert position == len(shp)
            assert [struct.unpack_from('>2i', shx, off) for off in range(100, len(shx), 8)] == index
            assert len(rows) == struct.unpack_from('<I', dbf, 4)[0] == len(out['features']) == l['parsed_records']
            for (recno, rings, xy), d in zip(rows, out['features']):
                assert d['record_ordinal'] == recno and d['parts'] == rings and d['points'] == xy
                assert d['z'] is None and d['m'] is None and d['ordinal_is_native_id'] is False
            features += len(rows)
    assert (layers, features, vertices) == (253, 2615, 803565)
    assert len(j(MAPS / 'geometry-audit.json')['archives']) == 252

    ledger = j(SOURCES / 'acquisition-ledger.json'); originals = 0
    own = {a['id']: a for a in ledger}; assert len(own) == len(ledger) == 626
    for a in ledger:
        if a.get('status') is None:
            assert a.get('error') and not a['parts']; continue
        for e in a['stored_objects']: verify(SOURCES / e['path'], e)
        b = b''.join(gzip.decompress((SOURCES / p).read_bytes()) for p in a['parts'])
        assert len(b) == a['original_bytes'] and sha(b) == a['original_sha256']; originals += 1
    assert originals == 624
    a = own['vendor-current-xml']
    z = zipfile.ZipFile(io.BytesIO(b''.join(gzip.decompress((SOURCES / p).read_bytes()) for p in a['parts'])))
    assert z.testzip() is None
    xml = ET.fromstring(z.read('detail.xml'))
    assert xml.findtext('ElectionDate') == '6/2/2026' and 'Primary' in xml.findtext('ElectionName')
    candidates = []; raw_positions = []
    fips = {c['county']: c['county_fips'] for c in counties}
    for ci, contest in enumerate(xml.findall('Contest'), 1):
        if not contest.get('text', '').startswith('United States Senator'): continue
        for qi, choice in enumerate(contest.findall('Choice'), 1):
            total = 0
            for vi, method in enumerate(choice.findall('VoteType'), 1):
                units = method.findall('County')
                assert len(units) == 99 and {u.get('name') for u in units} == set(fips)
                assert sum(int(u.get('votes')) for u in units) == int(method.get('votes'))
                total += int(method.get('votes'))
                for ui, unit in enumerate(units, 1):
                    raw_positions.append(dict(source_id=a['id'], source_xml_path=f'Contest[{ci}]/Choice[{qi}]/VoteType[{vi}]/County[{ui}]', county_fips=fips[unit.get('name')], native_county_attributes=dict(unit.attrib), contest_attributes=dict(contest.attrib), choice_attributes=dict(choice.attrib), method_attributes=dict(method.attrib)))
            assert total == int(choice.get('totalVotes'))
            candidates.append((choice.get('text'), total))
    assert raw_positions == lines(SOURCES / 'primary-2026-native-positions.jsonl.gz') and len(raw_positions) == 1188
    scopes = list(csv.DictReader((ROOT / 'data/official-results-sources.csv').open()))
    assert [x['county_fips'] for x in scopes] == [x['county_fips'] for x in counties]
    assert [x['investigation_scope'] for x in scopes] == ['deep_priority']*41 + ['discovery_only']*58
    counts = collections.Counter(d['diagnostic_status'] for d in diag)
    result = dict(status='pass_with_retained_source_defects', checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), owned_asset_hashes=assets, exact_constituent_objects=13558, county_rosters=99, priority_assets=41, map_HTTP_entities=653, original_ZIP_members_hashed=members, original_binary_polygon_layers=layers, original_binary_polygon_records=features, original_binary_vertices=vertices, original_binary_parts=parts, official_HTTP_entities=originals, official_requests=626, independent_primary_candidate_method_county_cells=len(raw_positions), primary_candidate_totals=candidates, map_diagnostic_statuses=dict(counts), approved_crosswalks=0, implemented_collector=False, calibrated_forecast=False)
    output = ROOT / 'data/coordinator-second-wave-checks.json'
    if output.exists():
        previous = j(output)
        if {k:v for k,v in previous.items() if k!='checked_utc'} == {k:v for k,v in result.items() if k!='checked_utc'}: result['checked_utc'] = previous['checked_utc']
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
if __name__ == '__main__': main()
