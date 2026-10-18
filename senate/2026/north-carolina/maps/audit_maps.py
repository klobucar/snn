"""Independent retained-artifact audit, using only the standard library.

Run after build_maps.py. Does not require GIS packages or network access.
Writes evidence/artifact manifests and validation.json only under maps/.
"""
from pathlib import Path
import collections
import csv
import datetime
import html.parser
import json
import math
import re
import struct
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from source_io import ROOT, read, sha

def walk_positions(c):
    if c and isinstance(c[0],(int,float)):
        yield c
    else:
        for x in c:
            yield from walk_positions(x)

def main():
    source_records=[]
    for p in sorted((ROOT/'raw').glob('*.meta.json')):
        target=p.with_name(p.name.removesuffix('.meta.json'))
        read(str(target.relative_to(ROOT)))
        meta=json.loads(p.read_text())
        meta['local_path']=str(target.relative_to(ROOT))
        source_records.append(meta)
    (ROOT/'evidence-manifest.json').write_text(json.dumps(source_records,indent=2)+'\n')
    ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
    listing=ET.fromstring(read('raw/ncsbe-precinct-list.xml'))
    assert listing.findtext('s:IsTruncated',namespaces=ns)=='false'
    objects={c.findtext('s:Key',namespaces=ns):int(c.findtext('s:Size',namespaces=ns)) for c in listing.findall('s:Contents',ns)}
    c=json.loads((ROOT/'checks.json').read_text())
    for v,info in c['vintages'].items():
        arc=ROOT/info['archive']
        assert arc.stat().st_size == objects['ShapeFiles/Precinct/'+arc.name]
        assert sha(arc.read_bytes()) == info['archive_sha256']
        with zipfile.ZipFile(arc) as z:
            assert set(z.namelist())==set(info['zip_members'])
            for member,m in info['zip_members'].items():
                b=z.read(member)
                assert sha(b)==m['sha256'] and len(b)==m['bytes']
            dbf=z.read(arc.stem+'.dbf')
            shx=z.read(arc.stem+'.shx')
            assert struct.unpack('<I',dbf[4:8])[0]==info['statewide_features']==(len(shx)-100)//8
        assert len(info['counties'])==38
    for dep in c['dependencies']:
        assert sha((ROOT.parent/dep['path']).read_bytes())==dep['sha256'],dep
    inv=list(csv.DictReader((ROOT/'county-inventory.csv').open()))
    assert len(inv)==100 and len({r['county_fips'] for r in inv})==100
    assert len({r['ncsbe_county_id'] for r in inv})==100
    priority=[r for r in inv if r['research_priority']=='1']
    assert len(priority)==38
    assert sum(int(r['president_2024_votes']) for r in inv)==5699145
    assert sum(int(r['president_2024_votes']) for r in priority)==4576486
    for vintage,column in [('2024-07-23','geometry_2024_count'),('2026-08-24','geometry_current_count')]:
        assert sum(int(r[column]) for r in inv)==c['vintages'][vintage]['statewide_features']
    units=list(csv.DictReader((ROOT/'result-unit-diagnostics.csv').open()))
    assert len({(u['county_fips'],u['year'],u['result_unit_literal']) for u in units})==len(units)
    unit_counts={year:dict(collections.Counter(u['real_precinct_flag'] for u in units if u['year']==year)) for year in ['2024','2022']}
    assert unit_counts=={'2024':{'Y':2658,'N':250},'2022':{'Y':2655,'N':322}},unit_counts
    manifest=list(csv.DictReader((ROOT/'manifest.csv').open()))
    assert len(manifest)==152
    seen=collections.Counter()
    total_vertices=0
    for m in manifest:
        p=ROOT/m['local_path']
        assert sha(p.read_bytes())==m['sha256'] and p.stat().st_size==int(m['bytes'])
        assert p.stat().st_size<40000000
        if m['format']!='GeoJSON': continue
        fc=json.loads(p.read_text())
        fs=fc['features']
        assert len(fs)==int(m['feature_count'])
        assert len({f['id'] for f in fs})==len(fs)
        assert all(f['properties']['_county_fips']==m['county_fips'] and str(f['properties']['county_id'])==m['ncsbe_county_id'] for f in fs)
        assert all(f['properties']['_snapshot']==m['geometry_vintage'] for f in fs)
        bbox=[math.inf,math.inf,-math.inf,-math.inf]
        n=0
        for f in fs:
            g=f['geometry']; assert g['type'] in ['Polygon','MultiPolygon']
            rings=g['coordinates'] if g['type']=='Polygon' else [r for poly in g['coordinates'] for r in poly]
            assert all(len(r)>=4 and r[0]==r[-1] for r in rings)
            for x,y in walk_positions(g['coordinates']):
                assert math.isfinite(x) and math.isfinite(y) and -85<x<-75 and 33<y<37
                bbox=[min(bbox[0],x),min(bbox[1],y),max(bbox[2],x),max(bbox[3],y)]
                n+=1
        assert bbox==fc['bbox']==json.loads(m['bbox'])
        assert n==c['vintages'][m['geometry_vintage']]['counties'][m['county'].upper()]['vertex_count']
        total_vertices+=n
        seen[m['geometry_vintage']]+=1
    assert dict(seen)=={'2024-07-23':38,'2026-08-24':38}
    page=json.loads(read('raw/onemap-attributes-page-0.json.gz'))
    last=json.loads(read('raw/onemap-attributes-page-1.json.gz'))
    ids=json.loads(read('raw/onemap-ids.json.gz'))['objectIds']
    returned=[f['attributes']['objectid'] for p in [page,last] for f in p['features']]
    assert len(set(ids))==len(ids)==len(returned)==2625 and set(ids)==set(returned)
    assert not last.get('exceededTransferLimit',False)
    alternatives={}
    for name,expected in [('wake',216),('union',54)]:
        attributes=json.loads(read(f'raw/{name}-attributes.json'))
        alt_ids=json.loads(read(f'raw/{name}-ids.json'))['objectIds']
        alt_count=json.loads(read(f'raw/{name}-count.json'))['count']
        returned_ids=[f['attributes']['OBJECTID'] for f in attributes['features']]
        assert len(set(alt_ids))==len(alt_ids)==len(returned_ids)==alt_count==expected
        assert set(alt_ids)==set(returned_ids)
        assert not attributes.get('exceededTransferLimit',False)
        alternatives[name]=dict(feature_count=alt_count,ids_reconciled=True)
    union_subset=json.loads(read('raw/union-alias-alternative.geojson.gz'))
    assert len(union_subset['features'])==3 and not union_subset.get('exceededTransferLimit',False)
    assert {f['properties']['OBJECTID'] for f in union_subset['features']}=={50,52,54}
    # Local index and Markdown links: resolve actual files, never guessed URLs.
    class Links(html.parser.HTMLParser):
        def __init__(self):super().__init__();self.links=[]
        def handle_starttag(self,tag,attrs):
            self.links.extend(v for k,v in attrs if k in ['href','src'])
    parser=Links();parser.feed((ROOT/'index.html').read_text())
    local_links=[(ROOT,s) for s in parser.links if not urllib.parse.urlsplit(s).scheme]
    report=ROOT.parent/'precinct-maps.md'
    if report.exists():
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',report.read_text()):
            if not urllib.parse.urlsplit(target).scheme and not target.startswith('#'):
                local_links.append((report.parent,target))
    for base,target in local_links:
        resolved=(base/urllib.parse.unquote(target.split('#')[0])).resolve()
        if resolved not in {ROOT/'validation.json',ROOT/'artifact-manifest.json'}:
            assert resolved.exists(),target
    artifacts=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(part in ['.runtime','__pycache__'] for part in p.relative_to(ROOT).parts):continue
        if p.name in ['artifact-manifest.json','validation.json']:continue
        assert p.stat().st_size<40000000,p
        artifacts.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
    (ROOT/'artifact-manifest.json').write_text(json.dumps(artifacts,indent=2)+'\n')
    result=dict(validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
        evidence_snapshots=len(source_records),source_listing_not_truncated=True,zip_crc_and_member_hashes_verified=True,
        statewide_inventory_count=100,priority_count=38,county_geojsons=76,county_svg_previews=76,
        vertices_verified=total_vertices,asset_hashes_verified=len(manifest),all_service_object_ids_reconciled=True,
        county_alternative_pagination=alternatives,
        result_units=unit_counts,local_links_checked=len(local_links),largest_file_bytes=max(x['bytes'] for x in artifacts),
        artifact_total_bytes=sum(x['bytes'] for x in artifacts),artifact_count=len(artifacts),
        report_sha256=sha(report.read_bytes()) if report.exists() else None,
        limitations=['November 2026 approval unestablished','No election-unit crosswalk or vote allocation','Geometry defects preserved; independent county-gap review unavailable'])
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    for base,target in local_links:
        assert (base/urllib.parse.unquote(target.split('#')[0])).exists(),target
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
