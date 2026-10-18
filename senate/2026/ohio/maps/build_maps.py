#!/usr/bin/env python3
"""Offline full-precision map derivatives and diagnostics. Originals are never rewritten."""
import sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.runtime'))
os.environ['PROJ_NETWORK']='OFF'
import csv,collections,gzip,hashlib,html,io,json,math,re,zipfile,xml.etree.ElementTree as ET
import shapefile,shapely,pyproj
from shapely.geometry import Polygon,MultiPolygon,shape,mapping
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity
STATE=ROOT.parent

def jwrite(path,d):
 p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def read(path):
 b=(ROOT/path).read_bytes();return gzip.decompress(b) if str(path).endswith('.gz') else b

def esri(rings):
 shells=[];holes=[]
 for ring in rings:
  a=sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(ring,ring[1:]))/2
  (shells if a<0 else holes).append(ring)
 note=[]
 if not shells and holes:shells,holes=holes,[];note.append('all rings counterclockwise; interpreted as exterior rings')
 groups=[[s,[]] for s in shells]
 for hole in holes:
  hp=Polygon(hole);poss=[]
  for i,(s,hs) in enumerate(groups):
   try:
    p=Polygon(s)
    if p.covers(hp.representative_point()):poss.append((p.area,i))
   except Exception:pass
  if poss:groups[min(poss)[1]][1].append(hole)
  else:groups.append([hole,[]]);note.append('uncontained counterclockwise ring interpreted as exterior')
 ps=[Polygon(s,hs) for s,hs in groups];return (ps[0] if len(ps)==1 else MultiPolygon(ps)),note

def shp_bytes(path,ext):
 b=read(path)
 if b.startswith(b'PK'):
  z=zipfile.ZipFile(io.BytesIO(b));n=next(n for n in z.namelist() if n.lower().endswith('.'+ext.lower()));return z.read(n)
 return b

def load_shp(parts):
 rd=shapefile.Reader(**{e:io.BytesIO(b) for e,b in parts.items() if e in ['shp','shx','dbf']},encoding='utf-8',encodingErrors='replace')
 fs=[];notes=[];vertices=0
 for i,sr in enumerate(rd.iterShapeRecords()):
  attrs=sr.record.as_dict();attrs={k:(v.isoformat() if hasattr(v,'isoformat') else v) for k,v in attrs.items()};g=sr.shape.__geo_interface__ if sr.shape.points else None;geom=shape(g) if g else Polygon();fs.append((attrs,geom));vertices+=len(sr.shape.points)
 return fs,parts.get('prj',b'').decode('utf-8','replace'),vertices

def zip_parts(path,stem):
 z=zipfile.ZipFile(io.BytesIO(read(path)));return {e:z.read(next(n for n in z.namelist() if n.lower()==(stem+'.'+e).lower())) for e in ['shp','shx','dbf','prj'] if any(n.lower()==(stem+'.'+e).lower() for n in z.namelist())}

