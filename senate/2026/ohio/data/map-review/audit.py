#!/usr/bin/env python3
"""Offline coordinator audit of alternative map-source research; no network."""
from pathlib import Path
import datetime, gzip, hashlib, io, json, struct, zipfile

ROOT = Path(__file__).resolve().parent
def sha(b): return hashlib.sha256(b).hexdigest()
manifest = json.loads((ROOT / 'manifest.json').read_text())
assert len(manifest) == len({r['id'] for r in manifest}) == 15
raw = {}
for r in manifest:
    stored = (ROOT / r['asset']).read_bytes()
    b = gzip.decompress(stored)
    assert sha(stored) == r['stored_sha256']
    assert sha(b) == r['raw_sha256'] and len(b) == r['bytes']
    assert r['retrieved_at_utc'] and r['url'] and (r.get('headers') or r.get('raw_headers'))
    raw[r['id']] = b
findings = {}
for key, expected in [('richland-geopolitical-shapefile', 36), ('richland-county-district-shapefile', 8)]:
    with zipfile.ZipFile(io.BytesIO(raw[key])) as z:
        assert z.testzip() is None
        members = {Path(n).suffix.lower(): n for n in z.namelist() if Path(n).suffix.lower() in ('.shp', '.shx', '.dbf')}
        assert set(members) == {'.shp', '.shx', '.dbf'}
        dbf = z.read(members['.dbf'])
        count, header, width = struct.unpack('<IHH', dbf[4:12])
        fields = []
        for pos in range(32, header - 1, 32):
            f = dbf[pos:pos+32]
            fields.append((f[:11].split(b'\0')[0].decode(), f[16]))
        records = []
        for i in range(count):
            row = dbf[header+i*width:header+(i+1)*width]
            assert row[:1] == b' '
            offset = 1; record = {}
            for name, length in fields:
                record[name] = row[offset:offset+length].decode('utf-8', errors='replace').strip(); offset += length
            records.append(record)
        assert len(records) == expected
        findings[key] = {'records': expected, 'fields': [f[0] for f in fields], 'attributes': records,
                         'voting_precinct_layer': False,
                         'reason': 'city/township/county boundaries' if expected == 36 else 'ward/annex boundaries; incomplete precinct coverage'}
minimal = json.loads(raw['tuscarawas-minimal-geometry'])
assert len(minimal['features']) == 1 and 'geometry' not in minimal['features'][0]
assert minimal['features'][0]['attributes']['PRECT_NA'] == 'DOVER CORP 1A'
png = (ROOT / 'tuscarawas-official-render.png').read_bytes()
assert png == raw['tuscarawas-official-render']
assert png[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', png[16:24]) == (2000, 2600)
assert sha(png) == 'c08224550273054f43636f6fe4bbd1fd72bf84c4ddab0f5802af808049ab33e8'
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'requests': len(manifest), 'findings': findings, 'richland_precinct_gap_repaired': False,
          'original_richland_pdf_downloaded': False, 'browser_render_file_downloaded': False,
          'tuscarawas_render': {'bytes': len(png), 'dimensions': [2000, 2600], 'sha256': sha(png),
                               'native_crs': 'EPSG:3734', 'vector_geometry_supplied': False,
                               'boundary_approval': 'unestablished', 'visually_inspected': True}}
(ROOT / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k != 'findings'}, indent=2))
