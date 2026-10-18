#!/usr/bin/env python3
"""Offline full-vertex conversion, identity inventory and practical map index.

Requires shapely, pyproj, pyshp and PyMuPDF; does not repair or simplify GIS.
Original HTTP response entities are read only. No vote geometry allocation.
"""
import collections,csv,gzip,hashlib,html,io,json,math,pathlib,re,sys,zipfile
import shapely
from shapely.geometry import Polygon,MultiPolygon,LinearRing,shape,mapping
from shapely.ops import transform
from shapely.validation import explain_validity
from shapely.strtree import STRtree
from pyproj import Transformer
import pyproj
from acquire import ROOT,load,digest
STATE=ROOT.parent
def dump(path,obj):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def operation_details(transformer):
    """The generic transformer description can stay unresolved after use."""
    op=transformer.get_last_used_operation()
    return {'description':op.description,'pipeline':op.definition,'reported_accuracy_m':op.accuracy,'pyproj_version':pyproj.__version__,'proj_version':pyproj.proj_version_str,'selection':'PROJ default selection, always_xy; last observed operation after transforming retained geometry, no custom grid/accuracy claim'}
def norm(s):
    s=s.upper().replace('SAINT','ST')
    for x in ['TOWNSHIP','TWP','PLANTATION','PLT']:s=s.replace(x,'')
    return re.sub('[^A-Z0-9]','',s)
def strictnorm(s):return re.sub('[^A-Z0-9]','',s.upper().replace('SAINT','ST'))
def esri_polygon(g):
    if not g:return None
    if 'curveRings' in g:raise ValueError('Native curves require an explicitly labeled linearization; originals retained')
    rings=g['rings'];shells=[];holes=[]
    for r in rings:
        assert len(r)>=4 and r[0]==r[-1]
        assert all(len(p)==2 and all(math.isfinite(v) for v in p) for p in r)
        (holes if LinearRing(r).is_ccw else shells).append(r)
    assert shells,'No Esri clockwise shell'
    polygons=[Polygon(s) for s in shells];attached=[[] for _ in shells]
    for h in holes:
        point=Polygon(h).representative_point()
        candidates=[i for i,p in enumerate(polygons) if p.covers(point)]
        assert candidates,'Orphan Esri hole'
        attached[min(candidates,key=lambda i:polygons[i].area)].append(h)
    p=[Polygon(s,attached[i]) for i,s in enumerate(shells)]
    return p[0] if len(p)==1 else MultiPolygon(p)
def vertex_count(g):
    if g is None:return 0
    if g.geom_type=='Polygon':return len(g.exterior.coords)+sum(len(x.coords) for x in g.interiors)
    return sum(vertex_count(x) for x in g.geoms)
