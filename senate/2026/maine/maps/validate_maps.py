#!/usr/bin/env python3
"""Offline independent integrity/coverage checks; no network, repair or allocation."""
import collections,csv,datetime,gzip,hashlib,html.parser,json,math,pathlib,re,zipfile
ROOT=pathlib.Path(__file__).resolve().parent;STATE=ROOT.parent
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):
    b=p.read_bytes();return gzip.decompress(b) if p.suffix=='.gz' else b
def vertices(coords):
    if coords and isinstance(coords[0],(int,float)):
        assert len(coords)==2 and all(math.isfinite(n) for n in coords)
        assert -180<=coords[0]<=180 and -90<=coords[1]<=90
        return 1
    return sum(vertices(x) for x in coords)
class Links(html.parser.HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if d.get('id'):self.ids.add(d['id'])
        for k in ['href','src']:
            if d.get(k):self.links.append(d[k])
def main():
    (ROOT/'validation.json').write_text(json.dumps({'status':'in_progress','meaning':'The validator replaces this record with pass only after all checks succeed.'},indent=2)+'\n')
    inputs={'data/county-turnout.csv':'0d0852ce0029561dec0d764f52272b07c88c329e4f8eb5d4a946ed41f33569be','data/turnout/priority-keys.txt':'086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'}
    for p,h in inputs.items():assert sha((STATE/p).read_bytes())==h,p
    contract=json.loads((STATE/'data/turnout/priority-set.json').read_text());units=json.loads((ROOT/'unit-inventory.json').read_text())
    assert len(units)==512 and [u['native_key'] for u in units]==[u['native_key'] for u in contract['all_unit_coverage']]
    for u,c in zip(units,contract['all_unit_coverage']):
        for k in c:assert u[k]==c[k],(u['native_key'],k)
    pr=[u for u in units if u['priority']];assert len(pr)==164
    keys=''.join(u['native_key']+'\n' for u in pr).encode();assert keys==(STATE/'data/turnout/priority-keys.txt').read_bytes()
    assert sum(u['senate_votes'] for u in units)==821072
    assert sum(u['senate_votes'] for u in units[:15])==215627
    assert sum(u['senate_votes'] for u in units[:163])==656778
    assert sum(u['senate_votes'] for u in pr)==658029
    assert pr[-1]['native_name']=='Pownal' and pr[-1]['senate_votes']==1251
    adm=pr[21];assert adm['native_name']=='STATE UOCAVA' and adm['senate_votes']==6434
    assert adm['matched_source_ids']==[] and not adm['county_code'] and not adm['county_fips'] and 'geojson' not in adm and 'preview' not in adm
    assert adm['classification']=='administrative, no polygon appropriate'
    acquisitions=json.loads((ROOT/'acquisitions.json').read_text());responses=0
    for k,r in acquisitions.items():
        p=ROOT/r['path'];stored=p.read_bytes();body=read(p)
        assert sha(stored)==r['stored_sha256'] and len(stored)==r['stored_bytes'],k
        assert sha(body)==r['original_sha256'] and len(body)==r['original_bytes'],k
        assert r['retrieved_utc'] and r['url'] and r['headers'] is not None and r['redirects'] is not None
        if p.suffix=='.pdf':assert r['status']==200 and body.startswith(b'%PDF'),k
        if p.suffix=='.zip':assert r['status']==200 and body.startswith(b'PK'),k
        responses+=1
    assert {str(p.relative_to(ROOT)) for p in (ROOT/'raw').glob('*')}=={r['path'] for r in acquisitions.values()},'orphan source file or missing acquisition'
    layers=json.loads((ROOT/'gis-downloads.json').read_text());audit=json.loads((ROOT/'geometry-audit.json').read_text())['layers'];counts={}
    for key,meta in layers.items():
        native={};nv={}
        assert meta['count']==meta['after_count'] and meta['ids']==meta['after_ids']
        for b in meta['batches']:
            assert len(b['requested_ids'])<=80 and not b['exceededTransferLimit']
            r=acquisitions[b['key']];j=json.loads(read(ROOT/r['path']));assert not j.get('exceededTransferLimit')
            actual=[f['attributes'][meta['oid_field']] for f in j['features']]
            assert sorted(actual)==b['requested_ids'] and actual==b['returned_ids']
            for f in j['features']:
                oid=f['attributes'][meta['oid_field']];assert oid not in native
                native[oid]=f['attributes'];g=f['geometry'];assert g and not g.get('curveRings')
                nv[oid]=sum(len(r) for r in g['rings'])
                for ring in g['rings']:
                    assert ring[0]==ring[-1] and len(ring)>=4
                    assert all(len(pt)==2 and all(math.isfinite(v) for v in pt) for pt in ring)
        assert sorted(native)==meta['ids'] and len(native)==meta['count']
        paths=sorted((ROOT/'state-reference').glob('*.gz')) if key=='town' else [ROOT/'municipal-gis'/(key+'.geojson.gz')]
        derived={};dv={}
        for p in paths:
            j=json.loads(read(p));assert j['type']=='FeatureCollection'
            for f in j['features']:
                oid=f['id'];assert oid not in derived;assert f['properties']==native[oid]
                assert f['geometry']['type'] in ['Polygon','MultiPolygon']
                derived[oid]=f;dv[oid]=vertices(f['geometry']['coordinates'])
        assert sorted(derived)==meta['ids'] and nv==dv,(key,'full vertex / ID coverage')
        assert sum(dv.values())==audit[key]['native_and_derivative_vertices']
        if key=='town':
            for u in pr:
                if u['map_scope']=='none':continue
                assert u.get('geojson') and u.get('preview') and (ROOT/u['preview']).exists()
                fs=json.loads(read(ROOT/u['geojson']))['features']
                assert [f['id'] for f in fs]==u['matched_source_ids']
                assert all(f==derived[f['id']] for f in fs)
            wilton=next(x for x in pr if x['native_name']=='Wilton/Twps')
            assert wilton['matched_town_names']==['Perkins Twp','Washington Twp','Wilton']
            bristol=next(x for x in pr if x['native_name']=='Bristol/Louds Island Twp')
            assert 4898 in bristol['matched_source_ids'] and bristol['unresolved_components']
        counts[key]={'features':len(native),'native_full_vertices':sum(nv.values()),'bounded_batches':len(meta['batches']),'native_and_derivative_ids_identical':True,'attributes_unchanged':True,'no_geometry_repair':True}
    ca=json.loads((ROOT/'census-audit.json').read_text());z=zipfile.ZipFile(ROOT/'raw/census-vtd-2020pl.zip');assert z.testzip() is None
    assert len(z.infolist())==len(ca['members'])
    for m in ca['members']:assert sha(z.read(m['name']))==m['sha256'] and len(z.read(m['name']))==m['bytes']
    fs=json.loads(read(ROOT/'census-vtd-2020-reference.geojson.gz'))['features'];assert len(fs)==ca['feature_count'] and [f['id'] for f in fs]==ca['ids']
    pa=json.loads((ROOT/'pdf-audit.json').read_text());page_count=0;originals=set()
    for key,r in pa.items():
        if not r.get('page_count'):continue
        originals.add(r['path']);assert len(r['pages'])==r['page_count']
        for page in r['pages']:assert (ROOT/page['preview']).exists()
        assert (ROOT/r['text']).exists();page_count+=len(r['pages'])
    hp=Links();hp.feed((ROOT/'index.html').read_text());assert all('unit-'+str(u['rank']) in hp.ids for u in pr)
    checked=0
    for link in hp.links:
        if re.match(r'^[a-z]+:',link,re.I) or link.startswith('//'):continue
        target,_,fragment=link.partition('#')
        if not target:assert fragment in hp.ids,link
        else:assert (ROOT/target).resolve().exists(),link
        checked+=1
    report=STATE/'precinct-maps.md';assert report.exists()
    for link in re.findall(r'\]\(([^)]+)\)',report.read_text()):
        if re.match(r'^[a-z]+:',link,re.I) or link.startswith('#'):continue
        assert (STATE/link.split('#')[0]).resolve().exists(),link
    for filename,r in json.loads((ROOT/'external-evidence-references.json').read_text()).items():assert sha((STATE/filename).read_bytes())==r['sha256'],('read-only source changed',filename)
    files=[p for p in ROOT.rglob('*') if p.is_file()];maximum=max((p.stat().st_size,str(p.relative_to(ROOT))) for p in files)
    assert maximum[0]<40_000_000,maximum
    assert not any(p.suffix=='.pyc' or '__pycache__' in p.parts for p in files),'remove generated caches'
    result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'all_native_identities':512,'ordered_priority_entries':164,'administrative_no_polygon':1,'priority_physical_previews_and_subsets':163,'priority_keys_sha256':sha(keys),'top15_votes':215627,'first163_votes':656778,'priority_votes':658029,'statewide_votes':821072,'original_http_acquisitions_verified':responses,'gis':counts,'census_original_zip_crc':'pass','census_feature_count':len(fs),'pdf_unique_originals':len(originals),'pdf_previews_checked_including_aliases':page_count,'local_index_links_checked':checked,'max_retained_object_bytes':maximum[0],'max_retained_object_path':maximum[1],'limitations':'Passing checks certify retained bytes, source coverage and explicit gap accounting, not legal geometry approval, historical boundary equivalence, valid topology for every feature, or vote-return allocation.'}
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
