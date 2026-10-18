#!/usr/bin/env python3
"""Independent offline, standard-library-only integrity/identity/link audit; no network or boundary approval."""
from pathlib import Path
import collections,csv,datetime,gzip,hashlib,io,json,math,re,struct,sys,urllib.parse,zipfile,xml.etree.ElementTree as ET
from html.parser import HTMLParser
R=Path(__file__).resolve().parent;S=R.parent
H=lambda b:hashlib.sha256(b).hexdigest()
j=lambda p:json.loads((R/p).read_text())
read=lambda p:gzip.decompress((R/p).read_bytes()) if str(p).endswith('.gz') else (R/p).read_bytes()
checks=[]
for output in ['validation.json','artifact-manifest.json']:
 if not (R/output).exists():(R/output).write_text('{}\n')
def ok(name,detail):checks.append(dict(check=name,status='pass',detail=detail))
# Read-only baseline, exact ordered FIPS/constituents, all native identities.
for p,sha in j('input-hashes.json').items():assert H((S/p).read_bytes())==sha,p
assert H((S/'data/county-turnout.csv').read_bytes())=='d9133f7f88eca91b8bef8f3987b3e1abfb30b19e61d1d824a1e270dde4049a90'
rows=list(csv.DictReader((S/'data/county-turnout.csv').open()));dispatch=json.loads((S/'data/turnout/priority-set.json').read_text());C=j('county-inventory.json');pr=[c for c in C if c['priority']]
expected_names='Franklin,Cuyahoga,Hamilton,Summit,Montgomery,Lucas,Stark,Butler,Lorain,Warren,Delaware,Lake,Clermont,Mahoning,Medina,Trumbull,Licking,Greene,Fairfield,Portage,Wood,Clark,Miami,Richland,Geauga,Wayne,Columbiana,Allen,Ashtabula,Tuscarawas,Erie,Muskingum'.split(',')
assert [c['county'] for c in pr]==expected_names
assert len(C)==88 and len({c['county_fips'] for c in C})==88
assert [c['county_fips'] for c in C]==dispatch['ordered_county_keys_all88']
assert [c['county_fips'] for c in pr]==dispatch['ordered_priority_county_keys']
assert len(j('official-boe-directory.json')['counties'])==88
units=list(csv.DictReader(io.StringIO(read('reporting-unit-compatibility.csv.gz').decode())))
for y,count in [(2024,8878),(2022,8933)]:
 us=list(csv.DictReader(gzip.open(S/f'data/turnout/reporting-units-{y}.csv.gz','rt')));assert len(us)==count
 xs=[u for u in units if u['election_date'].startswith(str(y))];assert len(xs)==count
 assert {u['unit_key'] for u in xs}=={u['unit_key'] for u in us}
 bykey={u['unit_key']:u for u in xs}
 for u in us:assert all(bykey[u['unit_key']][k]==v for k,v in u.items()),u['unit_key']
 expected={u['unit_key']:(u['precinct_code_native'],u['precinct_name_native']) for c in dispatch['county_records'] for u in c['reporting_units'][str(y)]['units']}
 assert {u['unit_key']:(u['precinct_code_native'],u['precinct_name_native']) for u in us}==expected
ok('baseline hashes, 88 FIPS, exact ordered 32 priorities and every native reporting identity','8878 + 8933 = 17811 unchanged native records; exact dispatch constituents and original CSV fields')
# All HTTP outcomes, response/stored hashes, gzip and original ZIP CRC/member hashes.
ledger=j('source-ledger.json');zipinfo=[];statuses=collections.Counter()
for m in ledger:
 p=R/m['stored_path'];b=p.read_bytes();assert H(b)==m['stored_sha256'],p
 b=gzip.decompress(b) if p.suffix=='.gz' else b
 assert len(b)==m['bytes'] and H(b)==m['sha256'],p
 assert m['requested_url'].startswith(('http://','https://')) and m['retrieved_utc'];statuses[str(m['status'])]+=1
 if b[:2]==b'PK':
  z=zipfile.ZipFile(io.BytesIO(b));assert z.testzip() is None
  zipinfo.append(dict(path=m['stored_path'],members=[dict(name=i.filename,bytes=i.file_size,crc32=f'{i.CRC:08x}',sha256=H(z.read(i))) for i in z.infolist() if not i.is_dir()]))