def all_datasets():
 out=[]
 for p in sorted((ROOT/'datasets').glob('*.json')):
  print('LOAD',p.stem,flush=True)
  d=json.loads(p.read_text());d['dataset_id']=p.stem
  if 'batch_paths' in d:
   fs=[];notes=[];verts=0;sr=None;curves=[]
   linear={}
   if d.get('linearized_derivative_path'):
    linear={f['attributes'][d['object_id_field']]:f['geometry'] for f in json.loads(read(d['linearized_derivative_path']))['features']}
    notes.append('Original true curves retained in EsriJSON. Curve IDs listed in native_curve_object_ids are server-linearized with returnTrueCurves=false solely for polygon-only derivatives.')
   for path in d['batch_paths']:
    r=json.loads(read(path));sr=r.get('spatialReference',sr)
    for f in r['features']:
     g=f.get('geometry') or {};rings=g.get('rings',[])
     if 'curveRings' in g:
      oid=f['attributes'][d['object_id_field']];curves.append(oid);g=linear[oid];rings=g['rings']
     geom,note=esri(rings);fs.append((f['attributes'],geom));notes.extend(note);verts+=sum(len(x) for x in rings)
   assert len(fs)==d['feature_count']
   if curves:assert sorted(curves)==sorted(d['native_curve_object_ids'])
   if not sr:sr=d.get('native_sr')
   if not sr:
    md=json.loads(read(d['layer_metadata_path']));sr=md.get('extent',{}).get('spatialReference')
   code=sr.get('latestWkid',sr.get('wkid'))
   d.update(crs='EPSG:'+str(code),features=fs,source_vertices=verts,conversion_notes=notes)
  elif 'components' in d:
   parts={e:shp_bytes(v,e) for e,v in d['components'].items() if e in ['shp','shx','dbf','prj']};fs,crs,nv=load_shp(parts);d.update(features=fs,crs=crs,source_vertices=nv,conversion_notes=['BOE downloads each shapefile component inside a separate ZIP; original ZIP bytes retained.'])
  else:continue
  out.append(d)
 specs=[('clermont-published','clermont','evidence/probe/clermont-zip.bin','VotingPrecincts','published ZIP; effective date unestablished','Clermont County GIS','https://gis.clermontcountyohio.gov/download-gis-data/'),('montgomery-2022','montgomery','evidence/routes/montgomery-zip.bin','Precinct_2022_Polygon','2022-named layer in currently published June 2026 ZIP; not approval','Montgomery County Auditor; BOE-referenced GIS','https://go.mcohio.org/embed/auditor/downloads/gis_downloads.cfm'),('montgomery-2021','montgomery','evidence/routes/montgomery-zip.bin','Precinct_Historical_2021','historical 2021','Montgomery County Auditor','https://go.mcohio.org/embed/auditor/downloads/gis_downloads.cfm'),('montgomery-2017','montgomery','evidence/routes/montgomery-zip.bin','Precinct_Historical_2017','historical 2017','Montgomery County Auditor','https://go.mcohio.org/embed/auditor/downloads/gis_downloads.cfm'),('montgomery-2012','montgomery','evidence/routes/montgomery-zip.bin','Precinct_Historical_2012','historical 2012','Montgomery County Auditor','https://go.mcohio.org/embed/auditor/downloads/gis_downloads.cfm'),('mahoning-2025','mahoning','evidence/finaldiscovery/mahoning-2025.bin','Precincts_2025','2025-named county download; no November 2026 approval','Mahoning County GIS','https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/'),('mahoning-2020','mahoning','evidence/finaldiscovery/mahoning-2020.bin','Precints_2020','historical 2020; native filename spells Precints','Mahoning County GIS','https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/'),('butler-2019','butler','evidence/late5/butler-2019-zip.bin','2019 Precinct Shapefile/2019_Butler_County_Precincts','historical 2019 BOE ZIP retained through archive 2021-02-06','Butler County BOE','https://elections.bcohio.gov/maps/precinct_maps.php'),('fairfield-published','fairfield','evidence/late/fairfield-zip.bin','Precincts','county download listing 2026-10-12; effective boundary date unestablished','Fairfield County Auditor GIS','https://www.co.fairfield.oh.us/gis/')]
 for did,county,path,stem,vintage,authority,url in specs:
  if not (ROOT/path).exists():continue
  print('LOAD',did,flush=True);parts=zip_parts(path,stem);fs,crs,nv=load_shp(parts)
  out.append(dict(dataset_id=did,county=county,features=fs,crs=crs,source_vertices=nv,conversion_notes=[],kind='shapefile-zip',original_path=path,shapefile_stem=stem,vintage=vintage,authority=authority,url=url,approved_nov2026=False))
 # Full native WFS GML geometry; server omits all IDs and attributes.
 x=ET.fromstring(read('evidence/resolve/medina-features.gz'));members=x.findall('{http://www.opengis.net/gml}featureMember');fs=[];nv=0
 for m in members:
  ps=[]
  for p in m.findall('.//{http://www.opengis.net/gml}Polygon'):
   def ring(elem):return [[float(v) for v in a.split(',')] for a in elem.text.split()]
   outer=p.find('.//{http://www.opengis.net/gml}outerBoundaryIs//{http://www.opengis.net/gml}coordinates');ins=p.findall('.//{http://www.opengis.net/gml}innerBoundaryIs//{http://www.opengis.net/gml}coordinates');shell=ring(outer);holes=[ring(a) for a in ins];nv+=len(shell)+sum(map(len,holes));ps.append(Polygon(shell,holes))
  fs.append(({},ps[0] if len(ps)==1 else MultiPolygon(ps)))
 hits=ET.fromstring(read('evidence/finish/medina-hits.gz'));assert len(fs)==int(hits.get('numberOfFeatures'))==203
 assert read('evidence/finish/medina-highlimit.gz')==read('evidence/resolve/medina-features.gz')
 assert len(ET.fromstring(read('evidence/finish/medina-first10.gz')).findall('{http://www.opengis.net/gml}featureMember'))==10
 out.append(dict(dataset_id='medina-wfs',county='medina',features=fs,crs='EPSG:3753',source_vertices=nv,conversion_notes=['GML WFS has geometry only: no feature IDs or precinct names. Positional ordinal is not a precinct ID.','Capabilities misnames projected bounds as LatLongBoundingBox. No correction to original.'],kind='WFS-GML',original_path='evidence/resolve/medina-features.gz',vintage='BOE-linked county GeoMOOSE publication; effective date unestablished',authority='Medina County GIS (BOE-linked)',url='https://gm.medinaco.org/',approved_nov2026=False,pagination='WFS1.1 hits 203 equals unbounded/100000-maxfeatures 203; 10-feature control returns 10'))
 return out