def fc(features):return {'type':'FeatureCollection','features':features}
def write_fc(path,features):
    b=json.dumps(fc(features),separators=(',',':'),allow_nan=False).encode()
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(b,mtime=0))
def svg(path,features,title,scope):
    geoms=[shape(f['geometry']) for f in features if f.get('geometry')]
    if not geoms:return
    # Simple longitude display at 44.5N; no distance/area claim. All vertices retained.
    k=math.cos(math.radians(44.5));bounds=[g.bounds for g in geoms]
    x0=min(b[0] for b in bounds)*k;x1=max(b[2] for b in bounds)*k
    y0=-max(b[3] for b in bounds);y1=-min(b[1] for b in bounds)
    scale=min(700/max(x1-x0,1e-10),490/max(y1-y0,1e-10))
    dx=(760-(x1-x0)*scale)/2;dy=78+(490-(y1-y0)*scale)/2
    def ring(r):return 'M'+'L'.join(f'{dx+(x*k-x0)*scale:.2f},{dy+(-y-y0)*scale:.2f}' for x,y,*_ in r)+'Z'
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 620"><rect width="760" height="620" fill="#f6f8fa"/><text x="24" y="28" font-family="sans-serif" font-size="17">{html.escape(title)}</text><text x="24" y="52" font-family="sans-serif" font-size="12">{html.escape(scope)}</text>']
    colors=['#6baed6','#9ecae1','#bcbddc','#a1d99b','#fdae6b','#dadaeb','#fdd0a2']
    for i,(f,g) in enumerate(zip(features,geoms)):
        polys=[g] if g.geom_type=='Polygon' else g.geoms
        d=''.join(ring(p.exterior.coords)+''.join(ring(h.coords) for h in p.interiors) for p in polys)
        label=f['properties'].get('TOWN',f['properties'].get('NAME20',f['properties'].get('NAME',str(f.get('id','')))))
        out.append(f'<path d="{d}" fill="{colors[i%len(colors)]}" fill-rule="evenodd" stroke="#24466b" stroke-width="0.7"><title>{html.escape(label)}</title></path>')
        if 'Ward' in f['properties'] and 'Precinct' in f['properties']:
            q=g.representative_point();x=dx+(q.x*k-x0)*scale;y=dy+(-q.y-y0)*scale
            out.append(f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="middle" font-family="sans-serif" font-size="16">{html.escape(str(f["properties"]["Ward"])+"-"+str(f["properties"]["Precinct"]))}</text>')
    out.append('<text x="24" y="601" font-family="sans-serif" font-size="11">Research preview; display rounding only; no votes allocated; November 2026 approval unestablished.</text></svg>')
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(out))
def gis():
    layers=json.loads((ROOT/'gis-downloads.json').read_text());checks={};bylayer={};native={}
    for key,meta in layers.items():
        fs=[];ng=[];invalid=[];empty=[];counts=[];ids=[];curves=[];derivative_invalid=[]
        transformer=Transformer.from_crs(meta['native_crs'].get('latestWkid',meta['native_crs']['wkid']),4326,always_xy=True)
        for batch in meta['batches']:
            j=json.loads(load(batch['key']));assert not j.get('exceededTransferLimit')
            actual=[f['attributes'][meta['oid_field']] for f in j['features']]
            assert sorted(actual)==batch['requested_ids']
            for f in j['features']:
                oid=f['attributes'][meta['oid_field']];ids.append(oid)
                if 'curveRings' in (f.get('geometry') or {}):curves.append(oid)
                g=esri_polygon(f.get('geometry'));ng.append(g)
                if g is None or g.is_empty:empty.append(oid)
                elif not g.is_valid:invalid.append({'id':oid,'reason':explain_validity(g)})
                gg=transform(transformer.transform,g) if g is not None else None
                assert vertex_count(g)==vertex_count(gg)
                if gg is not None and not gg.is_valid:derivative_invalid.append({'id':oid,'reason':explain_validity(gg)})
                counts.append(vertex_count(g))
                fs.append({'type':'Feature','id':oid,'properties':f['attributes'],'geometry':mapping(gg) if gg else None})
        assert sorted(ids)==meta['ids'] and len(ids)==len(set(ids))==meta['count']
        # Positive-area overlaps only; shared edges are expected. Invalid input is skipped explicitly.
        valid=[i for i,g in enumerate(ng) if g is not None and not g.is_empty and g.is_valid]
        tree=STRtree([ng[i] for i in valid]);overlaps=[];errors=[]
        for ti,i in enumerate(valid):
            for tj in tree.query(ng[i],predicate='intersects'):
                if tj<=ti:continue
                n=valid[int(tj)]
                try:
                    area=ng[i].intersection(ng[n]).area
                    if area>0:overlaps.append({'id_a':ids[i],'id_b':ids[n],'intersection_area_native_units2':area})
                except Exception as e:errors.append({'id_a':ids[i],'id_b':ids[n],'error':str(e)})
        checks[key]={'feature_count':len(fs),'ids':ids,'native_crs':meta['native_crs'],'hasZ':meta['hasZ'],'hasM':meta['hasM'],'curve_feature_ids':curves,'native_and_derivative_vertices':sum(counts),'empty_ids':empty,'invalid':invalid,'derivative_invalid':derivative_invalid,'overlap_pairs_positive_area':overlaps,'overlap_errors':errors,'overlap_excluded_invalid_ids':[x['id'] for x in invalid],'method':'GEOS in native CRS; positive intersection area, no repair; not a legal boundary or gap audit','pyproj_operation':operation_details(transformer),'source_globalids_unique':len({f['properties'].get('GlobalID') for f in fs})==len(fs)}
        bylayer[key]=fs;native[key]=ng
        if key=='town':
            for county in sorted({f['properties']['COUNTY'] for f in fs}):
                selected=[f for f in fs if f['properties']['COUNTY']==county]
                write_fc('state-reference/'+county.lower()+'.geojson.gz',selected)
        else:
            write_fc('municipal-gis/'+key+'.geojson.gz',fs);svg('previews/'+key+'-gis.svg',fs,key.title()+' municipal GIS','Ward/district reference; current service snapshot')
    dump('geometry-audit.json',{'shapely':shapely.__version__,'geos':shapely.geos_version_string,'layers':checks})
    return bylayer