(R/'zip-member-manifest.json').write_text(json.dumps(zipinfo,indent=2)+'\n');ok('HTTP snapshot integrity and all ZIP CRC/member hashes',dict(responses=len(ledger),status_counts=dict(statuses),original_zip_files=len(zipinfo)))
D=j('dataset-manifest.json');assert len(D)==60
curve_count=0;original_features=0
for d in D:
 if 'batch_paths' not in d:continue
 n=json.loads(read(d['count_path']))['count'];ids=json.loads(read(d['ids_path']))['objectIds'];oid=d['object_id_field'];source=[]
 assert n==len(ids)==len(set(ids))==d['feature_count']
 for p in d['batch_paths']:
  x=json.loads(read(p));assert not x.get('error') and not x.get('exceededTransferLimit');assert len(x['features'])<=50;source.extend(x['features'])
 actual=[f['attributes'][oid] for f in source];assert len(actual)==len(set(actual))==n and set(actual)==set(ids)
 gj=json.loads(read(d['geojson_path']));assert len(gj['features'])==len(source)
 for a,b in zip(source,gj['features']):assert all(b['properties'][k]==v for k,v in a['attributes'].items())
 curves=[f['attributes'][oid] for f in source if 'curveRings' in (f.get('geometry') or {})];assert sorted(curves)==sorted(d.get('native_curve_object_ids',[]));curve_count+=len(curves)
 if curves:
  lin=json.loads(read(d['linearized_derivative_path']));assert {f['attributes'][oid] for f in lin['features']}==set(curves)
 original_features+=n
ok('ArcGIS count/all-ID/batch coverage and all source attributes',dict(downloaded_records=original_features,native_curve_records=curve_count,transfer_limit_flags=False))
# Independent native shapefile record/vertex parsing, including empty records, without pyshp.
def parts(d):
 if d.get('components'):
  out={}
  for e,p in d['components'].items():
   if e not in ['shp','dbf','shx','prj']:continue
   b=read(p)
   if b[:2]==b'PK':z=zipfile.ZipFile(io.BytesIO(b));b=z.read(next(n for n in z.namelist() if n.lower().endswith('.'+e)))
   out[e]=b
  return out
 if d.get('shapefile_stem'):
  z=zipfile.ZipFile(io.BytesIO(read(d['original_path'])));stem=d['shapefile_stem'].lower();return {e:z.read(next(n for n in z.namelist() if n.lower()==stem+'.'+e)) for e in ['shp','shx','dbf','prj']}
 return None
def native_shape_count(b):
 assert struct.unpack('>i',b[:4])[0]==9994 and struct.unpack('>i',b[24:28])[0]*2==len(b)
 pos=100;count=vertices=empty=0
 while pos<len(b):
  rn,words=struct.unpack('>ii',b[pos:pos+8]);v=b[pos+8:pos+8+words*2];t=struct.unpack('<i',v[:4])[0];count+=1
  if t==0:empty+=1
  else:
   assert t in [5,15,25],t
   nparts,npts=struct.unpack('<ii',v[36:44]);vertices+=npts
   if not npts:empty+=1
   off=44+4*nparts;xy=[struct.unpack('<dd',v[off+16*i:off+16*i+16]) for i in range(npts)];assert all(math.isfinite(x) and math.isfinite(y) for x,y in xy)
   starts=list(struct.unpack('<'+'i'*nparts,v[44:off]))+[npts]
   for a,bx in zip(starts,starts[1:]):assert bx-a>=4 and xy[a]==xy[bx-1],(rn,'unclosed source ring')
  pos+=8+words*2
 assert pos==len(b);return count,vertices,empty
censusparts=None
for d in D:
 p=parts(d)
 if not p:continue
 n,nv,empty=native_shape_count(p['shp']);dbfcount=struct.unpack('<I',p['dbf'][4:8])[0];assert n==dbfcount
 if d['dataset_id'].startswith('census'):
  censusparts=p;assert n==8941;continue
 assert (n,nv,empty)==(d['feature_count'],d['source_vertices'],d['empty_count']),d['dataset_id']
assert censusparts is not None
ci=j('census-all88-inventory.json');assert set(ci)==set(dispatch['ordered_county_keys_all88']) and sum(x['features'] for x in ci.values())==8941
allcensus=[id for x in ci.values() for id in x['native_ids']];assert len(allcensus)==len(set(allcensus))==8941
ok('native shapefile records, vertices, finite coordinates and ring closure; all-state VTD inventory','All original polygon rings closed; Census 8941 unique native GEOIDs across exact88 FIPS; no current approval implied')
# Every derivative: finite closed rings, original count/attributes/vertex count, deliberate empties and source defects.
def walk(g):
 if not g:return []
 assert g['type'] in ['Polygon','MultiPolygon']
 return g['coordinates'] if g['type']=='Polygon' else [r for p in g['coordinates'] for r in p]
invalid=empty=overlaps=intersection_errors=0
for d in D:
 gj=json.loads(read(d['geojson_path']));dg=j(d['diagnostics_path']);assert len(gj['features'])==dg['feature_count']==d['feature_count'];nv=0;em=[]
 for i,f in enumerate(gj['features']):
  assert f['properties']['research_county_fips']==d['county_fips'] and f['properties']['research_source_ordinal']==i
  rings=walk(f['geometry']);nv+=sum(len(r) for r in rings)
  if not rings:em.append(i)
  for ring in rings:
   assert len(ring)>=4 and ring[0]==ring[-1]
   assert all(math.isfinite(x) and math.isfinite(y) and -180<=x<=180 and -90<=y<=90 for x,y,*_ in ring)
 assert nv==dg['derived_vertices']==dg['source_vertices']==d['source_vertices']
 assert em==dg['empty_ordinals'];assert dg['finite_bounds'];assert len(dg['invalid_features'])==d['invalid_count'];assert len(dg['overlap_pairs'])==d['overlap_count'];assert all(x['area_in_crs_squared_units']>0 for x in dg['overlap_pairs']);assert d['approved_nov2026'] is False
 assert (R/d['preview_path']).read_text().startswith('<svg')
 invalid+=d['invalid_count'];empty+=d['empty_count'];overlaps+=d['overlap_count'];intersection_errors+=d['intersection_error_count']