def verts(g):
 if g.geom_type=='Polygon':return len(g.exterior.coords)+sum(len(r.coords) for r in g.interiors)
 if g.geom_type=='MultiPolygon':return sum(verts(p) for p in g.geoms)
 return 0

def preview(dataset,fs):
 if not any(not g.is_empty for a,g in fs):
  p=ROOT/'derived'/f'{dataset}.svg';p.parent.mkdir(exist_ok=True);p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 520"><rect width="740" height="520" fill="#fff5ed"/><text x="30" y="240" font-size="22">Source returned records without geometry</text></svg>');return None
 minx=min(g.bounds[0] for a,g in fs if not g.is_empty);miny=min(g.bounds[1] for a,g in fs if not g.is_empty);maxx=max(g.bounds[2] for a,g in fs if not g.is_empty);maxy=max(g.bounds[3] for a,g in fs if not g.is_empty)
 s=min(700/(maxx-minx),480/(maxy-miny));ox=(740-(maxx-minx)*s)/2;oy=(520-(maxy-miny)*s)/2
 paths=[]
 for i,(a,g) in enumerate(fs):
  rings=[]
  for p in ([g] if g.geom_type=='Polygon' else g.geoms):
   for r in [p.exterior,*p.interiors]:rings.append('M'+' L'.join(f'{ox+(x-minx)*s:.2f},{520-oy-(y-miny)*s:.2f}' for x,y,*_ in r.coords)+' Z')
  paths.append(f'<path d="{" ".join(rings)}" fill="hsl({(i*137)%360} 45% 85%)" stroke="#264653" stroke-width="0.45" fill-rule="evenodd"><title>{html.escape(json.dumps(a,ensure_ascii=False))}</title></path>')
 p=ROOT/'derived'/f'{dataset}.svg';p.parent.mkdir(exist_ok=True);p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 740 520" role="img"><title>'+html.escape(dataset)+'; display preview, no legal approval</title><rect width="740" height="520" fill="#f7fafb"/>'+''.join(paths)+'</svg>')
 return [minx,miny,maxx,maxy]

def diagnostics(d):
 fs=d['features'];geoms=[g for _,g in fs];invalid=[];empty=[];unclosed=[];finite=True
 for i,(a,g) in enumerate(fs):
  if g.is_empty:empty.append(i)
  elif not g.is_valid:invalid.append(dict(source_feature_ordinal=i,attributes=a,reason=explain_validity(g)))
  if not g.is_empty and not all(math.isfinite(v) for v in g.bounds):finite=False
 tree=STRtree(geoms);pairs=[];errors=[]
 for i,g in enumerate(geoms):
  for j in tree.query(g):
   j=int(j)
   if j<=i:continue
   try:
    area=g.intersection(geoms[j]).area
    if area>0:pairs.append({'left_ordinal':i,'right_ordinal':j,'area_in_crs_squared_units':area})
   except Exception as e:errors.append({'left_ordinal':i,'right_ordinal':j,'error':str(e)})
 fields=sorted(set(k for a,g in fs for k in a));ids={}
 for f in fields:
  values=[a.get(f) for a,g in fs];nonblank=[str(v) for v in values if v is not None and str(v).strip()!=''];cnt=collections.Counter(nonblank)
  ids[f]={'nonblank':len(nonblank),'blank_or_null':len(fs)-len(nonblank),'unique_nonblank':len(cnt),'reused_values':{k:v for k,v in cnt.items() if v>1},'examples':nonblank[:8]}
 return dict(feature_count=len(fs),source_vertices=d['source_vertices'],derived_vertices=sum(verts(g) for g in geoms),empty_ordinals=empty,invalid_features=invalid,finite_bounds=finite,overlap_pairs=pairs,intersection_errors=errors,id_field_diagnostics=ids,checks_do_not_approve_boundaries=True)

