"""Offline map inventory, precinct-page audit, geometry diagnostics and previews.

Requires requirements.txt and Poppler pdftotext/pdfinfo. Never allocates votes,
repairs geometry, simplifies coordinates, or infers cross-year equivalence.
"""
from pathlib import Path
import collections
import csv
import datetime as dt
import gzip
import hashlib
import html
import io
import json
import math
import re
import subprocess
import zipfile
import pymupdf as fitz
from PIL import Image, ImageDraw
import pyproj
import shapefile
import shapely
from shapely.geometry import shape, mapping
from shapely.ops import transform
from shapely.validation import explain_validity

ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent
ORDER=[6,9,3,8,23,29,25,30,24,34,11,35,16,7,36,2,26,15,28,4,21,27,33,10,1,12,5,17]
VINTAGES=['baseline-2024','current-retrieved-2026']
OWNER='State of Alaska Division of Elections'
APPROVAL='April 2024 adoption documented; November 3 2026 approval unknown'
LANDING='https://www.elections.alaska.gov/research/district-maps/'
manifest=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def raw(p):
    b=(ROOT/p).read_bytes()
    return gzip.decompress(b) if str(p).endswith('.gz') else b
def js(p): return json.loads(raw(p))
def save(p,x):
    q=ROOT/p; q.parent.mkdir(parents=True,exist_ok=True)
    q.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str)+'\n')
def csvout(p,rows):
    with (ROOT/p).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def asset(p,urls,vintage,crs='',features='',pages='',kind='derivative',hd='',note=''):
    q=ROOT/p
    metas=[js(u+'.retrieval.json') for u in urls]
    manifest.append(dict(local_path=p,asset_kind=kind,state_fips='02',county_fips='',
        native_geography='Alaska native House District '+str(hd) if hd else 'Alaska physical voting precincts statewide',
        native_house_district=hd,source_url=' | '.join(m['source_url'] for m in metas),
        official_owner=OWNER,geometry_vintage=vintage,
        approval_status=('Published DOE locator; election-effective adoption date not established; November 3 2026 approval unknown' if 'current' in vintage else APPROVAL),
        retrieved_utc=' | '.join(sorted(set(m['retrieved_utc'] for m in metas))),
        crs=crs,feature_count=features,page_count=pages,bytes=q.stat().st_size,
        sha256=sha(q.read_bytes()),source_raw_sha256=' | '.join(m['raw_sha256'] for m in metas),limitations=note))

def ring_geometry(rings):
    # ArcGIS rings use the same outer/inner winding convention as shapefiles.
    # pyshp groups existing rings without altering source coordinates.
    pts=[];parts=[]
    for ring in rings: parts.append(len(pts));pts.extend(ring)
    s=shapefile.Shape(shapeType=5,points=pts,parts=parts)
    return shape(s.__geo_interface__)