COMPOSITES={
 'Ellsworth/Fletchers Landing Twp':['Ellsworth','Fletchers Landing Twp'],
 'Old Town/Argyle Twp':['Old Town','Argyle Twp'],
 'Caribou/Connor':['Caribou','Connor Twp'],
 'Bristol/Louds Island Twp':['Bristol','Louds Island'],
 'Milford/Greenfield Twp':['Milford','Greenfield Twp'],
 'Bethel/Mason Twp':['Bethel','Mason Twp'],
 'Wilton/Twps':['Wilton','Perkins Twp','Washington Twp'],
 'Millinocket/Twps':['Millinocket','Chesuncook Twp','T1 R9 WELS','T3 R11 WELS','T4 R10 WELS','T6 R11 WELS','T6 R13 WELS','T8 R11 WELS','Long A Twp','T1 R8 WELS','T3 Indian Purchase Twp','T4 Indian Purchase Twp']}
def inventory(towns):
    contract=json.loads((STATE/'data/turnout/priority-set.json').read_text());units=contract['all_unit_coverage']
    assert len(units)==512
    expected=(STATE/'data/turnout/priority-keys.txt').read_bytes();assert digest(expected)=='086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'
    assert ''.join(u['native_key']+'\n' for u in units if u['priority']).encode()==expected
    current=json.loads((STATE/'data/results-sources/current-voting-places.json').read_text())['rows']
    authority={u['native_key']:u for u in json.loads((STATE/'data/results-sources/authority-reconciliation.json').read_text())}
    byname=collections.defaultdict(list);bystrict=collections.defaultdict(list)
    for f in towns:
        byname[norm(f['properties']['TOWN'])].append(f)
        bystrict[strictnorm(f['properties']['TOWN'])].append(f)
    out=[];used=collections.defaultdict(list)
    for u in units:
        name=u['native_name'].strip();admin=name=='STATE UOCAVA';combined='/' in name
        components=COMPOSITES.get(name) or (name.split('/') if combined else [name])
        mapped=[];missing=[]
        for component in components:
            if component in ['Twps','Townships']:missing.append(component+' (historical constituents unspecified)');continue
            candidates=bystrict.get(strictnorm(component),[]) or byname.get(norm(component),[])
            if name=='Bristol/Louds Island Twp' and component=='Louds Island':
                candidates=[f for f in towns if f['properties'].get('ISLANDID')=='65-185']
                missing.append('Louds Island: coastal registry 65-185 identifies main island outline only; full reporting township extent unestablished (registry original page44)')
            # Literal reported county is a guard for simple matches, never applied to cross-county composites.
            if not combined and u['county_fips']:
                candidates=[f for f in candidates if f['properties']['CNTYCODE']==u['county_fips'][-3:][-2:]]
            if len({f['properties']['GEOCODE'] for f in candidates})>1:
                missing.append(component+' (ambiguous normalized GIS name; not selected)');candidates=[]
            if not candidates:missing.append(component)
            for f in candidates:
                if f['id'] not in {g['id'] for g in mapped}:mapped.append(f)
        if admin:mapped=[];missing=[]
        base=name.split('/')[0].strip()
        supplied_rows=authority.get(u['native_key'],{}).get('current_voting_place_rows',[])
        roster=[r for r in current if r['source_row'] in supplied_rows]
        historical_wp=sorted({r['ward_precinct'] for r in u['registration_constituents']})
        current_wp=sorted({r['ward_precinct'] for r in roster})
        status='administrative, no polygon appropriate' if admin else ('combined component reference; historical whole-return crosswalk unverified' if combined else ('municipal/township polygon reference; lexical identity candidate' if mapped else 'unmatched physical identity; geometry gap retained'))
        if name in ['Millinocket/Twps','Wilton/Twps']:missing.append('Historical /Twps membership unestablished; displayed expanded components are current 2026 roster references only')
        r={**u,'classification':status,'map_scope':'none' if admin else 'town/township political boundaries, not voting precincts','geometry_vintage':'current GeoLibrary snapshot; metadata extent says current as of 2024-02-23; not a frozen election-day 2024 export','approved_november_2026':'unestablished','components_requested':components if not admin else [],'unresolved_components':missing,'matched_source_ids':[f['id'] for f in mapped],'matched_geocodes':sorted({f['properties']['GEOCODE'] for f in mapped}),'matched_town_names':sorted({f['properties']['TOWN'] for f in mapped}),'current_voting_place_rows':roster,'current_roster_relationship':'read-only official-results authority-reconciliation.json provisional identities; not boundary equivalence','historical_registration_precinct_keys_status':'preserved from contract; not matched to map features','historical_registration_wp':historical_wp,'current_roster_wp':current_wp,'wp_label_diagnostic':{'common':sorted(set(historical_wp)&set(current_wp)),'historical_only':sorted(set(historical_wp)-set(current_wp)),'current_only':sorted(set(current_wp)-set(historical_wp)),'meaning':'Textual label sets only across different source types/vintages, not a legal boundary change or vote-return crosswalk'},'results_polygon_crosswalk':'unestablished','state_administration_source':'https://www3.maine.gov/sos/elections-voting/uniformed-service-and-overseas-voters' if admin else None}
        for f in mapped:used[f['id']].append(u['native_key'])
        if u['priority'] and mapped:
            slug=f'{u["rank"]:03d}-'+re.sub('[^a-z0-9]+','-',name.lower()).strip('-')
            r['geojson']='units/'+slug+'.geojson.gz';r['preview']='previews/'+slug+'.svg'
            write_fc(r['geojson'],mapped);svg(r['preview'],mapped,name,'Town/township reference'+('; composite scope unverified' if combined else ''))
        out.append(r)
    dump('unit-inventory.json',out)
    fields=['rank','native_key','native_name','county_code','county_fips','priority','classification','map_scope','geometry_vintage','approved_november_2026','matched_geocodes','matched_source_ids','unresolved_components','geojson','preview']
    with (ROOT/'unit-inventory.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for u in out:w.writerow({k:json.dumps(u[k]) if isinstance(u.get(k),list) else u.get(k,'') for k in fields})
    dump('compatibility-diagnostics.json',{'all_native_units':512,'priority_count':164,'remainder':348,'priority_keys_sha256':digest(expected),'source_numeric_results_ids_absent':all(not u['results_ward_precinct_ids'] for u in units),'no_2026_equivalence_claim':True,'unmatched':[{'native_key':u['native_key'],'native_name':u['native_name'],'unresolved_components':u['unresolved_components']} for u in out if not u['matched_source_ids'] and u['map_scope']!='none'],'combined_returns':[{'native_key':u['native_key'],'components':u['components_requested'],'unresolved':u['unresolved_components'],'geocodes':u['matched_geocodes']} for u in out if '/' in u['native_name']],'source_geometry_used_by_multiple_returns':[{'id':i,'native_keys':v} for i,v in used.items() if len(v)>1],'historical_source_defects':'All 517/510/512/513 baseline rows remain read-only by source row identity. No ward IDs inferred for repeated 2022 Cranberry Isles; T3 ND Twp row190 printed PEN inside HAN section not repaired. Alfred count correction does not imply geometry change.'})
    return out
def pdfs():
    import fitz
    acquisitions=json.loads((ROOT/'acquisitions.json').read_text());audit={};seen={}
    for key,r in acquisitions.items():
        if not r['path'].endswith('.pdf'):continue
        p=ROOT/r['path'];b=p.read_bytes()
        if r['status']!=200 or not b.startswith(b'%PDF'):
            audit[key]={'status':'not a downloaded PDF','http_status':r['status'],'path':r['path']};continue
        if r['original_sha256'] in seen:
            audit[key]={**audit[seen[r['original_sha256']]],'same_bytes_as':seen[r['original_sha256']]};continue
        seen[r['original_sha256']]=key;doc=fitz.open(p);pages=[];texts=[]
        for n,page in enumerate(doc):
            preview='previews/'+key+f'-page-{n+1:02d}.png'
            scale=min(1800/page.rect.width,1800/page.rect.height)
            page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False).save(ROOT/preview)
            texts.append(page.get_text());pages.append({'page':n+1,'preview':preview,'width_points':page.rect.width,'height_points':page.rect.height})
        textpath='previews/'+key+'.txt';(ROOT/textpath).write_text('\n\f\n'.join(texts))
        audit[key]={'status':'original PDF verified and every page rendered','pages':pages,'page_count':len(pages),'text':textpath,'metadata':doc.metadata,'path':r['path']}
    dump('pdf-audit.json',audit);return audit
