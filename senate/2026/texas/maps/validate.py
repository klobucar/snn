#!/usr/bin/env python3
"""Independent offline checks of archived sources, subsets, contracts and local links."""
import collections,csv,datetime,gzip,hashlib,io,json,re,struct,sys,zipfile
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import shapefile
from pyproj import CRS,Transformer
from acquire import ROOT,original,sha,save_json

def readcsv(p):
 if p.suffix=='.gz':
  with gzip.open(p,'rt',newline='') as f:return list(csv.DictReader(f))
 with p.open(newline='') as f:return list(csv.DictReader(f))
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=set();self.remote_resources=[]
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if 'id' in d:self.ids.add(d['id'])
  if 'href' in d:self.links.append(d['href'])
  if 'src' in d:
   self.links.append(d['src'])
   if urlsplit(d['src']).scheme:self.remote_resources.append(d['src'])
def main():
 save_json(ROOT/'validation.json',dict(status='running',scope='Offline final archive validation in progress'))
 if not (ROOT/'asset-hashes.json').exists():save_json(ROOT/'asset-hashes.json',dict(status='pending final validation'))
 data=ROOT.parent/'data';checks={};sources={p.stem:json.loads(p.read_text()) for p in (ROOT/'sources').glob('*.json')};original_cache={}
 def body(key):
  if key not in original_cache:original_cache[key]=original(sources[key])
  return original_cache[key]
 county=readcsv(data/'county-turnout.csv');contract=json.loads((data/'turnout/priority-set.json').read_text());keys=(data/'coordinator-priority-keys.txt').read_bytes();ordered=keys.decode().splitlines()
 assert len(county)==254==len({c['county_fips'] for c in county})==len(contract['groups'])
 assert [c['dispatch_key'] for c in county]==contract['full_order']
 assert sha(keys)=='a5d39344328ab3c0f76809439c6af42c09a59d81f76b9b756e5b538a63ac5be5'
 assert ordered==contract['priority_keys']==[c['dispatch_key'] for c in county[:34]]
 assert sum(int(c['senate_2024_total']) for c in county)==11291854
 assert sum(int(c['senate_2024_total']) for c in county[:34])==9076868
 assert sum(int(c['senate_2024_total']) for c in county[:33])==9018686
 pinned={'county-turnout.csv':'1da814cfbdc254063fa3bd60a35fed870b5825a89f3267303e3cff3656144140','turnout/priority-set.json':'8c30e57da8010aeb34c539611a41740ec199caa2bc8f2a0285f45e5a84d56ff5','county-baselines.csv':'dd2aff196f5e04ba4da0c743a423e12bead91aac3d7a00dd8ebb1ec6380a75d6'}
 for fn,h in pinned.items():assert sha((data/fn).read_bytes())==h,fn
 final_native={
  'native-unit-identities.csv.gz':('425f67998803ab3e64be410739083f2deabc1995052f484252bd159f4e5c0b61',151211),
  'native-unit-observations.csv.gz':('81e6a8ad4fa554303d85ef59099468ae99cd806fc3cab578567e9d29c3a3ad5c',1837859),
  'native-field-schemas.json':('da8ca595801613076760494e89b93db0bf90c90b45805e499073c2b326fd22d2',121688),
  'native-inventory-summary.json':('5b0f61e3621ff0c78653d2379403b8c709e3728701920b922ada2316441cc908',2631)}
 for fn,(h,n) in final_native.items():
  b=(data/'results-sources'/fn).read_bytes();assert len(b)==n and sha(b)==h,fn
 inv=readcsv(ROOT/'inventory/all-counties.csv');assert [x['dispatch_key'] for x in inv]==contract['full_order'];assert sum(int(x['priority80']) for x in inv)==34
 checks['county_contract']=dict(counties=254,priority=34,priority_keys_sha256=sha(keys),primary_county_input_hashes=pinned,priority_votes=9076868,all_votes=11291854,previous33_votes=9018686,Midland_crossing_votes=58182)
 stored=set();valid_sources=0;failure_sources=[]
 for key,d in sources.items():
  assert d.get('requested_url') and d.get('retrieved_utc')
  if 'stored_parts' in d:
   for part in d['stored_parts']:
    p=ROOT/part['path'];b=p.read_bytes();assert len(b)==part['bytes'] and sha(b)==part['sha256'] and len(b)<40_000_000,(key,p)
    stored.add(part['path'])
   b=original(d);assert len(b)==d['original_bytes'] and sha(b)==d['original_sha256']
   assert d.get('headers') is not None and d.get('final_url') and 'status' in d and 'redirects' in d
   valid_sources+=1
   if d['status']!=200 or not len(b):failure_sources.append(dict(source_id=key,status=d['status'],bytes=len(b),error=d.get('error')))
  else:assert d.get('error');failure_sources.append(dict(source_id=key,error=d['error']))
 assert {str(p.relative_to(ROOT)) for p in (ROOT/'originals').glob('*')}==stored,'Orphan or missing original storage'
 checks['originals']=dict(sources=valid_sources,unique_stored_stream_parts=len(stored),access_failures=failure_sources,all_original_and_saved_hashes_verified=True)
 geometry_rows=readcsv(ROOT/'inventory/native-geometry-units.csv.gz');grby=collections.defaultdict(list)
 for r in geometry_rows:grby[r['source_id']].append(r)
 native_total=0;vertices=0;subsets=0;invalid=0;positive_pairs=0
 for v in ['24g','26p','22g','20g']:
  key='tlc-'+v;z=zipfile.ZipFile(io.BytesIO(body(key)));assert z.testzip() is None
  n=next(n[:-4] for n in z.namelist() if n.endswith('.shp'));sb=z.read(n+'.shp');xb=z.read(n+'.shx');db=z.read(n+'.dbf');hlen,rlen=struct.unpack_from('<HH',db,8)
  reader=shapefile.Reader(shp=io.BytesIO(sb),shx=io.BytesIO(xb),dbf=io.BytesIO(db));a=json.loads((ROOT/'geometry'/(key+'-audit.json')).read_text());rows=grby[key]
  assert len(reader)==len(rows)==a['source_features']==(len(xb)-100)//8==struct.unpack_from('<I',db,4)[0]
  assert struct.unpack_from('>I',sb,24)[0]*2==len(sb)
  crs=CRS.from_wkt(z.read(n+'.prj').decode());assert crs.is_projected and all(x.unit_name=='metre' for x in crs.axis_info);trans=Transformer.from_crs(crs,4326,always_xy=True)
  counter=collections.Counter();vc=0
  for i,(sr,row) in enumerate(zip(reader.iterShapeRecords(),rows)):
   attr=sr.record.as_dict();assert json.loads(row['attributes_json'])==attr and int(row['source_row_index'])==i
   assert row['native_PREC']==str(attr['PREC']) and row['native_PCTKEY']==str(attr['PCTKEY'])
   assert int(row['vertices'])==len(sr.shape.points) and int(row['parts'])==len(sr.shape.parts)
   assert row['county_fips']=='48'+str(attr['CNTY']).zfill(3)
   counter[row['county_fips']]+=1;vc+=len(sr.shape.points)
   if sr.shape.shapeType:
    x0,y0,x1,y1=sr.shape.bbox
    for x,y in [(x0,y0),(x1,y1)]:
     lon,lat=trans.transform(x,y);assert -108<lon<-92 and 24<lat<38,(key,i,lon,lat)
  assert vc==a['source_vertices'];assert set(counter)=={c['county_fips'] for c in county};assert not a['duplicate_PCTKEY']
  for c in a['counties']:
   assert c['features']==counter[c['county_fips']]
   if c['county_fips'] not in {x['county_fips'] for x in county[:34]}:assert 'subset' not in c;continue
   sub=c['subset'];zz=zipfile.ZipFile(ROOT/sub['path']);ss=zz.read('precincts.shp');xx=zz.read('precincts.shx');dd=zz.read('precincts.dbf');indices=sub['source_row_indices_zero_based']
   assert zz.testzip() is None and len(indices)==c['features']==(len(xx)-100)//8==struct.unpack_from('<I',dd,4)[0]
   assert zz.read('precincts.prj')==z.read(n+'.prj')
   assert sha((ROOT/sub['path']).read_bytes())==sub['sha256'] and (ROOT/sub['path']).stat().st_size==sub['bytes']
   assert indices==[int(row['source_row_index']) for row in rows if row['county_fips']==c['county_fips']]
   for k,i in enumerate(indices):
    off,ln=struct.unpack_from('>II',xb,100+8*i);off2,ln2=struct.unpack_from('>II',xx,100+8*k);b1=sb[off*2+8:off*2+8+ln*2];b2=ss[off2*2+8:off2*2+8+ln2*2]
    assert b1==b2 and sha(b2)==sub['raw_geometry_record_sha256'][k]
    b1=db[hlen+i*rlen:hlen+(i+1)*rlen];b2=dd[hlen+k*rlen:hlen+(k+1)*rlen]
    assert b1==b2 and sha(b2)==sub['raw_dbf_record_sha256'][k]
   subsets+=1
  native_total+=len(reader);vertices+=vc;invalid+=len(a['invalid_or_empty']);positive_pairs+=sum(c['overlap']['positive_area_pair_count'] for c in a['counties'])
 assert subsets==136 and native_total==37871 and vertices==18050402
 checks['statewide_geometry']=dict(vintages=4,all_counties_each=254,features=native_total,full_source_vertices=vertices,county_subsets=subsets,subset_geometry_and_attributes_byte_identical=True,invalid_preserved=invalid,positive_area_pairs_in_native_square_metres=positive_pairs,limits='Within-county/source overlap diagnostics; invalid source geometry excluded from intersection only; no repair or cross-vintage allocation.')
 # GIS pagination and full attribute/vertex coverage checked directly against original pages.
 gis_features=0;gis_vertices=0;missing=[];actual_dims=collections.Counter()
 for p in (ROOT/'gis').glob('*-audit.json'):
  a=json.loads(p.read_text());assert a['status']=='pass',p
  seen=[];count=0;vc=0
  ordinary={f['name'] for f in a['all_fields'] if f['type']!='esriFieldTypeGeometry'}
  for batch in a['batches']:
   j=json.loads(body(batch['source_id']));assert not j.get('exceededTransferLimit',False)
   got=[f['attributes'][a['object_id_field']] for f in j['features']]
   assert sorted(got)==sorted(batch['requested_ids'])==sorted(batch['returned_ids'])
   assert len(batch['requested_ids'])<=100<=int(a['maxRecordCount'])
   for f in j['features']:
    if ordinary-set(f['attributes']):missing.append(dict(source=a['id'],oid=f['attributes'][a['object_id_field']],fields=sorted(ordinary-set(f['attributes']))))
    g=f.get('geometry') or {}
    for ring in g.get('rings',[]):vc+=len(ring);actual_dims.update(len(pt) for pt in ring)
   seen+=got;count+=len(got)
  assert sorted(seen)==a['pre_ids']==a['post_ids'] and len(set(seen))==count==a['pre_count']==a['post_count']
  ga=json.loads((ROOT/'geometry'/('gis-'+a['id']+'.json')).read_text());assert ga['features']==count and ga['vertices']==vc
  gis_features+=count;gis_vertices+=vc
 assert not missing,missing[:5]
 assert len(readcsv(ROOT/'inventory/county-gis-units.csv.gz'))==gis_features==1864
 checks['county_GIS']=dict(layers=9,features=gis_features,vertices=gis_vertices,actual_coordinate_dimensions=dict(actual_dims),all_attributes_covered=True,all_pre_post_count_ID_sets_equal=True,all_requested_returned_batch_ID_sets_equal=True,no_transfer_limits=True,Z_M_true_curves='Requested explicitly; Johnson XYZ retained, eight XY layers; no curves observed; support metadata preserved.')
 # Native unit and constituent coverage, without deduplicating source positions.
 comp=readcsv(ROOT/'inventory/reporting-unit-compatibility.csv.gz');cs=json.loads((ROOT/'inventory/compatibility-summary.json').read_text());peer_summary=json.loads((data/'results-sources/native-inventory-summary.json').read_text());assert len(comp)==cs['total_identities_accounted']==31702+4276+peer_summary['source_scoped_identities']
 assert set(r['status'] for r in comp)<={'matched','ambiguous','administrative/no-polygon','absent geometry','source conflict','unknown'}
 assert not any(r['status']=='matched' for r in comp)
 for name,fn in [('historical-OE','baselines/native-units.csv.gz'),('primary-historical','turnout/primary-native-units.csv.gz'),('official-discovery','results-sources/native-unit-identities.csv.gz')]:
  expected=readcsv(data/fn);actual=[json.loads(r['input_row_json']) for r in comp if r['inventory']==name]
  assert collections.Counter(json.dumps(x,sort_keys=True) for x in expected)==collections.Counter(json.dumps(x,sort_keys=True) for x in actual)
 constituents=readcsv(ROOT/'inventory/accepted-constituents.csv.gz');expected=[]
 for g in contract['groups']:
  for layer,component in [('native_constituents','source-native'),('derived_vtd_constituents','derived-VTD')]:
   for i,u in enumerate(g.get(layer,[])):expected.append((g['dispatch_key'],component,i,json.dumps(u,sort_keys=True)))
 assert expected==[(r['dispatch_key'],r['component_class'],int(r['component_ordinal']),json.dumps(json.loads(r['component_json']),sort_keys=True)) for r in constituents]
 obs=readcsv(data/'results-sources/native-unit-observations.csv.gz');ident=readcsv(data/'results-sources/native-unit-identities.csv.gz');oc=collections.Counter((r['source_id'],r['unit_kind'],r['native_id']) for r in obs)
 assert len(obs)==peer_summary['observations'] and sum(int(r['occurrences']) for r in ident)==len(obs)
 assert oc==collections.Counter({(r['source_id'],r['unit_kind'],r['native_id']):int(r['occurrences']) for r in ident})
 for ref in json.loads((ROOT/'read-only-references.json').read_text())['references']:
  p=ROOT/ref['path'];assert p.stat().st_size==ref['bytes'] and sha(p.read_bytes())==ref['sha256'],str(p)
 for item in json.loads((ROOT/'peer-original-reuse.json').read_text())['sources']:
  parts=[]
  for part in item['stored_parts']:
   b=(ROOT/part['path']).read_bytes();assert len(b)==part['bytes'] and sha(b)==part['sha256'];parts.append(b)
  b=gzip.decompress(b''.join(parts));assert len(b)==item['original_bytes'] and sha(b)==item['original_sha256']
 grayson=[r for r in comp if r['source_id']=='county-48181-office-follow1-sample'];assert len(grayson)==42
 assert all(r['county_fips']=='48181' and r['observation_class']=='older_election_excluded' and json.loads(r['input_row_json'])['unit_kind']=='pdf_precinct_label' and json.loads(r['input_row_json'])['election_id']=='2026-03-03' for r in grayson)
 assert sum(int(json.loads(r['input_row_json'])['occurrences']) for r in grayson)==546
 checks['reporting_compatibility']=dict(identities=len(comp),accepted_constituents=len(constituents),accepted_county_groups=254,official_observation_positions=len(obs),repeats_preserved=True,approved_matches=0,status_counts=dict(collections.Counter(r['status'] for r in comp)),peer_reference_hashes_verified=True,final_native_pins={fn:dict(sha256=h,bytes=n) for fn,(h,n) in final_native.items()},Grayson_PDF=dict(source_id='county-48181-office-follow1-sample',county_fips='48181',election_id='2026-03-03',unit_kind='pdf_precinct_label',observation_class='older_election_excluded',identities=42,appearances=546))
 pdf=json.loads((ROOT/'pdf/inspection.json').read_text());pages=0
 for p in pdf['sources']:
  b=body(p['source_id']);assert b.startswith(b'%PDF') and sha(b)==p['original_sha256'] and len(b)==p['original_bytes'];assert p['poppler_page_count_check'] and len(p['page_diagnostics'])==p['pages']
  assert gzip.decompress((ROOT/p['text_path']).read_bytes()).startswith(b'--- PAGE 1 ---')
  for pp in p['preview_paths']:assert (ROOT/pp).exists() and (ROOT/pp).stat().st_size>0
  pages+=p['pages']
 checks['PDFs']=dict(originals=len(pdf['sources']),pages=pages,selected_page_previews=sum(len(p['preview_paths']) for p in pdf['sources']),original_hashes_and_poppler_counts_verified=True,representative_visual_review='See visual-review.json; previews are not original PDF bytes or full page coverage.')
 parsers={};linkcount=0
 for p in ROOT.rglob('*.html'):
  parser=Links();parser.feed(p.read_text());parsers[p]=parser
 for p,parser in parsers.items():
  assert not parser.remote_resources,(p,parser.remote_resources)
  for url in parser.links:
   u=urlsplit(url)
   if u.scheme or u.netloc or not u.path and not u.fragment:continue
   target=(p.parent/unquote(u.path)).resolve() if u.path else p
   assert target.exists(),(p,url)
   if u.fragment and target.suffix=='.html':assert unquote(u.fragment) in parsers.get(target,Links()).ids,(p,url)
   linkcount+=1
 for p in [ROOT.parent/'precinct-maps.md',ROOT/'SCHEMA.md']:
  for url in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',p.read_text()):
   u=urlsplit(url.strip('<>'))
   if u.scheme or u.netloc or not u.path:continue
   assert (p.parent/unquote(u.path)).resolve().exists(),(p,url);linkcount+=1
 assert len(list((ROOT/'pages').glob('*.html')))==34 and len(list((ROOT/'counties').glob('*.zip')))==136
 checks['offline_links']=dict(html_pages=len(parsers),checked_local_links=linkcount,no_remote_render_resources=True,county_pages=34,county_reference_downloads=136,static_disk_operation=True)
 files=[p for p in ROOT.rglob('*') if p.is_file()]+[ROOT.parent/'precinct-maps.md'];assert all(p.stat().st_size<40_000_000 for p in files)
 assert not any(p.name in ['__pycache__','node_modules','.venv'] for p in ROOT.rglob('*'))
 checks['bounds']=dict(strict_asset_cap_bytes=40000000,largest_retained_file_bytes=max(p.stat().st_size for p in files),no_dependency_or_cache_directories=True)
 save_json(ROOT/'validation.json',dict(status='pass',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,scope='Evidence/asset/coverage/geometry/compatibility/offline validation. Not legal approval, collector admission, geographic crosswalk or calibration.'))
 files=sorted([p for p in ROOT.rglob('*') if p.is_file() and p.name!='asset-hashes.json']+[ROOT.parent/'precinct-maps.md'])
 hashes=[dict(path=str(p.relative_to(ROOT.parent)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in files]
 save_json(ROOT/'asset-hashes.json',dict(self_excluded='Only maps/asset-hashes.json; all other owned retained files included.',strict_cap=40000000,assets=hashes))
 print(json.dumps(dict(status='pass',files=len(hashes),bytes=sum(r['bytes'] for r in hashes),checks={k:({kk:vv for kk,vv in v.items() if kk not in ['access_failures']} if k=='originals' else v) for k,v in checks.items()}),indent=2))
if __name__=='__main__':main()