def build():
 rows=list(csv.DictReader((STATE/'data/county-turnout.csv').open()));byname={r['county'].lower():r for r in rows};priority=[r for r in rows if r['in_minimum80']=='1'];ds=all_datasets();summaries=[]
 # Census all88: retain statewide ZIP once, no cross-year code join.
 p='evidence/finaldiscovery/census-state-vtd.bin';fs,crs,nv=load_shp(zip_parts(p,'tl_2020_39_vtd20'));groups=collections.defaultdict(list)
 for a,g in fs:groups[a['STATEFP20']+a['COUNTYFP20']].append((a,g))
 assert set(groups)=={r['county_fips'] for r in rows}
 census_summary={}
 for r in rows:
  f=groups[r['county_fips']];census_summary[r['county_fips']]={'features':len(f),'native_ids':[a['GEOID20'] for a,g in f],'vtd_native_codes':[a['VTDST20'] for a,g in f],'vtd_indicators':dict(collections.Counter(a['VTDI20'] for a,g in f))}
  if r['in_minimum80']=='1':ds.append(dict(dataset_id='census2020-'+r['county'].lower(),county=r['county'].lower(),features=f,crs=crs,source_vertices=sum(verts(g) for a,g in f),conversion_notes=['2020 Census statistical VTD; not approved November 2026 precincts. No historical result join.'],kind='Census-VTD-historical',original_path=p,shapefile_stem='tl_2020_39_vtd20',vintage='2020 Census P.L.94-171 TIGER/Line; historical statistical reference',authority='US Census Bureau; county election authority remains county BOE',url='https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/tl_2020_39_vtd20.zip',approved_nov2026=False))
 jwrite('census-all88-inventory.json',census_summary)
 for d in ds:
  did=d['dataset_id'];fs=d['features'];r=byname[d['county']];assert fs
  dg=diagnostics(d);assert dg['source_vertices']==dg['derived_vertices'],(did,dg['source_vertices'],dg['derived_vertices'])
  crs=pyproj.CRS.from_user_input(d['crs']);tr=pyproj.Transformer.from_crs(crs,'EPSG:4326',always_xy=True)
  derived=[dict(type='Feature',properties=dict(a,research_county_fips=r['county_fips'],research_source_ordinal=i),geometry=mapping(transform(tr.transform,g))) for i,(a,g) in enumerate(fs)]
  gj={'type':'FeatureCollection','name':did,'research_provenance':{'source_crs':crs.to_wkt(),'output_crs':'OGC:CRS84 longitude latitude','transform':tr.description,'transform_accuracy_metres':tr.accuracy,'simplification':'none; every ring vertex retained; native true curves, if present, use explicitly identified server linearization in derivatives','approved_nov2026':False},'features':derived}
  b=json.dumps(gj,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();p=ROOT/'derived'/f'{did}.geojson.gz';p.parent.mkdir(exist_ok=True);p.write_bytes(gzip.compress(b,mtime=0))
  extent=preview(did,fs);dg['extent_native']=extent;dg['crs_wkt']=crs.to_wkt();jwrite('diagnostics/'+did+'.json',dg)
  summary={k:v for k,v in d.items() if k not in ['features','crs']};summary.update(county_fips=r['county_fips'],feature_count=len(fs),crs_wkt=crs.to_wkt(),crs_authority=crs.to_authority(),extent_native=extent,invalid_count=len(dg['invalid_features']),empty_count=len(dg['empty_ordinals']),overlap_count=len(dg['overlap_pairs']),intersection_error_count=len(dg['intersection_errors']),geojson_path='derived/'+did+'.geojson.gz',preview_path='derived/'+did+'.svg',diagnostics_path='diagnostics/'+did+'.json',id_field_diagnostics=dg['id_field_diagnostics'])
  summaries.append(summary);print(did,len(fs),'invalid',summary['invalid_count'],'overlaps',summary['overlap_count'],flush=True)
 jwrite('dataset-manifest.json',summaries)
 jwrite('build-environment.json',{'python':sys.version,'shapely':shapely.__version__,'GEOS':shapely.geos_version_string,'pyproj':pyproj.__version__,'PROJ':pyproj.proj_version_str,'pyshp':shapefile.__version__,'PROJ_NETWORK':'OFF','originals':'unchanged source responses, ZIP components and GML','preview':'native coordinates fitted to SVG; display positions rounded to 0.01 SVG unit only','GeoJSON':'full vertex count, XY projected to CRS84; native originals retain Z/M/SR metadata'})
if __name__=='__main__':build()