ok('full-vertex derivatives, exact feature counts, finite coordinates, retained defects',dict(datasets=len(D),empty_records=empty,invalid_source_geometries=invalid,positive_area_overlap_pairs=overlaps,intersection_errors=intersection_errors,repairs='none',approval='not established'))
x=ET.fromstring(read('evidence/resolve/medina-features.gz'));assert len(x.findall('{http://www.opengis.net/gml}featureMember'))==203;assert read('evidence/finish/medina-highlimit.gz')==read('evidence/resolve/medina-features.gz');assert len(ET.fromstring(read('evidence/finish/medina-first10.gz')).findall('{http://www.opengis.net/gml}featureMember'))==10;assert int(ET.fromstring(read('evidence/finish/medina-hits.gz')).get('numberOfFeatures'))==203
ok('Medina WFS count/transfer controls','203 hits/full/high-limit; 10-feature control; no IDs manufactured')
# Complete PDF manifest vs unchanged bytes and all-page preview inventory.
P=j('pdf-manifest.json');pc=pages=0
for p in P:
 if not p['complete_pdf']:continue
 b=(R/p['path']).read_bytes();assert H(b)==p['sha256'] and b.startswith(b'%PDF') and b'%%EOF' in b[-2048:]
 assert p['page_count']==len(p['page_sizes_points']) and p['page_count']>0
 for k in ['preview_path','contact_path','text_path']:assert (R/p[k]).is_file() and (R/p[k]).stat().st_size>0
 pc+=1;pages+=p['page_count']
assert (pc,pages)==(205,466)
for im in j('image-manifest.json'):
 b=(R/im['path']).read_bytes();assert H(b)==im['sha256']
 if im['format']=='PNG':assert b[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',b[16:24])==(im['width'],im['height']);assert im['vector_geometry'] is False
 else:assert b[:2]==b'\xff\xd8'
ok('PDF and image originals with usable previews',dict(complete_pdfs=pc,pages=pages,separate_images=2,excluded_truncated_captures=True))
# Exact local index links and all32 preview representation.
class Links(HTMLParser):
 def __init__(self):super().__init__();self.refs=[];self.ids=set();self.fips=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  for k in ['href','src']:
   if a.get(k):self.refs.append(a[k])
  if a.get('id'):self.ids.add(a['id'])
  if a.get('data-fips'):self.fips.append(a['data-fips'])
parser=Links();parser.feed((R/'index.html').read_text());assert parser.fips==dispatch['ordered_priority_county_keys']
for u in parser.refs:
 x=urllib.parse.urlparse(u)
 if x.scheme:continue
 if x.path:assert (R/urllib.parse.unquote(x.path)).is_file(),u
 if not x.path and x.fragment:assert x.fragment in parser.ids,u
for c in pr:assert (R/c['index_preview_path']).is_file()
md=(S/'precinct-maps.md').read_text()
for u in re.findall(r'\]\(([^)]+)\)',md):
 if u.startswith(('http:','https:')):continue
 assert (S/u.split('#')[0]).is_file(),u
ok('static index and report links',dict(priority_sections=len(parser.fips),local_links_checked=sum(not urllib.parse.urlparse(u).scheme for u in parser.refs)))
# No caches/dependencies, bounded individual Git asset sizes, reproducible whole-package hashes.
art=[]
for p in sorted(R.rglob('*')):
 if not p.is_file():continue
 rel=str(p.relative_to(R))
 if any(x in p.parts for x in ['.runtime','__pycache__','.venv']):raise AssertionError('runtime/cache must be removed: '+rel)
 if rel in ['artifact-manifest.json','validation.json']:continue
 assert p.stat().st_size<40000000,(rel,p.stat().st_size)
 art.append(dict(path=rel,bytes=p.stat().st_size,sha256=H(p.read_bytes())))
(R/'artifact-manifest.json').write_text(json.dumps(art,indent=2)+'\n');ok('all retained file hashes, no installed dependencies/caches, individual size ceiling',dict(files=len(art),bytes=sum(x['bytes'] for x in art),largest_bytes=max(x['bytes'] for x in art),limit_bytes=40000000))
result=dict(status='pass with explicitly retained source/access/approval gaps',audited_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),network_used=False,checks=checks,does_not_establish=['November2026 boundary approval','validated native-unit geographic crosswalk','vote allocation','live collector','calibration'])
(R/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
