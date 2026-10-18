#!/usr/bin/env python3
"""County GIS diagnostics in native CRS. Raw ArcGIS pages are authoritative originals."""
import collections,csv,io,json,zipfile
import shapefile
from shapely.geometry import shape
from shapely.validation import explain_validity
from pyproj import CRS,Transformer
from acquire import ROOT,original,sha,save_json
from build_geometry import csv_gz,preview,overlaps

def main():
 counties=list(csv.DictReader((ROOT.parent/'data/county-turnout.csv').open()));fipsby={c['county']:c['county_fips'] for c in counties};rows=[];audits=[]
 for p in sorted((ROOT/'gis').glob('*-audit.json')):
  a=json.loads(p.read_text())
  if a.get('status')!='pass':continue
  key=a['id'];units=[];geoms=[];ids=[];raw_features=[];sr=a['native_spatial_reference']
  crs=CRS.from_wkt(sr['wkt']) if sr.get('wkt') else CRS.from_user_input('EPSG:'+str(sr.get('latestWkid') or sr['wkid']))
  trans=Transformer.from_crs(crs,4326,always_xy=True)
  field={'bexar-voter':'NAME','travis-precincts':'Precinct','fort-bend-2025':'NAME','fort-bend-2022':'NAME','brazoria-2024':'PRECINCT','brazoria-2026':'PRECINCT','bell-2022':'EP','hays-2026':'VTD','johnson-2022':'DISTRICT'}[key]
  actual=collections.Counter();issues=[];bounds=[];dims=collections.Counter();curves=0
  for batch in a['batches']:
   meta=json.loads((ROOT/'sources'/(batch['source_id']+'.json')).read_text());j=json.loads(original(meta))
   assert [f['attributes'][a['object_id_field']] for f in j['features']]==batch['returned_ids']
   for f in j['features']:
    raw_features.append(f);attr=f['attributes'];oid=attr[a['object_id_field']];ident=str(attr.get(field));ids.append(ident);g=f.get('geometry');geom=None;reason='empty geometry';vertices=0;curve=bool(g and (g.get('curveRings') or g.get('curvePaths')))
    if curve:curves+=1;reason='true curves retained in original; excluded from linear-only preview/overlap'
    elif g and g.get('rings'):
     pts=[];parts=[]
     for ring in g['rings']:
      parts.append(len(pts));pts.extend([pt[:2] for pt in ring]);dims.update(len(pt) for pt in ring)
     s=shapefile.Shape(shapeType=5,points=pts,parts=parts)
     vertices=len(s.points);geom=shape(s.__geo_interface__);reason='valid' if geom.is_valid else explain_validity(geom)
    if geom and not geom.is_empty:
     box=geom.bounds;corners=[trans.transform(x,y) for x,y in [(box[0],box[1]),(box[2],box[3])]];bounds.extend(corners)
     assert all(-108<x<-92 and 24<y<38 for x,y in corners),(key,corners)
    if reason!='valid':issues.append(dict(object_id=oid,native_id=ident,reason=reason))
    geoms.append(geom);actual[ident]+=1;units.append(oid)
    rows.append(dict(source_id=key,county_fips=fipsby[a['county']],object_id=oid,native_id_field=field,native_id=ident,geometry_status=reason,vertices=vertices,true_curve=curve,source_batch_id=batch['source_id'],attributes_json=json.dumps(attr,ensure_ascii=False,separators=(',',':'))))
  assert sorted(units)==a['pre_ids']==a['post_ids']
  pr=ROOT/'previews'/('gis-'+key+'.png');preview(pr,geoms,a['county']+' | '+key,f'{len(units)} source features; county GIS; native CRS units {crs.axis_info[0].unit_name}',ids)
  ov=overlaps(geoms,units);ov['unit']='square '+crs.axis_info[0].unit_name+' in native projected CRS; planar diagnostic, not geodesic/ground/legal area'
  out=dict(id=key,county=a['county'],county_fips=fipsby[a['county']],source_audit=str(p.relative_to(ROOT)),features=len(units),vertices=sum(r['vertices'] for r in rows if r['source_id']==key),native_id_field=field,duplicate_native_ids={k:v for k,v in actual.items() if v>1},geometry_issues=issues,true_curve_count=curves,actual_point_dimensions=dict(dims),advertised_hasZ=a.get('hasZ'),advertised_hasM=a.get('hasM'),requested_returnZ=True,requested_returnM=True,requested_returnTrueCurves=True,native_crs=crs.to_wkt(),axis_order=[dict(name=x.name,direction=x.direction,unit=x.unit_name) for x in crs.axis_info],preview=str(pr.relative_to(ROOT)),preview_operation='Native projected x/y to image pixels, all source rings drawn; Z/M ignored in display only; curves excluded and listed, source unchanged.',geographic_bounds_check=dict(transformer=trans.description,always_xy=True,observed_lonlat_bbox=[min(x for x,y in bounds),min(y for x,y in bounds),max(x for x,y in bounds),max(y for x,y in bounds)] if bounds else None),overlap=ov,approval='Unknown for November2026; Hays VTD field remains literally VTD, no Census/TLC equivalence assumed.')
  save_json(ROOT/'geometry'/('gis-'+key+'.json'),out);audits.append(out)
 # Additional original county-adopted / municipal-scope ZIPs, audited separately.
 zipaudits=[]
 for key,c,scope in [('extra-harris-zip-https','Harris','20211220 county-adopted historical precincts'),('extra-galveston-city-voting','Galveston','City-published voting precinct reference; countywide completeness and current approval unverified')]:
  d=json.loads((ROOT/'sources'/(key+'.json')).read_text());z=zipfile.ZipFile(io.BytesIO(original(d)));assert z.testzip() is None
  n=next(n[:-4] for n in z.namelist() if n.endswith('.shp'));r=shapefile.Reader(shp=io.BytesIO(z.read(n+'.shp')),shx=io.BytesIO(z.read(n+'.shx')),dbf=io.BytesIO(z.read(n+'.dbf')))
  native=[];zz=[];problems=[]
  for i,sr in enumerate(r.iterShapeRecords()):
   g=shape(sr.shape.__geo_interface__) if sr.shape.shapeType else None;reason='null' if g is None else explain_validity(g);zz.append(g)
   if reason!='Valid Geometry':problems.append(dict(source_row=i,reason=reason))
   native.append(dict(source_row=i,attributes=sr.record.as_dict(),vertices=len(sr.shape.points),parts=len(sr.shape.parts)))
  wkt=z.read(n+'.prj').decode();crs=CRS.from_wkt(wkt);ov=overlaps(zz,list(range(len(r))));ov['unit']='square '+crs.axis_info[0].unit_name+' in native projected CRS; planar diagnostic'
  pr=ROOT/'previews'/(key+'.png');preview(pr,zz,c+' | '+scope,'Original county/municipal source; source-specific scope; native projected CRS',[str(i) for i in range(len(r))])
  a=dict(source_id=key,county=c,features=len(r),scope=scope,fields=[list(f) for f in r.fields[1:]],native_crs=wkt,axis_order=[dict(name=x.name,direction=x.direction,unit=x.unit_name) for x in crs.axis_info],geometry_type=r.shapeType,geometry_issues=problems,overlap=ov,preview=str(pr.relative_to(ROOT)),attributes_and_vertices='Complete original ZIP retained unchanged; source-specific units below, no2024 or2026 crosswalk inferred.',native_rows=native)
  save_json(ROOT/'geometry'/(key+'.json'),a);zipaudits.append(dict(source_id=key,features=len(r),scope=scope))
 csv_gz(ROOT/'inventory/county-gis-units.csv.gz',rows)
 save_json(ROOT/'geometry/local-summary.json',dict(layers=[{k:v for k,v in a.items() if k not in ['overlap','native_crs']} for a in audits],features=sum(a['features'] for a in audits),original_zip_layers=zipaudits))
 print('local GIS',len(audits),'layers',len(rows),'features',flush=True)
if __name__=='__main__':main()
