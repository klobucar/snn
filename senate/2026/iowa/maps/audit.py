#!/usr/bin/env python3
"""Offline native archive audit; originals and defects are never repaired."""
import collections, gzip, hashlib, html, io, json, math, pathlib, struct, warnings, zipfile
import shapefile, shapely, pyproj
from shapely.geometry import shape
from shapely.validation import explain_validity
from shapely.ops import transform
from PIL import Image, ImageDraw
from acquire import ROOT, body, sha, write_json

def json_safe(x):
    if isinstance(x,dict):return {str(k):json_safe(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [json_safe(v) for v in x]
    if isinstance(x,float) and not math.isfinite(x):return {'nonfinite_literal':repr(x)}
    if hasattr(x,'isoformat'):return x.isoformat()
    return x
def gzjson(path,d):path.write_bytes(gzip.compress(json.dumps(json_safe(d),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0))
def preview(features,crs,path,title):
    """Full vertex display derivative only; source points are retained separately."""
    project=pyproj.Transformer.from_crs(crs,'EPSG:5070',always_xy=True).transform if crs else None
    rings=[]
    for f in features:
        pts=f['points']; parts=f['parts']+[len(pts)]
        for a,b in zip(parts,parts[1:]):
            ring=pts[a:b]
            if not ring:continue
            try:r=[project(*p[:2]) if project else p[:2] for p in ring]
            except Exception:continue
            if all(math.isfinite(v) for p in r for v in p):rings.append((f['record_ordinal'],r))
    if not rings:return None
    xs=[p[0] for _,r in rings for p in r];ys=[p[1] for _,r in rings for p in r]
    bounds=[min(xs),min(ys),max(xs),max(ys)];dx=bounds[2]-bounds[0];dy=bounds[3]-bounds[1]
    if not dx or not dy:return None
    sc=min(920/dx,820/dy);ox=(1000-dx*sc)/2;oy=90+(820-dy*sc)/2
    im=Image.new('RGB',(1000,1000),'#f7f8fa');draw=ImageDraw.Draw(im)
    draw.text((25,20),title[:110],fill='#112740');draw.text((25,43),'Reference preview | no approved 2026 reporting crosswalk',fill='#98330c')
    for n,r in rings:
        xy=[(ox+(x-bounds[0])*sc,oy+(bounds[3]-y)*sc) for x,y in r]
        draw.line(xy,fill='#234e72',width=1)
    draw.text((25,950),'Full vertices projected to EPSG:5070, fitted to pixels; no source simplification/repair.',fill='#31465a')
    im.save(path)
    return dict(path=str(path.relative_to(ROOT)),display_crs='EPSG:5070' if crs else 'native unknown; no transform',bounds=bounds,vertex_simplification=False)

def audit_archive(m):
    key=m['source_id']; data=body(m);out=dict(source_id=key,source_path=m.get('path'),source_sha256=m['entity_sha256'])
    z=zipfile.ZipFile(io.BytesIO(data));out['zip_crc_bad_member']=z.testzip()
    out['members']=[dict(name=i.filename,bytes=i.file_size,compressed_bytes=i.compress_size,crc32=f'{i.CRC:08x}',sha256=sha(z.read(i))) for i in z.infolist() if not i.is_dir()]
    ns={n.lower():n for n in z.namelist()}; layers=[]
    for name in z.namelist():
        if not name.lower().endswith('.shp'):continue
        base=name[:-4]; lk=key+'--'+str(len(layers)+1)
        kw={e:io.BytesIO(z.read(ns[(base+'.'+e).lower()])) for e in ['shp','shx','dbf'] if (base+'.'+e).lower() in ns}
        prjname=ns.get((base+'.prj').lower());wkt=z.read(prjname).decode('utf-8-sig','replace') if prjname else None
        crs=pyproj.CRS.from_wkt(wkt) if wkt else None
        cpgname=ns.get((base+'.cpg').lower());encoding=z.read(cpgname).decode().strip() if cpgname else 'utf-8'
        r=shapefile.Reader(**kw,encoding=encoding,encodingErrors='strict')
        fields=[list(f) for f in r.fields[1:]]
        native=[];checks=[];geoms=[];projected=[];caught=[]
        with warnings.catch_warnings(record=True) as ws:
            for ordinal,sr in enumerate(r.iterShapeRecords(),1):
                s=sr.shape;points=[list(p) for p in s.points];attrs=sr.record.as_dict()
                f=dict(record_ordinal=ordinal,ordinal_is_native_id=False,attributes=attrs,shape_type=s.shapeType,points=points,parts=list(s.parts),z=list(s.z) if hasattr(s,'z') else None,m=list(s.m) if hasattr(s,'m') else None)
                native.append(f);finite=all(math.isfinite(v) for p in points for v in p)
                signed=[];part_starts=list(s.parts)+[len(points)]
                for start,end in zip(part_starts,part_starts[1:]):
                    ring=points[start:end];signed.append(sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(ring,ring[1:]+ring[:1]))/2 if ring and finite else None)
                ck=dict(record_ordinal=ordinal,vertices=len(points),parts=len(s.parts),empty=not points,nonfinite=not finite,native_ring_signed_areas=signed,ring_area_note='native coordinate squared values used only to diagnose ring orientation; not physical areas',native_clockwise_exteriors=sum(v is not None and v<0 for v in signed),native_ccw_holes=sum(v is not None and v>0 for v in signed),z_nonfinite=sum(not math.isfinite(v) for v in f['z'] if v is not None) if f['z'] else 0,m_nonfinite=sum(not math.isfinite(v) for v in f['m'] if v is not None) if f['m'] else 0,native_ids={k:v for k,v in attrs.items() if k.upper() in ['ID','FID','OBJECTID','LONGNAME','SHORTNAME','NAME','DISTRICT']})
                g=None;pg=None
                if points and finite:
                    try:
                        g=shape(s.__geo_interface__);ck.update(valid=g.is_valid,validity_reason=explain_validity(g),geometry_type=g.geom_type)
                        if crs and g.is_valid:
                            pg=transform(pyproj.Transformer.from_crs(crs,'EPSG:5070',always_xy=True).transform,g)
                    except Exception as e:ck.update(valid=False,geometry_error=str(e))
                else:ck.update(valid=False,validity_reason='empty or nonfinite')
                geoms.append(g);projected.append(pg);checks.append(ck)
            caught=[str(x.message) for x in ws]
        overlaps=[];skipped=[]
        for i,g in enumerate(projected):
            if g is None:skipped.append(i+1);continue
            for j in range(i+1,len(projected)):
                h=projected[j]
                if h is None or not g.intersects(h):continue
                try:
                    a=g.intersection(h).area
                    if a>0:
                        native_area=geoms[i].intersection(geoms[j]).area if crs.is_projected else None
                        overlaps.append(dict(record_ordinals=[i+1,j+1],intersection_area=a,units='square metres',operation_crs='EPSG:5070',native_projected_intersection_area=native_area,native_projected_area_units=('square '+crs.axis_info[0].unit_name) if native_area is not None else None,native_area_unavailable_reason=None if native_area is not None else 'native CRS angular; no physical area assigned to square degrees',operation='separate equal-area projected derivative; original native geometry unchanged'))
                except Exception as e:overlaps.append(dict(record_ordinals=[i+1,j+1],error=str(e)))
        shp=z.read(name);dbf=z.read(ns[(base+'.dbf').lower()]);shx=z.read(ns[(base+'.shx').lower()]) if (base+'.shx').lower() in ns else None
        dbf_count=struct.unpack('<I',dbf[4:8])[0]; shp_records=0;pos=100;record_numbers=[]
        while pos+8<=len(shp):
            num,words=struct.unpack('>ii',shp[pos:pos+8]);record_numbers.append(num);shp_records+=1;pos+=8+words*2
        layer=dict(layer_key=lk,shp_member=name,dbf_fields=fields,dbf_encoding=encoding,cpg_present=bool(cpgname),wkt_original=wkt,crs_authority=crs.to_authority() if crs else None,axis_info=[dict(name=a.name,abbreviation=a.abbrev,direction=a.direction,unit=a.unit_name,conversion_factor=a.unit_conversion_factor) for a in crs.axis_info] if crs else None,shapefile_xy_order='stored X,Y; preview transform always_xy=True',shp_shape_type=r.shapeType,shp_records=shp_records,shp_record_header_numbers=record_numbers,dbf_declared_records=dbf_count,shx_records=(len(shx)-100)//8 if shx else None,parsed_records=len(native),vertices=sum(len(f['points']) for f in native),parts=sum(len(f['parts']) for f in native),z_returned=any(f['z'] is not None for f in native),m_returned=any(f['m'] is not None for f in native),curves_supported=False,curves_actually_returned=False,curve_note='ESRI shapefile stores linear vertices; original ZIP fully retained',native_extent=list(r.bbox),feature_checks=checks,overlap_checks=overlaps,overlap_skipped_invalid_or_unknown_crs=skipped,warnings=caught,record_balance=shp_records==dbf_count==len(native) and (shx is None or (len(shx)-100)//8==len(native)),trailing_shp_bytes=len(shp)-pos)
        derivative=ROOT/'native'/f'{lk}.json.gz'
        gzjson(derivative,dict(source_id=key,layer_key=lk,wkt_original=wkt,fields=fields,features=native,operation='unmodified native points/parts/Z/M/attributes decoded; originals authoritative for raw DBF bytes and types'))
        layer['native_derivative']=str(derivative.relative_to(ROOT))
        layer['topology_interpretation']='pyshp GeoJSON ring interpretation; orientation/orphan-hole fallback may interpret a hole as exterior for diagnostic geometry only; native ring vertices/parts unchanged. Preview draws all original rings as lines.'
        layer['preview']=preview(native,crs,ROOT/'previews'/f'{lk}.png',name)
        layers.append(layer)
    out['layers']=layers
    out['pagination']='not applicable: static full ZIP; all members/CRC/records inspected'
    return out
def main():
    for d in ['native','previews','audit']:(ROOT/d).mkdir(exist_ok=True)
    audit=[]
    for meta in sorted((ROOT/'raw').glob('*.meta.json')):
        m=json.loads(meta.read_text())
        if m.get('status')!=200 or not m.get('path','').endswith('.zip'):continue
        cache=ROOT/'audit'/(m['source_id']+'.json')
        if cache.exists():a=json.loads(cache.read_text())
        else:
            try:a=audit_archive(m)
            except Exception as e:a=dict(source_id=m['source_id'],error=type(e).__name__+': '+str(e))
            write_json(cache,a)
        audit.append(a)
    write_json(ROOT/'geometry-audit.json',dict(schema_version=1,software=dict(pyshp=shapefile.__version__,shapely=shapely.__version__,pyproj=pyproj.__version__),archives=audit))
    print(json.dumps(dict(archives=len(audit),layers=sum(len(a.get('layers',[])) for a in audit),errors=[a for a in audit if a.get('error')],invalid=sum(not f['valid'] for a in audit for l in a.get('layers',[]) for f in l['feature_checks']))))
if __name__=='__main__':main()
