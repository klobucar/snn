#!/usr/bin/env python3
"""Offline lossless county SHP subsets, all-county/source-row diagnostics, previews.
Native SHP record bodies and DBF records are copied verbatim, not reserialized.
"""
import csv, gzip, io, json, struct, zipfile, logging, collections, math
from pathlib import Path
import shapefile
from shapely.geometry import shape
from shapely.validation import explain_validity
from shapely.strtree import STRtree
from pyproj import CRS, Transformer
from PIL import Image, ImageDraw, ImageFont
from acquire import ROOT, original, sha, save_json

logging.getLogger('shapefile').setLevel(logging.ERROR)
DATA=ROOT.parent/'data'
VINTAGES={'24g':'2024 general','26p':'2026 primary','22g':'2022 general','20g':'2020 general'}
def csv_gz(path,rows,fields=None):
 path.parent.mkdir(exist_ok=True,parents=True)
 with gzip.GzipFile(filename='',fileobj=path.open('wb'),mode='wb',mtime=0) as g:
  with io.TextIOWrapper(g,encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def preview(path, geoms, title, subtitle, ids):
 """Draw full source rings to raster; only pixel display quantization, no source edits."""
 good=[g for g in geoms if g and not g.is_empty]
 im=Image.new('RGB',(1000,900),'#f7f8fa');d=ImageDraw.Draw(im)
 if good:
  boxes=[g.bounds for g in good];x0=min(b[0] for b in boxes);y0=min(b[1] for b in boxes);x1=max(b[2] for b in boxes);y1=max(b[3] for b in boxes)
  scale=min(930/max(x1-x0,1),750/max(y1-y0,1));dx=(1000-(x1-x0)*scale)/2
  def ring(coords):return [(dx+(p[0]-x0)*scale,825-(p[1]-y0)*scale) for p in coords]
  for i,g in enumerate(geoms):
   if not g or g.is_empty:continue
   for poly in ([g] if g.geom_type=='Polygon' else g.geoms if g.geom_type=='MultiPolygon' else []):
    if not poly.is_empty:
     d.polygon(ring(poly.exterior.coords),fill=('#d8e6ef' if i%2 else '#edf2d9'),outline='#405b70')
     for h in poly.interiors:d.polygon(ring(h.coords),fill='#f7f8fa',outline='#405b70')
   if len(geoms)<150 and g.is_valid:
    p=g.representative_point();d.text(ring([(p.x,p.y)])[0],str(ids[i]),fill='#122c40',anchor='mm')
 d.text((28,22),title,fill='#122c40',font_size=25)
 d.text((28,59),subtitle[:135],fill='#405b70',font_size=15)
 d.text((28,859),'Reference geometry. No November approval or results-to-polygon crosswalk inferred.',fill='#5c4652',font_size=15)
 path.parent.mkdir(parents=True,exist_ok=True);im.save(path,optimize=True)

def raw_subset(z,base,indices,shapes,path):
 shp=z.read(base+'.shp');shx=z.read(base+'.shx');dbf=z.read(base+'.dbf')
 hlen,rlen=struct.unpack_from('<HH',dbf,8)
 header=bytearray(shp[:100]);newshp=bytearray(header);newshx=bytearray(shx[:100]);newdbf=bytearray(dbf[:hlen]);struct.pack_into('<I',newdbf,4,len(indices))
 boxes=[s.bbox for s in shapes if s.shapeType and s.bbox]
 bbox=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else [0]*4
 geometry_body_hashes=[];attribute_hashes=[]
 for k,i in enumerate(indices):
  off,length=struct.unpack_from('>ii',shx,100+8*i);body=shp[off*2+8:off*2+8+length*2]
  assert len(body)==length*2
  newshx.extend(struct.pack('>ii',len(newshp)//2,length));newshp.extend(struct.pack('>ii',k+1,length));newshp.extend(body)
  row=dbf[hlen+i*rlen:hlen+(i+1)*rlen];newdbf.extend(row)
  geometry_body_hashes.append(sha(body));attribute_hashes.append(sha(row))
 newdbf.extend(b'\x1a')
 for b in [newshp,newshx]:struct.pack_into('>i',b,24,len(b)//2);struct.pack_into('<4d',b,36,*bbox)
 path.parent.mkdir(exist_ok=True,parents=True)
 def write(zout,name,b):
  zi=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zout.writestr(zi,b)
 with zipfile.ZipFile(path,'w') as out:
  for ext,b in [('.shp',newshp),('.shx',newshx),('.dbf',newdbf)]:write(out,'precincts'+ext,b)
  for ext in ['.prj','.cpg']:
   if base+ext in z.namelist():write(out,'precincts'+ext,z.read(base+ext))
 # Reopen and verify bytewise feature/attribute coverage, not just feature count.
 with zipfile.ZipFile(path) as out:
  assert out.testzip() is None
  a=out.read('precincts.shp');b=out.read('precincts.shx');c=out.read('precincts.dbf')
  assert (len(b)-100)//8==len(indices)==struct.unpack_from('<I',c,4)[0]
  for k,(gh,ah) in enumerate(zip(geometry_body_hashes,attribute_hashes)):
   off,n=struct.unpack_from('>ii',b,100+k*8)
   assert sha(a[off*2+8:off*2+8+n*2])==gh and sha(c[hlen+k*rlen:hlen+(k+1)*rlen])==ah
 return dict(path=str(path.relative_to(ROOT)),features=len(indices),source_row_indices_zero_based=indices,raw_geometry_record_sha256=geometry_body_hashes,raw_dbf_record_sha256=attribute_hashes,bbox_native=bbox,bytes=path.stat().st_size,sha256=sha(path.read_bytes()),bytewise_reopen_check=True)

def overlaps(geoms,rowids):
 valid=[(i,g) for i,g in enumerate(geoms) if g and not g.is_empty and g.is_valid]
 shapes=[g for i,g in valid];tree=STRtree(shapes);found=[]
 for i,g in enumerate(shapes):
  for j in tree.query(g,predicate='intersects'):
   j=int(j)
   if j<=i:continue
   ar=g.intersection(shapes[j]).area
   if ar>0:found.append(dict(source_row_a=rowids[valid[i][0]],source_row_b=rowids[valid[j][0]],intersection_native_square_units=ar))
 return dict(checked_valid_nonempty=len(valid),excluded_invalid_or_empty=len(geoms)-len(valid),positive_area_pair_count=len(found),pairs=found)

def main():
 counties=list(csv.DictReader((DATA/'county-turnout.csv').open()));keys=(DATA/'coordinator-priority-keys.txt').read_bytes()
 assert sha(keys)=='a5d39344328ab3c0f76809439c6af42c09a59d81f76b9b756e5b538a63ac5be5'
 priority=keys.decode().splitlines();assert [c['dispatch_key'] for c in counties[:34]]==priority
 audits=[];units=[];bymap=collections.defaultdict(dict)
 for vint,label in VINTAGES.items():
  meta=json.loads((ROOT/'sources'/f'tlc-{vint}.json').read_text());z=zipfile.ZipFile(io.BytesIO(original(meta)));assert z.testzip() is None
  base=next(n[:-4] for n in z.namelist() if n.lower().endswith('.shp'))
  sb=z.read(base+'.shp');xb=z.read(base+'.shx');db=z.read(base+'.dbf');wkt=z.read(base+'.prj').decode();crs=CRS.from_wkt(wkt)
  r=shapefile.Reader(shp=io.BytesIO(sb),shx=io.BytesIO(xb),dbf=io.BytesIO(db),encoding=z.read(base+'.cpg').decode().strip() if base+'.cpg' in z.namelist() else 'utf-8')
  assert len(r)==(len(xb)-100)//8==struct.unpack_from('<I',db,4)[0]
  assert struct.unpack_from('>i',sb,24)[0]*2==len(sb)
  (ROOT/'crs').mkdir(exist_ok=True);(ROOT/'crs'/f'tlc-{vint}.wkt').write_text(wkt+'\n')
  features=collections.defaultdict(list);polyissues=[];attrs=[];allkeys=[];vertex_total=0
  for i,sr in enumerate(r.iterShapeRecords()):
   attr=sr.record.as_dict();cnty=attr['CNTY'];fips='48'+str(cnty).zfill(3);k=str(attr['PCTKEY']);allkeys.append(k)
   # Never repair the source; null/invalid geometries remain in the original/subset.
   g=shape(sr.shape.__geo_interface__) if sr.shape.shapeType else None
   valid=bool(g and not g.is_empty and g.is_valid);reason='null' if g is None else explain_validity(g)
   if not valid:polyissues.append(dict(source_row=i,PCTKEY=k,county_fips=fips,reason=reason))
   vertices=len(sr.shape.points);vertex_total+=vertices
   u=dict(source_id='tlc-'+vint,vintage=label,county_fips=fips,source_row_index=i,native_PREC=str(attr['PREC']),native_PCTKEY=k,parts=len(sr.shape.parts),vertices=vertices,geometry_status='valid' if valid else reason,geometry_type=sr.shape.shapeTypeName,hasZ=hasattr(sr.shape,'z'),hasM=hasattr(sr.shape,'m'),true_curves='not supported by shapefile polygon format',attributes_json=json.dumps(attr,ensure_ascii=False,separators=(',',':')))
   units.append(u);features[fips].append((i,sr.shape,attr,g))
  assert set(features)=={c['county_fips'] for c in counties}
  a=dict(source_id='tlc-'+vint,vintage=label,original_sha256=meta['original_sha256'],source_features=len(r),dbf_record_count=len(r),shx_record_count=(len(xb)-100)//8,source_shp_bytes=len(sb),source_vertices=vertex_total,all_counties=len(features),source_county_codes=sorted(features),native_wkt=wkt,crs_name=crs.name,axis_order=[dict(name=x.name,direction=x.direction,unit=x.unit_name) for x in crs.axis_info],shapeType=r.shapeType,hasZ=False,hasM=False,true_curves='Shapefile Polygon type5 has no curve/Z/M support; all record bodies retained verbatim.',pagination='Not applicable: complete original ZIP; ZIP CRC, SHP length, SHX and DBF counts checked; every record iterated.',source_metadata_members=[n for n in z.namelist() if n.endswith('.xml')],invalid_or_empty=polyissues,duplicate_PCTKEY=[k for k,n in collections.Counter(allkeys).items() if n>1],fields=[list(f) for f in r.fields[1:]],counties=[])
  for c in counties:
   fips=c['county_fips'];ff=features[fips];idx=[x[0] for x in ff];shapes=[x[1] for x in ff];geoms=[x[3] for x in ff];ids=[str(x[2]['PREC']) for x in ff]
   ca=dict(county_fips=fips,county=c['county'],features=len(ff),vertices=sum(len(s.points) for s in shapes),source_rows=idx,native_ids=ids,duplicate_PREC=[k for k,n in collections.Counter(ids).items() if n>1])
   # Native projected units, never degrees. This is planar diagnostic area, not legal/ground area.
   ca['overlap']=overlaps(geoms,idx);ca['overlap']['unit']='square metre in source NAD83 Texas Lambert Conformal Conic; planar diagnostic, not geodesic or legal area'
   if c['dispatch_key'] in priority:
    ca['subset']=raw_subset(z,base,idx,shapes,ROOT/'counties'/f'{fips}-{vint}.zip')
    if vint in ['24g','26p']:
     path=ROOT/'previews'/f'{fips}-{vint}.png';preview(path,geoms,c['county']+' | '+label,f'{len(ff)} native precinct features; TLC county-collected reference; projected in source CRS',ids);ca['preview']=str(path.relative_to(ROOT))
   a['counties'].append(ca);bymap[fips][vint]=dict(features=len(ff),vertices=ca['vertices'],invalid_or_empty=sum(not (g and g.is_valid and not g.is_empty) for g in geoms),duplicate_PREC=ca['duplicate_PREC'],overlap_pairs=ca['overlap']['positive_area_pair_count'])
  audits.append(a);save_json(ROOT/'geometry'/f'tlc-{vint}-audit.json',a);print(vint,len(r),vertex_total,'done',flush=True)
 csv_gz(ROOT/'inventory/native-geometry-units.csv.gz',units)
 save_json(ROOT/'geometry/summary.json',dict(vintages=[dict(source_id=a['source_id'],features=a['source_features'],vertices=a['source_vertices'],invalid_or_empty=len(a['invalid_or_empty']),duplicate_PCTKEY=a['duplicate_PCTKEY']) for a in audits],counties=bymap))

if __name__=='__main__':main()
