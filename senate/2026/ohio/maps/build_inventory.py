#!/usr/bin/env python3
"""Offline 88-county inventory and all native historical unit compatibility; no vote allocation."""
from pathlib import Path
import collections,csv,gzip,hashlib,io,json,re
R=Path(__file__).resolve().parent;S=R.parent
j=lambda p:json.loads((R/p).read_text())
rows=list(csv.DictReader((S/'data/county-turnout.csv').open()));dispatch=json.loads((S/'data/turnout/priority-set.json').read_text());ds=j('dataset-manifest.json');pdfs=j('pdf-manifest.json');census=j('census-all88-inventory.json');initial=j('initial-inventory.json')
assert hashlib.sha256((S/'data/county-turnout.csv').read_bytes()).hexdigest()=='d9133f7f88eca91b8bef8f3987b3e1abfb30b19e61d1d824a1e270dde4049a90'
assert [r['county_fips'] for r in rows]==dispatch['ordered_county_keys_all88'];assert [r['county_fips'] for r in rows if r['in_minimum80']=='1']==dispatch['ordered_priority_county_keys']
# These fields are explicitly source-labeled state precinct identifiers, not generic numeric object IDs.
code_fields={'clark':'Name2','clermont-published':'STATEID','muskingum':'STATE_ID','fairfield-published':'SOS_CODE','butler-2019':'STATECODE','columbiana':'PREC'}
name_fields={'franklin-2025':'NAME','franklin-2023':'NAME','franklin-2022':'NAME','cuyahoga':'Label','hamilton':'PRC_NAME','stark':'NAME','delaware':'name','licking':'PrecinctName','erie':'Jurisdctn','portage':'NAME','mahoning-2025':'NAME','geauga':'TwpPctFull'}
maps=collections.defaultdict(list);fieldvalues={};attrs={}
for d in ds:
 if d['dataset_id'].startswith('census2020'):continue
 did=d['dataset_id'];maps[d['county_fips']].append(d);g=json.loads(gzip.decompress((R/d['geojson_path']).read_bytes()));attrs[did]=[f['properties'] for f in g['features']]
 for f in [code_fields.get(did),name_fields.get(did)]:
  if f:fieldvalues[(did,f)]=collections.defaultdict(list)
  if f:
   for n,a in enumerate(attrs[did]):
    v=a.get(f)
    if v is not None and str(v).strip():fieldvalues[(did,f)][str(v)].append(n)
units=[]
for year in [2024,2022]:
 with gzip.open(S/f'data/turnout/reporting-units-{year}.csv.gz','rt') as f:us=list(csv.DictReader(f))
 assert len(us)=={2024:8878,2022:8933}[year]
 expected={u['unit_key']:(u['precinct_code_native'],u['precinct_name_native']) for c in dispatch['county_records'] for u in c['reporting_units'][str(year)]['units']}
 assert {u['unit_key']:(u['precinct_code_native'],u['precinct_name_native']) for u in us}==expected
 for u in us:
  codes=[];names=[]
  for d in maps[u['county_fips']]:
   did=d['dataset_id'];cf=code_fields.get(did);nf=name_fields.get(did)
   for field,what,res in [(cf,u['precinct_code_native'],codes),(nf,u['precinct_name_native'],names)]:
    if field:
     match=fieldvalues[(did,field)].get(what,[])
     if match:res.append({'dataset':did,'source_field':field,'source_value':what,'source_ordinals':match})
  u=dict(u,code_inventory_matches=json.dumps(codes,separators=(',',':')),exact_name_inventory_matches=json.dumps(names,separators=(',',':')),crosswalk_status='unvalidated; string equality is inventory evidence only; no cross-year or 2026 geometry/vote allocation',writein_allocation='not available at precinct level; county residual retained outside polygons')
  units.append(u)
s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(units[0]));w.writeheader();w.writerows(units);(R/'reporting-unit-compatibility.csv.gz').write_bytes(gzip.compress(s.getvalue().encode(),mtime=0))
# Explicit inventory differences for every selected dataset, each vintage separately.
compat=[]
for d in ds:
 did=d['dataset_id']
 if did.startswith('census'):continue
 cf=code_fields.get(did);nf=name_fields.get(did)
 for y in [2024,2022]:
  us=[u for u in units if u['county_fips']==d['county_fips'] and u['election_date'].startswith(str(y))];k='precinct_code_native' if cf else 'precinct_name_native';field=cf or nf
  available=set(fieldvalues.get((did,field),{}));base={u[k] for u in us};blank=len(attrs[did])-sum(1 for a in attrs[did] if field and a.get(field) is not None and str(a.get(field)).strip())
  compat.append(dict(dataset=did,county_fips=d['county_fips'],baseline_year=y,comparison_kind='exact native code' if cf else 'exact name only' if nf else 'no comparable identifier',source_field=field,features=d['feature_count'],nonempty_geometries=d['feature_count']-d['empty_count'],source_blank_identifier_features=blank,native_baseline_units=len(us),matching_strings=len(base&available),unmatched_baseline_values=sorted(base-available),source_values_absent_from_baseline=sorted(available-base),reused_source_values={v:len(a) for v,a in fieldvalues.get((did,field),{}).items() if len(a)>1},approval='not established',geographic_crosswalk='not validated'))
(R/'compatibility-summary.json').write_text(json.dumps(compat,indent=2)+'\n')
# Whole-state inventory: actual retained Census feature inventory and both historical result rosters.
directory=j('official-boe-directory.json')['counties']
inv=[]
for r,init in zip(rows,initial):
 f=r['county_fips'];p=[d for d in pdfs if d['county']==r['county'].lower() and d['complete_pdf']];g=maps[f]
 inv.append(dict(rank=int(r['rank_2024_senate']),county=r['county'],county_fips=f,county_native_id=r['county_native_id'],official_boe_directory_url=directory[r['county']],official_directory_evidence='evidence/sos-directory-browser.txt',priority=r['in_minimum80']=='1',native_units_2024=int(r['native_reporting_units_2024']),native_units_2022=int(r['native_reporting_units_2022']),census2020_vtd_count=census[f]['features'],census_original='evidence/finaldiscovery/census-state-vtd.bin',county_datasets=[d['dataset_id'] for d in g],county_pdf_paths=[d['path'] for d in p],county_pdf_pages=sum(d['page_count'] for d in p),boe_route_attempted=init['landing_url'],boe_route_http_status=init['status'],map_approval_nov2026='not established',native_2026_reporting_crosswalk='not validated',scope='deep priority acquisition' if r['in_minimum80']=='1' else 'whole-state inventory; Census 2020 retained; current county maps not deeply investigated'))
(R/'county-inventory.json').write_text(json.dumps(inv,indent=2)+'\n')
s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=[k for k in inv[0] if k not in ['county_datasets','county_pdf_paths']]+['county_datasets','county_pdf_paths']);w.writeheader()
for r in inv:w.writerow(dict(r,county_datasets=';'.join(r['county_datasets']),county_pdf_paths=';'.join(r['county_pdf_paths'])))
(R/'county-inventory.csv').write_text(s.getvalue())
inputs=['data/county-turnout.csv','data/turnout/priority-set.json','data/coordinator-baseline-reconciliation.json','data/turnout/reporting-units-2024.csv.gz','data/turnout/reporting-units-2022.csv.gz']
(R/'input-hashes.json').write_text(json.dumps({p:hashlib.sha256((S/p).read_bytes()).hexdigest() for p in inputs},indent=2)+'\n')
print('88 counties;',len(units),'native units preserved;',len(compat),'dataset/vintage inventory comparisons')