def load_geometries():
    archive='originals/AK_Election_Precincts_2023Final.zip'
    with zipfile.ZipFile(ROOT/archive) as z:
        assert z.testzip() is None
        r=shapefile.Reader(shp=io.BytesIO(z.read('Precincts.shp')),
            shx=io.BytesIO(z.read('Precincts.shx')),dbf=io.BytesIO(z.read('Precincts.dbf')))
        crs=pyproj.CRS.from_wkt(z.read('Precincts.prj').decode())
        assert crs.to_epsg()==3857
        baseline=[];ringchecks={'baseline-2024':[], 'current-retrieved-2026':[]}
        for record in r.iterShapeRecords():
            p=record.record.as_dict()
            s=record.shape
            ends=[*s.parts[1:],len(s.points)]
            rings=[s.points[start:end] for start,end in zip(s.parts,ends)]
            diag=ring_diagnostic(p['Precinct_N'][:6],rings)
            if diag:ringchecks['baseline-2024'].append(diag)
            baseline.append(dict(id=p['Precinct_N'][:6],hd=int(p['HouseDistr']),properties=p,
                geometry=shape(record.shape.__geo_interface__)))
        zip_members=[dict(name=i.filename,bytes=i.file_size,sha256=sha(z.read(i.filename))) for i in z.infolist()]
    current=[];batchfiles=[];returned=[]
    for q in sorted((ROOT/'raw').glob('locator-features-*.json.gz')):
        file=str(q.relative_to(ROOT));batchfiles.append(file);d=js(file)
        assert not d.get('exceededTransferLimit',False)
        assert d['spatialReference'].get('latestWkid',d['spatialReference']['wkid'])==3857
        for f in d['features']:
            p=f['attributes'];returned.append(p['OBJECTID'])
            diag=ring_diagnostic(p['Precinct_Number'][:6],f['geometry']['rings'])
            if diag:ringchecks['current-retrieved-2026'].append(diag)
            current.append(dict(id=p['Precinct_Number'][:6],hd=int(p['HouseDistrict']),properties=p,
                geometry=ring_geometry(f['geometry']['rings'])))
    ids=js('raw/locator-ids.json')['objectIds']
    count=js('raw/locator-count.json')['count']
    assert len(returned)==len(set(returned))==len(ids)==count==402
    assert sorted(returned)==sorted(ids)
    save('archive-members.json',zip_members)
    save('ring-orientation-checks.json',dict(vintages=ringchecks,
        conversion='pyshp groups clockwise shells and counterclockwise holes. When every ring is counterclockwise, pyshp emits each ring as a shell and warns. No coordinates are changed. Raw sources are authoritative; review these derivative interpretations before overlay.',
        repaired=False))
    save('pagination-checks.json',dict(source_count=count,object_ids=len(ids),returned_features=len(returned),
        batches=len(batchfiles),batch_size=50,complete=True,native_crs='EPSG:3857',
        parameters='objectIds batches; outFields=*; returnGeometry=true; no outSR, precision or quantization',
        source_files=batchfiles))
    return {'baseline-2024':baseline,'current-retrieved-2026':current},archive,batchfiles

def ring_diagnostic(pid,rings):
    a=[shapefile.signed_area(r) for r in rings]
    unclosed=[i for i,r in enumerate(rings) if r[0]!=r[-1]]
    short=[i for i,r in enumerate(rings) if len(r)<4]
    zero=[i for i,x in enumerate(a) if x==0]
    if not any(x<0 for x in a) or unclosed or short or zero:
        return dict(native_precinct_id=pid,ring_count=len(rings),clockwise_shells=sum(x<0 for x in a),
            counterclockwise_rings=sum(x>0 for x in a),unclosed_rings=unclosed,short_rings=short,zero_area_rings=zero,
            native_signed_ring_areas=a)

