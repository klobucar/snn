#!/usr/bin/env python3
"""Build all99/exact41 offline inventory without inventing a geographic crosswalk."""
import collections, csv, gzip, hashlib, html, json, pathlib, re
from acquire import ROOT, body, sha, write_json
from audit import gzjson
STATE=ROOT.parent
CONTRACT_SHA='579b22b8d4f35f12d085ef8402a1bcab14e135a1577daf3ddc4f7d3f66460822'
KEY_SHA='e015514b8718b35e9599389cddde2451e5cd598115ef4d6468016a7858271f95'
CITY_COUNTIES='''Adel:Dallas
Albia:Monroe
Algona:Kossuth
Altoona:Polk
Ames:Story
Anamosa:Jones
Ankeny:Polk
Asbury:Dubuque
Atlantic:Cass
Belle Plaine:Benton
Bettendorf:Scott
Bloomfield:Davis
Bondurant:Polk
Boone:Boone
Burlington:Des Moines
Camanche:Clinton
Carlisle:Warren,Polk
Carroll:Carroll
Carter Lake:Pottawattamie
Cedar Falls:Black Hawk
Cedar Rapids:Linn
Centerville:Appanoose
Chariton:Lucas
Charles City:Floyd
Cherokee:Cherokee
City of Maquoketa:Jackson
Clarinda:Page
Clear Lake:Cerro Gordo
Clinton:Clinton
Clive:Polk,Dallas
Colfax:Jasper
Coralville:Johnson
Corning:Adams
Council Bluffs:Pottawattamie
Cresco:Howard
Creston:Union
Davenport:Scott
De Witt:Clinton
Decorah:Winneshiek
Denison:Crawford
Des Moines:Polk,Warren
Dubuque:Dubuque
Dyersville:Dubuque,Delaware
Eagle Grove:Wright
Eldridge:Scott
Emmetsburg:Palo Alto
Estherville:Emmet
Evansdale:Black Hawk
Fairfield:Jefferson
Forest City:Winnebago,Hancock
Fort Dodge:Webster
Fort Madison:Lee
Franklin County Hampton:Franklin
Glenwood:Mills
Grimes:Polk,Dallas
Grinnell:Poweshiek
Hampton:Franklin
Harlan:Shelby
Hiawatha:Linn
Humboldt:Humboldt
Huxley:Story
Ida Grove:Ida
Independence:Buchanan
Indianola:Warren
Iowa City:Johnson
Iowa Falls:Hardin
Jefferson:Greene
Johnston:Polk
Keokuk:Lee
Knoxville:Marion
Le Claire:Scott
Le Mars:Plymouth
Madrid:Boone
Manchester:Delaware
Marion:Linn
Marshalltown:Marshall
Mason City:Cerro Gordo
Milford:Dickinson
Monticello:Jones
Mount Pleasant:Henry
Mount Vernon:Linn
Muscatine:Muscatine
Nevada:Story
New Hampton:Chickasaw
Newton:Jasper
North Liberty:Johnson
Norwalk:Warren,Polk
Oelwein:Fayette
Onawa:Monona
Orange City:Sioux
Osage:Mitchell
Osceola:Clarke
Oskaloosa:Mahaska
Ottumwa:Wapello
Pella:Marion
Perry:Dallas
Pleasant Hill:Polk
Polk City:Polk
Red Oak:Montgomery
Rock Rapids:Lyon
Rock Valley:Sioux
Sergeant Bluff:Woodbury
Sheldon:O'Brien,Sioux
Shenandoah:Page,Fremont
Sibley:Osceola
Sigourney:Keokuk
Sioux Center:Sioux
Sioux City:Woodbury,Plymouth
Spencer:Clay
Spirit Lake:Dickinson
Storm Lake:Buena Vista
Tiffin:Johnson
Tipton:Cedar
Urbandale:Polk,Dallas
Vinton:Benton
Wapello:Louisa
Washinton:Washington
Waterloo:Black Hawk
Waukee:Dallas
Waukon:Allamakee
Waverly:Bremer
Webster City:Hamilton
West Des Moines:Polk,Dallas,Warren,Madison
West Liberty:Muscatine
West Union:Fayette
Windsor Heights:Polk
Winterset:Madison'''
CITY_MAP={a:b.split(',') for a,b in (x.split(':') for x in CITY_COUNTIES.splitlines())}
STYLE='''body{font:16px system-ui,sans-serif;color:#183047;background:#f3f6fa;max-width:1180px;margin:auto;padding:24px}a{color:#075ca8}h1{font-size:32px}h2{margin-top:32px}.note{background:#fff3d7;padding:16px;border-left:4px solid #b07819}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.card{background:white;padding:16px;border:1px solid #ccd9e3;border-radius:8px}img{width:100%;height:auto}table{border-collapse:collapse;width:100%;background:white}td,th{padding:8px;text-align:left;border-bottom:1px solid #d6e0e9}small{color:#485f72}code{overflow-wrap:anywhere}details{margin:12px 0}li{margin:6px 0}'''
def page(title,content):return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+STYLE+'</style><body>'+content+'</body></html>'
def href(p,label,prefix=''):return '<a href="'+html.escape(prefix+p,quote=True)+'">'+html.escape(label)+'</a>'
def main():
    for d in ['inventory','counties']:(ROOT/d).mkdir(exist_ok=True)
    contract=STATE/'data/turnout/priority-set.json';raw=contract.read_bytes();assert sha(raw)==CONTRACT_SHA
    data=json.loads(raw);counties=data['all_counties'];assert len(counties)==99
    keybytes=(STATE/'data/coordinator-priority-keys.txt').read_bytes();assert sha(keybytes)==KEY_SHA
    assert keybytes.decode().splitlines()==['IA:'+c['county_fips'] for c in counties[:41]]
    records=[json.loads(p.read_text()) for p in sorted((ROOT/'raw').glob('*.meta.json'))]
    audits=json.loads((ROOT/'geometry-audit.json').read_text())['archives'];amap={a['source_id']:a for a in audits}
    pdfs=json.loads((ROOT/'pdf-audit.json').read_text())['sources'];pmap={a['source_id']:a for a in pdfs}
    county_by_name={c['county']:c for c in counties};manifest=[]
    for m in records:
        key=m['source_id'];name=m.get('native_link_filename','');cs=[];kind='discovery-evidence';disposition='not a map asset';vintage='unknown';notes=[]
        if key.startswith('sos-county-') and name:
            if name.startswith('City of Maquoketa'):cs=['Jackson'];kind='local-ward-reference'
            elif name.startswith('Franklin County Hampton'):cs=['Franklin'];kind='city-precinct-reference'
            else:
                n=name.split(' County ')[0].replace('Buchananan','Buchanan')
                if name.startswith('Buena Vista'):n='Buena Vista'
                if n in county_by_name:cs=[n]
                kind='county-precinct-reference'
            vintage='2021/2022 reprecincting-era source publication; individual adoption/effective date unverified'
            disposition='reference geometry; current 2026 equivalence unapproved'
            if cs in [['Polk'],['Jackson']] and kind=='county-precinct-reference':
                kind='wrong-scope-district-source';disposition='sourceconflict: reject as precinct geometry';notes.append('Native layer/attributes describe supervisor-scale districts; archive title is insufficient.')
        elif key.startswith('sos-city-current-') and name:
            city=next((x for x in sorted(CITY_MAP,key=len,reverse=True) if name.startswith(x+' ')),None)
            cs=CITY_MAP.get(city,[]);kind='city-ward-reference' if 'Ward' in name else 'city-precinct-reference'
            vintage='reprecincting-era SOS collection; source-specific legal effective date unknown';disposition='partial city reference, not countywide geometry'
            if len(cs)>1:notes.append('Municipality may span counties. Association is navigation only; original extent not clipped or allocated.')
        elif m.get('county'):
            cs=[m['county']];label=m.get('link_label','');path=m.get('path','')
            if path.endswith('.pdf') or key.startswith('polk-all-precincts'):
                if re.search(r'Statistical Reports|Results|Summary|^By Precinct$|Calendar|Worksheet|Instructions|Precinct List',label,re.I):
                    kind='non-map-evidence';disposition='excluded from map coverage'
                elif re.search(r'Descriptions',label,re.I):kind='legal-description-reference';disposition='historical legal text; no November2026 geometry approval established'
                elif re.search(r'300.Foot',label,re.I):kind='polling-site-buffer-reference';disposition='excluded as precinct geometry; electioneering buffer scope'
                elif re.search(r'1972|1982|1992|2002|2012',label):kind='archive-map';disposition='historical reference only'
                else:kind='county-published-map';disposition='actual map asset; extent/vintage must be read from map, no approved reporting crosswalk'
                vintage='source PDF text/metadata retained in pdf-audit.json; edit/retrieval date is not adoption date'
            else:kind='county-authority-discovery'
        if m.get('status')!=200:disposition='access failure; no geometry accepted'
        if key=='lee-map-app-data':disposition='HTTP200 JSON permission error403; no GIS geometry accepted'
        a=amap.get(key,{});pp=pmap.get(key,{})
        features=sum(l['parsed_records'] for l in a.get('layers',[]))
        if a.get('layers'):
            labels=[f['native_ids'].get('LONGNAME') for l in a['layers'] for f in l['feature_checks']]
            placeholders=[s for s in labels if s and re.search(r'city precincts|unassigned',s,re.I)]
            if placeholders:notes.append('Source aggregate/unassigned labels retained, not individual precincts: '+repr(placeholders))
            if any(re.search(r'proposed|amend',l['shp_member'],re.I) for l in a['layers']):notes.append('Native filename contains Proposed/Amend: no approval inferred.')
        manifest.append(dict(source_id=key,counties=cs,county_association='explicit filename/authority/municipality navigation; not reporting-unit or feature crosswalk',kind=kind,disposition=disposition,vintage=vintage,source_url=m['requested_url'],parent_authority_url=m.get('parent_authority_url'),status=m.get('status'),source_path=m.get('path'),source_parts=m.get('parts'),entity_sha256=m.get('entity_sha256'),entity_bytes=m.get('entity_bytes'),notes=notes,features=features,layers=[l['layer_key'] for l in a.get('layers',[])],pdf_documents=len(pp.get('documents',[])),pdf_pages=pp.get('total_pages',0)))
    write_json(ROOT/'manifest.json',dict(schema_version=1,contract_sha256=CONTRACT_SHA,priority_key_sha256=KEY_SHA,assets=manifest))
    write_json(ROOT/'source-manifest.json',dict(schema_version=1,records=records))
    labels=collections.defaultdict(lambda:collections.defaultdict(list))
    for a in manifest:
        if a['status']!=200 or a['kind'] in ['wrong-scope-district-source','discovery-evidence']:continue
        for l in amap.get(a['source_id'],{}).get('layers',[]):
            for f in l['feature_checks']:
                for field,value in f['native_ids'].items():
                    if not isinstance(value,str) or not value:continue
                    for county in a['counties']:labels[county][value].append(dict(layer_key=l['layer_key'],record_ordinal=f['record_ordinal'],native_field=field,literal_value=value))
    diagnostics=[];inventory=[];counts=collections.Counter()
    for c in counties:
        cn=c['county'];assets=[a for a in manifest if cn in a['counties']];good=[a for a in assets if a['status']==200 and a['kind'] in ['county-precinct-reference','city-precinct-reference','local-ward-reference','city-ward-reference','county-published-map']]
        scopes={}
        for year,contexts in c['native_constituents'].items():
            for context,units in contexts.items():
                if not isinstance(units,list):continue
                scopes[year+'/'+context]=len(units)
                for i,obj in enumerate(units):
                    candidates=labels[cn].get(obj.get('native_unit_label',''),[])
                    # Literal equality supplies review candidates only. Never accept a crosswalk.
                    status='administrative-no-polygon' if context=='candidate_administrative_controls' else 'ambiguous' if candidates else 'unknown' if good else 'missinggeometry'
                    reason='County control is not a constituent polygon.' if status=='administrative-no-polygon' else 'Literal label candidates only; source scope/vintage/physical equivalence unproven.' if candidates else 'No documented source-unit to polygon crosswalk. Names/counts cannot prove physical extent.'
                    diagnostics.append(dict(county=cn,county_fips=c['county_fips'],year=year,context=context,context_ordinal=i+1,original_constituent=obj,diagnostic_status=status,literal_label_candidates=candidates,approved_polygon_matches=[],vote_allocation=None,reason=reason))
                    counts[year+'/'+context]+=1
        row=dict(rank=c['rank_2024'],county=cn,county_fips=c['county_fips'],priority=c['in_minimum80'],candidate_generic_marks=c['pres2024_candidate_generic_writein_votes'],source_native_context_counts=scopes,native_source_roster=c['native_constituents']['2024'].get('native_source_roster'),source_ids=[a['source_id'] for a in assets],accepted_reference_asset_ids=[a['source_id'] for a in good],current_2026_geometry_status='unknown/unapproved; publication and edit dates do not establish approval',approved_november_2026_crosswalks=0,missing_extent='Source-native units remain unlocated until documentary crosswalk; aggregate/unassigned city areas and partial city files retained separately.',county_preview_page='counties/'+c['county_fips']+'.html')
        if cn in ['Kossuth','Lyon']:row['missing_extent']='SOS county ZIP absent from observed county index; city-only reference files do not cover full county.'
        if cn=='Polk':row['missing_extent']='SOS county ZIP rejected as supervisor-scale districts; official countywide PDF and detailed precinct ZIPs provide raster reference, not a vector/crosswalk replacement.'
        if cn=='Jackson':row['missing_extent']='SOS county ZIP rejected as supervisor districts. County PDF scan shows rural groups 1-8 without a Maquoketa ward inset; the separate five-ward ZIP is retained. Combined completeness and current equivalence remain unapproved.'
        primary=next((a for a in good if a['source_id']=={'Polk':'polk-wall-precinct-map','Jackson':'local-jackson-7305d66b3133'}.get(cn)),None)
        primary=primary or next((a for a in good if a['kind']=='county-precinct-reference'),None) or (good[0] if good else None)
        if primary:
            pp=pmap.get(primary['source_id'],{});gg=amap.get(primary['source_id'],{})
            row['index_primary_source_id']=primary['source_id'];row['index_download']=primary['source_path']
            row['index_preview']=next((d['first_page_preview'] for d in pp.get('documents',[]) if d.get('first_page_preview')),None) or next((l['preview']['path'] for l in gg.get('layers',[]) if l.get('preview')),None)
        inventory.append(row)
        blocks=['<p>'+href('../index.html','All counties')+'</p><h1>'+html.escape(str(c['rank_2024'])+'. '+cn+' County')+'</h1><p class="note">Reference maps. No approved November 2026 reporting-unit crosswalk.</p><p>'+html.escape(row['missing_extent'])+'</p><p>'+href('../inventory/constituent-diagnostics.json.gz','Exact source-native diagnostics (gzip JSON)')+'</p>']
        for a in assets:
            if a['status']!=200 or a['kind'] in ['county-authority-discovery','discovery-evidence','non-map-evidence']:continue
            m=next(m for m in records if m['source_id']==a['source_id']);p=amap.get(a['source_id'],{});pp=pmap.get(a['source_id'],{})
            b='<article class="card"><h2>'+html.escape(m.get('native_link_filename') or m.get('link_label') or a['source_id'])+'</h2><p>'+html.escape(a['disposition'])+'</p><p>'+html.escape('; '.join(a['notes']))+'</p>'
            if a['source_path']:b+=href(a['source_path'],'Original source download','../')
            elif a['source_parts']:
                b+='<p>Exact ordered byte parts; reconstruct with reconstruct.py:</p><ol>'+''.join('<li>'+href(p['path'],pathlib.Path(p['path']).name,'../')+'</li>' for p in a['source_parts'])+'</ol>'
            b+=' <a href="'+html.escape(a['source_url'],quote=True)+'">Primary source</a><p><small>'+html.escape(a['vintage'])+'</small></p>'
            for l in p.get('layers',[]):
                b+='<p>'+str(l['parsed_records'])+' native records; '+str(l['vertices'])+' vertices. '+href(l['native_derivative'],'Full native attributes/vertices','../')+'</p>'
                if l.get('preview'):b+='<img loading="lazy" src="../'+l['preview']['path']+'" alt="Reference geometry preview">'
            for doc in pp.get('documents',[])[:1]:
                if doc.get('first_page_preview'):b+='<img loading="lazy" src="../'+doc['first_page_preview']+'" alt="Actual rendered first map page">'
            if pp.get('contact_sheets'):b+='<details><summary>All rendered PDF pages ('+str(pp['total_pages'])+')</summary>'+''.join('<p>'+href(cp,'Contact sheet '+str(i+1),'../')+'</p>' for i,cp in enumerate(pp['contact_sheets']))+'</details>'
            b+='</article>';blocks.append(b)
        blocks.append('<h2>Historical source scopes</h2><pre>'+html.escape(json.dumps(scopes,indent=2))+'</pre>')
        (ROOT/'counties'/f"{c['county_fips']}.html").write_text(page(cn+' reference maps',''.join(blocks)))
    assert len(diagnostics)==13558
    gzjson(ROOT/'inventory/constituent-diagnostics.json.gz',dict(schema_version=1,contract_sha256=CONTRACT_SHA,original_object_count=len(diagnostics),ordered_exact_source_constituents=diagnostics))
    write_json(ROOT/'inventory/counties.json',inventory)
    write_json(ROOT/'inventory/constituent-counts.json',dict(total=len(diagnostics),contexts=dict(counts),statuses=dict(collections.Counter(x['diagnostic_status'] for x in diagnostics)),rosters=sum(x['native_source_roster'] is not None for x in inventory),approved_crosswalks=0))
    with (ROOT/'manifest.csv').open('w',newline='') as f:
        keys=['rank','county','county_fips','priority','candidate_generic_marks','current_2026_geometry_status','missing_extent','county_preview_page'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(inventory)
    intro='<h1>Iowa precinct map evidence</h1><p>Offline county previews, original downloads and source diagnostics. Exact 41 research counties appear first in the accepted order; all 99 remain in inventory.</p><p class="note">These are reference assets. Current publication, a matching label, a map title, or an edit date does not establish approved November 2026 boundaries or a reporting-unit crosswalk.</p><p>'+href('SCHEMA.md','Schema and reproduction')+' | '+href('manifest.json','Asset dispositions')+' | '+href('geometry-audit.json','Full GIS audit')+' | '+href('pdf-audit.json','PDF audit')+' | '+href('inventory/constituent-diagnostics.json.gz','13,558 exact constituent diagnostics')+'</p><h2>Exact 41 priority counties</h2><div class="grid">'
    cards=[]
    for r in inventory[:41]:
        picture='<img loading="lazy" src="'+r['index_preview']+'" alt="'+html.escape(r['county'])+' reference map preview">' if r.get('index_preview') else ''
        download=href(r['index_download'],'Primary reference download') if r.get('index_download') else ''
        cards.append('<div class="card"><h2>'+href(r['county_preview_page'],str(r['rank'])+'. '+r['county'])+'</h2>'+picture+'<p>'+download+' | '+href(r['county_preview_page'],'All maps and diagnostics')+'</p><p>'+str(len(r['accepted_reference_asset_ids']))+' reference assets; '+format(r['candidate_generic_marks'],',')+' baseline candidate/generic marks.</p><small>'+html.escape(r['missing_extent'])+'</small></div>')
    rest='</div><h2>All 99 counties in accepted volume order</h2><table><tr><th>Rank</th><th>County</th><th>FIPS</th><th>Reference assets</th></tr>'+''.join('<tr><td>'+str(r['rank'])+'</td><td>'+href(r['county_preview_page'],r['county'])+'</td><td>'+r['county_fips']+'</td><td>'+str(len(r['accepted_reference_asset_ids']))+'</td></tr>' for r in inventory)+'</table>'
    (ROOT/'index.html').write_text(page('Iowa precinct map evidence',intro+''.join(cards)+rest))
    # Stable, consumed read-only inputs are pinned individually, avoiding circular output pins.
    paths=['data/turnout/priority-set.json','data/coordinator-priority-keys.txt','data/county-turnout.csv','data/turnout/SCHEMA.md','data/coordinator-native-contract-checks.json','data/coordinator-baseline-reconciliation.json','data/turnout/asset-manifest.json','data/baselines/asset-manifest.json']
    pins={p:dict(bytes=(STATE/p).stat().st_size,sha256=sha((STATE/p).read_bytes())) for p in paths if (STATE/p).exists()}
    write_json(ROOT/'read-only-pins.json',pins)
    print(json.dumps(dict(counties=len(inventory),priority=sum(r['priority'] for r in inventory),diagnostics=len(diagnostics),priority_with_assets=sum(bool(r['accepted_reference_asset_ids']) for r in inventory[:41]),assets=len(manifest))))
if __name__=='__main__':main()