def census():
    import shapefile
    p=ROOT/'raw/census-vtd-2020pl.zip';z=zipfile.ZipFile(p);assert z.testzip() is None
    stem='tl_2020_23_vtd20';r=shapefile.Reader(shp=io.BytesIO(z.read(stem+'.shp')),shx=io.BytesIO(z.read(stem+'.shx')),dbf=io.BytesIO(z.read(stem+'.dbf')))
    fields=[x[0] for x in r.fields[1:]];fs=[];ids=[];invalid=[];empty=[]
    transformer=Transformer.from_crs(4269,4326,always_xy=True)
    for sr in r.iterShapeRecords():
        attrs=dict(zip(fields,sr.record));g=sr.shape.__geo_interface__;gid=attrs['GEOID20'];ids.append(gid);sg=shape(g)
        if sg.is_empty:empty.append(gid)
        if not sg.is_valid:invalid.append({'GEOID20':gid,'reason':explain_validity(sg)})
        gg=transform(transformer.transform,sg);assert vertex_count(sg)==vertex_count(gg)
        fs.append({'type':'Feature','id':gid,'properties':attrs,'geometry':mapping(gg)})
    assert len(ids)==len(set(ids))
    write_fc('census-vtd-2020-reference.geojson.gz',fs);svg('previews/census-vtd-2020.svg',fs,'Maine 2020 Census voting districts','Historical Census reference; not approved 2026 precincts')
    dump('census-audit.json',{'zip_crc':'all members pass','members':[{'name':x.filename,'bytes':x.file_size,'crc32':x.CRC,'sha256':digest(z.read(x.filename))} for x in z.infolist()],'feature_count':len(fs),'ids':ids,'fields':fields,'native_crs_prj':z.read(stem+'.prj').decode(),'geojson_crs':'OGC:CRS84 longitude/latitude; pyproj EPSG4269 to EPSG4326 always_xy; all vertices retained','transform_operation':operation_details(transformer),'shape_type':r.shapeType,'z_m':'source shapefile polygon type 5; no Z/M','invalid':invalid,'empty':empty,'not_a_2024_or_2026_crosswalk':True})
    return fs