def svg(file,features,hd,vintage):
    bs=[f['geometry'].bounds for f in features]
    xmin=min(b[0] for b in bs);ymin=min(b[1] for b in bs)
    xmax=max(b[2] for b in bs);ymax=max(b[3] for b in bs)
    scale=min(860/(xmax-xmin),620/(ymax-ymin));ox=(960-(xmax-xmin)*scale)/2;oy=80+(660-(ymax-ymin)*scale)/2
    def xy(x,y):return ox+(x-xmin)*scale,oy+(ymax-y)*scale
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 820"><title>HD{hd} {vintage} precinct preview</title>',
        '<rect width="960" height="820" fill="#f5f8fa"/>',
        f'<text x="28" y="35" font-family="sans-serif" font-size="25">Alaska HD{hd}: {len(features)} physical precincts</text>',
        f'<text x="28" y="63" font-family="sans-serif" font-size="17">{vintage}; research preview; November 2026 approval unknown</text>']
    colors=['#c6e4eb','#c9dbb9','#f2d5b4','#d7c9e6','#f2c6c9','#c4d8ed']
    for i,f in enumerate(features):
        geom=f['geometry'];polys=list(geom.geoms) if geom.geom_type=='MultiPolygon' else [geom]
        d=[]
        for poly in polys:
            for ring in [poly.exterior,*poly.interiors]:
                coords=[xy(x,y) for x,y,*_ in ring.coords]
                d.append('M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in coords)+' Z')
        lines.append(f'<path d="{" ".join(d)}" fill="{colors[i%len(colors)]}" stroke="#314b58" stroke-width="0.8" fill-rule="evenodd"><title>{f["id"]}</title></path>')
    label_boxes=[]
    for f in features:
        q=f['geometry'].representative_point();x,y=xy(q.x,q.y)
        lx,ly=x,y
        # Move only display labels, with leaders, when overview labels collide.
        for dx,dy in [(0,0),(-35,-20),(35,20),(-35,20),(35,-20),(0,-38),(0,38),(-65,0),(65,0),(-65,-38),(65,38)]:
            box=(x+dx-24,y+dy-12,x+dx+24,y+dy+3)
            if not any(box[0]<b[2] and box[2]>b[0] and box[1]<b[3] and box[3]>b[1] for b in label_boxes):
                lx,ly=x+dx,y+dy;break
        label_boxes.append((lx-24,ly-12,lx+24,ly+3))
        if lx!=x or ly!=y:lines.append(f'<path d="M{x:.2f},{y:.2f} L{lx:.2f},{ly:.2f}" stroke="#314b58" stroke-width="0.6"/>')
        textattrs=f'x="{lx:.2f}" y="{ly:.2f}" text-anchor="middle" font-family="sans-serif" font-size="12"'
        lines.append(f'<text {textattrs} stroke="#fff" stroke-width="3" fill="#fff">{f["id"]}</text>')
        lines.append(f'<text {textattrs} fill="#172c36">{f["id"]}</text>')
    lines.append('<text x="28" y="785" font-family="sans-serif" font-size="15">EPSG:3857 display; no basemap. SVG positions rounded only for display. Original geometry retained.</text></svg>')
    (ROOT/file).write_text('\n'.join(lines)+'\n')

def topology(features):
    invalid=[];empty=[];overlaps=[];errors=[]
    for f in features:
        g=f['geometry']
        if not g.is_valid:invalid.append(dict(id=f['id'],reason=explain_validity(g)))
        if g.is_empty:empty.append(f['id'])
    tree=shapely.STRtree([f['geometry'] for f in features])
    for i,f in enumerate(features):
        a=f['geometry']
        for k in tree.query(a):
            k=int(k)
            if k<=i:continue
            b=features[k]['geometry']
            try:
                ar=a.intersection(b).area
                if ar>0:overlaps.append(dict(id_a=f['id'],id_b=features[k]['id'],web_mercator_area=ar))
            except shapely.errors.GEOSException as e:errors.append(dict(id_a=f['id'],id_b=features[k]['id'],error=str(e)))
    return dict(feature_count=len(features),invalid=invalid,empty=empty,positive_area_overlaps=overlaps,
        overlay_errors=errors,area_units='EPSG:3857 projected square meters, distorted; not geodesic land area',
        legal_boundary_or_gap_test='not established: no independent approved HD/precinct boundary or land coverage reference used')

def pdf_audit(priority,byhd):
    rows=[];info={}
    for d in priority['districts']:
        hd=int(d['native_house_district']);file=f'originals/HD{hd}_May2023Final_Maps.pdf'
        # Both extraction orders matter: roads can interleave with the title.
        texts={m:subprocess.check_output(['pdftotext',m,str(ROOT/file),'-']).decode() for m in ['-layout','-raw']}
        doc=fitz.open(ROOT/file);pages=len(doc)
        assert all(len(t.split('\f'))-1==pages for t in texts.values())
        out=ROOT/f'derived/pdf-text/HD{hd:02d}.txt.gz';out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(gzip.compress(texts['-layout'].encode(),mtime=0))
        expected={f['id'] for f in byhd[hd]};seen=[]
        cellw=300;cellh=250;cols=min(pages,4);nrows=math.ceil(pages/cols)
        sheet=Image.new('RGB',(cellw*cols,cellh*nrows),'#e7edf1');draw=ImageDraw.Draw(sheet)
        for n,page in enumerate(doc):
            a=texts['-layout'].split('\f')[n];b=texts['-raw'].split('\f')[n]
            m=re.search(r'Precinct:\s*(\d{2}-\d{3})',a) or re.search(r'Precinct:\s*(\d{2}-\d{3})',b)
            method='explicit Precinct title in layout/raw text'
            if m:pid=m[1]
            else:
                # Two printed/extracted titles omit a digit; interior label has the full native ID.
                candidates=set(re.findall(r'\b\d{2}-\d{3}\b',a+b)) & expected
                assert len(candidates)==1,(hd,n,candidates)
                pid=candidates.pop();method='full interior precinct label; malformed title requires visual review'
            assert pid in expected,(hd,n,pid)
            seen.append(pid)
            rows.append(dict(native_house_district=hd,page=n+1,native_precinct_id=pid,
                extraction_evidence=method,pdf_path=file,printed_vintage='May 15, 2023 Redistricting Plan',
                source_url=d['map_source_url'],november2026_approval='unknown'))
            if (hd,n+1) in [(21,5),(33,6),(6,4),(36,3)]:
                rp=f'derived/representative/HD{hd:02d}-page{n+1:02d}.jpg'
                (ROOT/rp).parent.mkdir(parents=True,exist_ok=True)
                page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False).save(ROOT/rp)
                asset(rp,[file],'baseline-2024 PDF page',pages=1,hd=hd,
                    note=f'Full-page raster preview of original PDF page {n+1}; original PDF retained')
            pix=page.get_pixmap(matrix=fitz.Matrix(0.24,0.24),alpha=False)
            im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);im.thumbnail((cellw-10,cellh-30))
            x=(n%cols)*cellw;y=(n//cols)*cellh
            sheet.paste(im,(x+(cellw-im.width)//2,y+24))
            draw.text((x+8,y+5),f'HD{hd} page {n+1}: {pid}',fill='#102d3b')
        assert len(seen)==len(set(seen))==len(expected) and set(seen)==expected,(hd,expected-set(seen),set(seen)-expected)
        cp=f'derived/pdf-contacts/HD{hd:02d}.jpg';(ROOT/cp).parent.mkdir(parents=True,exist_ok=True)
        sheet.save(ROOT/cp,quality=85)
        asset(file,[file],'April 2024 precinct adoption / May 15 2023 Final Proclamation',
            crs='cartographic PDF; no geospatial CRS established',pages=pages,kind='official original PDF',hd=hd,
            note='Individual physical precinct maps, not district outlines; titles printed May 15 2023')
        asset(cp,[file],'baseline-2024 PDF pages',pages=pages,hd=hd,note='Contact sheet renders every page; visual aid only')
        asset(str(out.relative_to(ROOT)),[file],'baseline-2024 PDF text',pages=pages,hd=hd,note='Poppler layout extraction; roads may interleave with titles')
        info[hd]=dict(pages=pages,ids=seen,pdf_path=file,contact_path=cp)
        doc.close()
    csvout('pdf-page-inventory.csv',rows)
    return info

def main():
    manifest.clear()
    priority=json.loads((STATE/'data/turnout/priority-set.json').read_text())
    assert [int(d['native_house_district']) for d in priority['districts']]==ORDER
    assert sum(d['votes'] for d in priority['districts'])==271492
    assert priority['statewide_votes']==338177 and 5*271492>=4*338177 and 5*(271492-7718)<4*338177
    datasets,archive,batches=load_geometries()
    byv={v:{hd:[f for f in fs if f['hd']==hd] for hd in range(1,41)} for v,fs in datasets.items()}
    for v,fs in datasets.items():
        assert len(fs)==len({f['id'] for f in fs})==402
        assert all(re.fullmatch(r'\d{2}-\d{3}',f['id']) and int(f['id'][:2])==f['hd'] for f in fs)
    pdf=pdf_audit(priority,byv['baseline-2024'])
    asset(archive,[archive],'April 2024 precinct adoption / May 15 2023 Final Proclamation',
        crs='EPSG:3857 / ESRI:102100',features=402,kind='official original shapefile ZIP')
    for b in batches:asset(b,[b],'current locator snapshot retrieved October 2026; effective date unknown',
        crs='EPSG:3857 / ESRI:102100',features=len(js(b)['features']),kind='original native EsriJSON response',
        note='Unmodified response bytes, lossless gzip; part of complete 402-feature object-ID download')
    project=pyproj.Transformer.from_crs(3857,4326,always_xy=True).transform
    checks={};coverage=[]
    for v,fs in datasets.items():
        checks[v]=topology(fs)
        for rank,hd in enumerate(ORDER,1):
            subset=byv[v][hd];outdir=ROOT/'derived'/v;outdir.mkdir(parents=True,exist_ok=True)
            geo=f'derived/{v}/HD{hd:02d}.geojson';sv=f'derived/{v}/HD{hd:02d}.svg'
            fc=dict(type='FeatureCollection',features=[dict(type='Feature',id=f['id'],properties={**f['properties'],
                'research_native_precinct_id':f['id'],'research_vintage':v},geometry=mapping(transform(project,f['geometry']))) for f in subset])
            # Compact whitespace only: no coordinate rounding or simplification.
            (ROOT/geo).write_text(json.dumps(fc,separators=(',',':'),ensure_ascii=False,default=str)+'\n')
            svg(sv,subset,hd,v)
            sources=[archive] if v=='baseline-2024' else batches
            asset(geo,sources,v,'OGC:CRS84 longitude,latitude (EPSG:4326 transform)',len(subset),hd=hd,
                note='Full coordinate precision; pyproj reprojection; original geometry retained separately; no vote allocation')
            asset(sv,sources,v,'EPSG:3857 display transform',len(subset),hd=hd,
                note='Display coordinates rounded to 0.01 SVG units; no basemap; unsuitable for measurements')
            coverage.append(dict(priority_rank=rank,native_house_district=hd,vintage=v,
                polygon_features=len(subset),pdf_pages=pdf[hd]['pages'] if v=='baseline-2024' else '',
                native_precinct_ids=' | '.join(sorted(f['id'] for f in subset)),
                november2026_approval='unknown',geojson_path=geo,preview_path=sv))
    save('topology-checks.json',checks)
    base={f['id']:f for f in datasets['baseline-2024']};curr={f['id']:f for f in datasets['current-retrieved-2026']}
    common=base.keys()&curr.keys()
    save('snapshot-comparison.json',dict(common_ids=len(common),baseline_only=sorted(base.keys()-curr.keys()),
        current_only=sorted(curr.keys()-base.keys()),
        exact_geometry_equal_ids=sorted(k for k in common if base[k]['geometry'].equals_exact(curr[k]['geometry'],0)),
        topological_geometry_equal_ids=sorted(k for k in common if base[k]['geometry'].equals(curr[k]['geometry'])),
        coordinates_equal_within_1e_minus7_projected_meter_ids=sorted(k for k in common if base[k]['geometry'].equals_exact(curr[k]['geometry'],1e-7)),
        coordinates_differ_beyond_1e_minus7_projected_meter_ids=sorted(k for k in common if not base[k]['geometry'].equals_exact(curr[k]['geometry'],1e-7)),
        normalized_coordinates_equal_within_1e_minus7_projected_meter_ids=sorted(k for k in common if base[k]['geometry'].equals_exact(curr[k]['geometry'],1e-7,normalize=True)),
        normalized_coordinates_differ_beyond_1e_minus7_projected_meter_ids=sorted(k for k in common if not base[k]['geometry'].equals_exact(curr[k]['geometry'],1e-7,normalize=True)),
        unequal_geometry_ids=sorted(k for k in common if not base[k]['geometry'].equals(curr[k]['geometry'])),
        limitation='Strict equality is sensitive to binary shapefile versus decimal JSON serialization. The 1e-7 EPSG:3857 meter tolerance is a diagnostic, not an applied geometry change. Same-CRS snapshot comparison does not establish election-effective equivalence or legal crosswalk'))
    units={y:list(csv.DictReader((STATE/f'data/turnout/reporting-units-{y}.csv').open())) for y in [2024,2022]}
    assert len(units[2024])==523 and len(units[2022])==522
    physical={u['native_pct_id']:u for u in units[2024] if u['unit_type']=='physical_precinct'}
    assert len(physical)==402 and physical.keys()==base.keys()==curr.keys()
    compat=[];inventory=[]
    for year,rows in units.items():
        for u in rows:
            pid=u['native_pct_id'];hd=int(u['native_house_district'])
            mapped=year==2024 and u['unit_type']=='physical_precinct'
            compat.append(dict(election_year=year,source_unit_key=u['source_unit_key'],source_label=u['source_label'],
                native_pct_id=pid,native_pct_seq_nbr=u['native_pct_seq_nbr'],native_house_district=hd,
                state_fips='02',county_fips='',unit_type=u['unit_type'],source_label_method=u['method'],
                priority_hd_2024=1 if hd in ORDER else 0,
                baseline2024_id_inventory_match=1 if mapped else '',current_id_inventory_match=1 if mapped else '',
                baseline_pdf_page=next((p+1 for p,k in enumerate(pdf[hd]['ids']) if k==pid),'') if mapped and hd in pdf else '',
                compatibility='2024 native-ID inventory match only; geographic vote allocation unapproved' if mapped else
                    ('2022-to-2024/2026 crosswalk not established' if year==2022 else 'administrative unit; no polygon assumed'),
                mixed_actual_methods=u.get('method_split_status',''),vote_allocation_performed='no'))
    for hd in [*range(1,41),99]:
        a=[u for u in units[2024] if int(u['native_house_district'])==hd]
        b=[u for u in units[2022] if int(u['native_house_district'])==hd]
        inventory.append(dict(native_house_district=hd,state_fips='02',county_fips='',
            geography_type='federal overseas administrative' if hd==99 else 'native House District',
            priority_rank=ORDER.index(hd)+1 if hd in ORDER else '',results2024_units=len(a),results2022_units=len(b),
            physical2024_units=sum(u['unit_type']=='physical_precinct' for u in a),
            physical2022_units=sum(u['unit_type']=='physical_precinct' for u in b),
            baseline2024_polygon_features=len(byv['baseline-2024'].get(hd,[])),
            current_locator_polygon_features=len(byv['current-retrieved-2026'].get(hd,[])),
            downloaded_pdf_pages=pdf.get(hd,{}).get('pages',0),
            pdf_status='downloaded every physical precinct page' if hd in pdf else
                ('not geographic; no polygon assumed' if hd==99 else 'outside priority; statewide GIS retained; PDF not downloaded'),
            november2026_approval='unknown',cross_year_spatial_equivalence='not established'))
    csvout('native-hd-inventory.csv',inventory);csvout('reporting-unit-compatibility.csv',compat)
    csvout('coverage-by-vintage.csv',sorted(coverage,key=lambda r:(r['priority_rank'],r['vintage'])))
    csvout('manifest.csv',manifest)
    inputs={str((STATE/p).relative_to(STATE)):sha((STATE/p).read_bytes()) for p in
        ['data/turnout/priority-set.json','data/turnout/reporting-units-2024.csv','data/turnout/reporting-units-2022.csv','data/coordinator-baseline-reconciliation.json']}
    save('checks.json',dict(status='pass',inputs_sha256=inputs,priority_districts=ORDER,
        priority_votes=271492,statewide_votes=338177,priority_share_percent=271492/338177*100,
        prior27_votes=263774,all_hd_inventory_rows=41,reporting_unit_compatibility_rows=len(compat),
        physical_precincts_2024=402,physical_precincts_2022=401,priority_pdf_packets=28,
        priority_pdf_pages=sum(p['pages'] for p in pdf.values()),
        priority_physical_results_units=sum(u['unit_type']=='physical_precinct' and int(u['native_house_district']) in ORDER for u in units[2024]),
        coverage_rows=len(coverage),features_by_vintage={v:len(fs) for v,fs in datasets.items()},
        priority_features_by_vintage={v:sum(len(byv[v][hd]) for hd in ORDER) for v in VINTAGES},
        november2026_approval='unknown for all 28 priority HDs',cross_year_crosswalk=False,vote_allocation=False,
        versions=dict(pyproj=pyproj.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string,
            pyshp=shapefile.__version__,pymupdf=fitz.VersionBind)))
    make_index(priority,pdf,byv)
    print('Built',len(manifest),'manifest assets;',sum(p['pages'] for p in pdf.values()),'individual precinct PDF pages;',len(compat),'reporting-unit records')

def make_index(priority,pdf,byv):
    lines=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>Alaska official precinct maps</title><style>body{font:16px system-ui;max-width:1380px;margin:2rem auto;padding:0 1rem;color:#173440;background:#f7fafb}a{color:#075d8b}table{border-collapse:collapse;width:100%}td,th{padding:14px;border:1px solid #b6cad3;vertical-align:top;text-align:left}td img{width:100%;max-width:360px}th:first-child{width:150px}caption{text-align:left;font-size:1.2rem;margin:1rem 0}small{display:block}summary{cursor:pointer}footer{margin:2rem 0}</style>',
        '<h1>Alaska precinct map assets</h1><p>28 priority native House Districts in vote rank order: 271,492 / 338,177 = 80.28103626% of 2024 presidential candidate votes. State FIPS 02; county FIPS blank. HD99 is administrative and has no assumed polygon.</p>',
        '<p><strong>April 2024 adoption is documented. November 3, 2026 approval remains unknown.</strong> Two distinct saved snapshots: the official April 2024/May 2023-proclamation shapefile ZIP and the current DOE precinct locator retrieved in October 2026. Native-ID matches do not establish a vote-allocation crosswalk.</p>',
        '<p><a href="../precinct-maps.md">Research report</a> · <a href="manifest.csv">Asset manifest</a> · <a href="native-hd-inventory.csv">All 41 HDs</a> · <a href="reporting-unit-compatibility.csv">All 523 + 522 results units</a> · <a href="pdf-page-inventory.csv">Every PDF page</a> · <a href="coverage-by-vintage.csv">56 HD/vintage coverage rows</a> · <a href="validation.json">Offline audit</a> · <a href="REPRODUCE.md">Reproduction</a></p>',
        '<p><a href="originals/AK_Election_Precincts_2023Final.zip">Official original statewide shapefile ZIP (402 features)</a>. Native current locator responses: <a href="pagination-checks.json">complete 402-feature / 9-batch inventory</a>. GeoJSONs below are full precision derivatives; previews have no basemap and are for research.</p>',
        '<table><caption>Every packet page is an individual physical precinct map; no district-outline substitute</caption><thead><tr><th>Priority / native HD</th><th>Original official PDF</th><th>Baseline 2024 GIS</th><th>Current locator snapshot</th></tr></thead><tbody>']
    for d in priority['districts']:
        hd=int(d['native_house_district']);p=pdf[hd]
        lines.append(f'<tr><th>#{d["rank"]} · HD{hd}<small>{d["votes"]:,} candidate votes</small></th><td><a href="{p["pdf_path"]}">{p["pages"]} precinct pages · original PDF</a><p><a href="{p["contact_path"]}"><img src="{p["contact_path"]}" loading="lazy" alt="Contact sheet of all HD{hd} PDF precinct pages"></a></p><a href="{html.escape(d["map_source_url"],quote=True)}">Official source</a></td>')
        for v in VINTAGES:
            path=f'derived/{v}/HD{hd:02d}'
            lines.append(f'<td><a href="{path}.svg"><img src="{path}.svg" alt="HD{hd} {v} physical precinct polygons" loading="lazy"></a><small>{len(byv[v][hd])} features</small><a href="{path}.geojson">Full precision GeoJSON</a> · <a href="{path}.svg">SVG preview</a></td>')
        lines.append('</tr>')
    lines.append('</tbody></table><footer>Administrative Absentee, Early Voting and Question units have no automatic physical polygon. Four 2024 Early Voting labeled records mix actual methods. No verified votes are allocated to polygons; no live collector or calibrated forecast is supplied.</footer></html>')
    (ROOT/'index.html').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