def census_candidates(units,features):
    diagnostics=[]
    for u in units:
        if not u['priority'] or u['map_scope']=='none':continue
        base=u['native_name'].split('/')[0].strip()
        def match(f):
            p=f['properties'];name=p['NAME20']
            prefix=re.split(r' (?:Ward|Voting District|Precinct|District)\b',name,flags=re.I)[0]
            return p['STATEFP20']+p['COUNTYFP20']==u['county_fips'] and strictnorm(prefix)==strictnorm(base)
        found=[f for f in features if match(f)]
        entry={'native_key':u['native_key'],'historical_census_candidate_ids':[f['id'] for f in found],'historical_census_candidate_names':[f['properties']['NAME20'] for f in found],'relationship':'2020 Census name prefix and county candidate only; no historical/current election-return equivalence; no spatial clipping or vote allocation'}
        if found:
            slug=f'{u["rank"]:03d}-census-vtd-2020'
            u['census_geojson']='census-candidates/'+slug+'.geojson.gz';u['census_preview']='previews/'+slug+'.svg'
            entry.update(geojson=u['census_geojson'],preview=u['census_preview'])
            write_fc(u['census_geojson'],found);svg(u['census_preview'],found,u['native_name']+' — 2020 Census VTD reference','Historical name candidates; not approved November 2026 boundaries')
        diagnostics.append(entry)
    dump('census-compatibility.json',diagnostics)
    # Candidate links are annotations; original contract data and source polygons remain separate.
    dump('unit-inventory.json',units)
def index(units,pdfa):
    sources=json.loads((ROOT/'municipal-sources.json').read_text());byunit={norm(x['unit']):x for x in sources}
    h=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Maine reporting geography research</title><style>body{font:16px/1.5 system-ui;max-width:1250px;margin:auto;padding:24px;color:#182b42;background:#f4f6f8}h1{font-size:30px}a{color:#075a9a}nav,.notice,article{background:white;border:1px solid #cbd5df;padding:18px;border-radius:10px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px}article{margin:0;min-width:0}img{width:100%;height:280px;object-fit:contain;background:#f6f8fa}code{font-size:11px;overflow-wrap:anywhere}small{display:block;color:#4d6073}.warn{color:#7b4200}input{font:inherit;padding:10px;width:90%}table{border-collapse:collapse;width:100%;font-size:13px}td,th{text-align:left;border-bottom:1px solid #ccc;padding:7px}</style><h1>Maine: 164 priority native reporting units</h1><p>Offline map and download index. Research retrievals: 2026-10-18 UTC. All 512 historical identities remain in the inventory; 348 are outside this map workload.</p><div class="notice"><strong>Scope matters.</strong> GeoLibrary town/township polygons are municipal political boundaries. Ward/precinct PDF supplements and Census VTDs are labeled separately. No November 2026 legal approval or election-results-to-polygon crosswalk is established. No vote allocation. STATE UOCAVA is administrative and has no physical polygon.</div><nav><a href="../precinct-maps.md">Research report</a> · <a href="unit-inventory.csv">All 512 units CSV</a> · <a href="unit-inventory.json">Full identities and compatibility JSON</a> · <a href="acquisitions.json">HTTP provenance and hashes</a> · <a href="manifest.csv">Download manifest</a> · <a href="geometry-audit.json">Geometry checks</a> · <a href="compatibility-diagnostics.json">Unmatched/composite diagnostics</a> · <a href="validation.json">Offline validation</a><p><a href="#supplements">Municipal supplements</a> · <a href="#state">Complete state reference</a> · <a href="#all">All 512 inventory</a></p></nav><label>Find priority unit <input id="q" placeholder="Name, county or exact native key"></label><main class="grid">']
    for u in units:
        if not u['priority']:continue
        name=u['native_name'];s=byunit.get(norm(name.split('/')[0]));sup=[]
        if s:
            for a in s.get('assets',[]):
                pa=pdfa.get(a['id'],{})
                if pa.get('page_count'):sup.append(f'<a href="{pa["path"]}">{html.escape(a["id"])} original PDF</a> (<a href="#supp-{s["id"]}">all page previews</a>)')
            if (ROOT/('municipal-gis/'+s['id']+'.geojson.gz')).exists():sup.append(f'<a href="municipal-gis/{s["id"]}.geojson.gz">{s["id"].title()} precinct GIS derivative</a> · <a href="previews/{s["id"]}-gis.svg">precinct preview</a> (source label2021; approval/crosswalk unestablished)')
        h.append(f'<article class="unit" id="unit-{u["rank"]}" data-find="{html.escape((name+" "+u["county_code"]+" "+u["native_key"]).lower(),quote=True)}"><h2>{u["rank"]}. {html.escape(name)}</h2><code>{html.escape(u["native_key"])}</code><small>Parent county context: {html.escape(u["county_fips"] or "none")}</small><p>{html.escape(u["classification"])}</p>')
        if u.get('preview'):h.append(f'<a href="{u["preview"]}"><img loading="lazy" src="{u["preview"]}" alt="{html.escape(name)} town/township reference preview"></a><p><a download href="{u["geojson"]}">Full-vertex GeoJSON (.gz)</a> · <a href="{u["preview"]}">SVG preview</a></p><small>Municipal/township scope. Source features: {len(u["matched_source_ids"])}; geocodes: {", ".join(u["matched_geocodes"])}. Decompress .gz before opening in GIS.</small>')
        elif u['map_scope']=='none':h.append('<p><strong>Administrative, no polygon appropriate.</strong> No county assignment; missing geometry is not missing votes. <a href="https://www3.maine.gov/sos/elections-voting/uniformed-service-and-overseas-voters">Maine SOS state administration</a> (<a href="../data/results-sources/requests/9aefb960640e24b8df40.json">retained successful primary request</a>).</p>')
        else:h.append('<p class="warn">No geometry identity match; see retained diagnostics.</p>')
        if u['unresolved_components']:h.append('<p class="warn">'+html.escape('; '.join(u['unresolved_components']))+'</p>')
        if '/' in name:h.append('<small>Component names: '+html.escape('; '.join(u['matched_town_names']))+'. Whole-return relationship unverified; no votes split.</small>')
        if sup:h.append('<p>'+'<br>'.join(sup)+'</p>')
        if (not sup or (s and s.get('id')=='lisbon')) and (len(u['historical_registration_wp'])>1 or len(u['current_roster_wp'])>1):h.append('<p class="warn">Finer ward/precinct geometry is unresolved. <a href="finer-research.json">Inspected primary-source routes and gaps</a>; municipal whole-return reference is available above. Any legislative PDF reference is a separate scope.</p>')
        if u.get('census_geojson'):h.append(f'<p><a href="{u["census_geojson"]}">2020 Census VTD name candidates</a> · <a href="{u["census_preview"]}">historical preview</a>. Historical fallback only; no results crosswalk.</p>')
        if u['current_voting_place_rows']:h.append('<small>Current SOS roster W/P labels: '+html.escape(', '.join(sorted({x['ward_precinct'] for x in u['current_voting_place_rows']})))+'. Labels are not polygon IDs. <a href="../data/results-sources/current-voting-places.json">Read-only current roster</a>.</small>')
        h.append('</article>')
    h.append('</main><h2 id="supplements">Municipal ward / precinct supplements</h2><p>Publisher dates and historical approval evidence are in the report. Every successful PDF page has a preview; publication does not establish November 2026 approval.</p>')
    for s in sources:
        h.append(f'<section class="notice" id="supp-{s["id"]}"><h3>{html.escape(s["unit"])}</h3><p><a href="{html.escape(s["landing"],quote=True)}">Official landing</a> · {html.escape(s.get("vintage_note","Current published source; effective/approval dates unestablished"))}</p><div class="grid">')
        for a in s.get('assets',[]):
            pa=pdfa.get(a['id'],{})
            if not pa.get('page_count'):h.append(f'<p class="warn">{a["id"]}: response did not supply a usable PDF. Municipal reference remains available above.</p>');continue
            for page in pa['pages']:h.append(f'<div><a href="{page["preview"]}"><img loading="lazy" src="{page["preview"]}" alt="{s["unit"]} PDF page {page["page"]}"></a><p><a download href="{pa["path"]}">{a["id"]}: original PDF</a>, page {page["page"]}/{pa["page_count"]} · <a href="{pa["text"]}">text derivative</a></p></div>')
        if (ROOT/('municipal-gis/'+s['id']+'.geojson.gz')).exists():h.append(f'<p><a href="municipal-gis/{s["id"]}.geojson.gz">Municipal ward GIS full-vertex GeoJSON</a> · <a href="previews/{s["id"]}-gis.svg">GIS preview</a></p>')
        h.append('</div></section>')
    h.append('<h2 id="state">Complete state references</h2><p>GeoLibrary source response batches, native EPSG:26919, original attributes/IDs: <a href="gis-downloads.json">all bounded batch links and IDs</a>. Full-vertex longitude/latitude derivatives below are split by source county context for file size, not substituted county reporting units.</p><ul>')
    for p in sorted((ROOT/'state-reference').glob('*.gz')):h.append(f'<li><a href="state-reference/{p.name}">{p.stem.replace(".geojson", "").title()} municipal/township features</a></li>')
    h.append('</ul><details><summary>Download original native GIS response batches (lossless gzip)</summary><ul>')
    for key,meta in json.loads((ROOT/'gis-downloads.json').read_text()).items():
        for batch in meta['batches']:h.append(f'<li><a download href="raw/{batch["key"]}.gz">{batch["key"]}: {len(batch["returned_ids"])} original source features</a></li>')
    h.append('</ul></details><p><a href="raw/census-vtd-2020pl.zip">Original 2020 Census VTD shapefile ZIP</a> · <a href="census-vtd-2020-reference.geojson.gz">GeoJSON derivative</a> · <a href="previews/census-vtd-2020.svg">State preview</a> · <a href="census-audit.json">CRC/member/ID audit</a>. Historical reference only; Maine submitted partial VTD coverage, so this is not a complete municipal replacement.</p><h2 id="all">All 512 native identities</h2><table><tr><th>Rank</th><th>Exact native name</th><th>County context</th><th>Priority</th><th>Map compatibility</th></tr>')
    for u in units:h.append(f'<tr><td>{u["rank"]}</td><td>{html.escape(u["native_name"])}</td><td>{u["county_code"]}</td><td>{u["priority"]}</td><td>{html.escape(u["classification"])}</td></tr>')
    h.append('</table><script>document.querySelector("#q").addEventListener("input",e=>{let q=e.target.value.toLowerCase();for(let x of document.querySelectorAll(".unit"))x.hidden=!x.dataset.find.includes(q)})</script></html>')
    (ROOT/'index.html').write_text(''.join(h))
if __name__=='__main__':
    layers=gis();units=inventory(layers['town']);census_candidates(units,census());pa=pdfs();index(units,pa)
    print('Built',len(units),'native identities;',sum(u['priority'] for u in units),'ordered priority entries')
