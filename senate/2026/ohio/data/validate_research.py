#!/usr/bin/env python3
"""Coordinator cross-file coverage and independent statewide scenario arithmetic."""
from pathlib import Path
from collections import defaultdict
import csv,json,runpy,gzip,io,math,datetime,sys,hashlib,re
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'data/reconcile_baselines.py'))
def read(rel):
 p=ROOT/rel;s=gzip.decompress(p.read_bytes()).decode() if p.suffix=='.gz' else p.read_text()
 return list(csv.DictReader(io.StringIO(s)))
def close(a,b,tol=1e-6):assert math.isfinite(float(a)) and abs(float(a)-float(b))<=tol,(a,b)
baseline=read('data/county-baselines.csv');assert len(baseline)==440
by={(r['comparison'],r['county_fips']):r for r in baseline};assert len(by)==440
turnout=read('data/county-turnout.csv');tm={r['county_fips']:r for r in turnout}
for year,n in [('2024',8878),('2022',8933)]:
 units=read(f'data/turnout/reporting-units-{year}.csv.gz');assert len(units)==n
 assert len({r['unit_key'] for r in units})==n
 assert {r['county_fips'] for r in units}==set(tm)
 for fips,t in tm.items():
  rr=[r for r in units if r['county_fips']==fips]
  assert len(rr)==int(t[f'native_reporting_units_{year}'])
  for field in ('ballots_counted','registered_voters'):assert sum(int(r[field]) for r in rr)==int(t[field+'_'+year])
  assert all(not r['voting_method'] and not r['undervotes'] and not r['overvotes'] for r in rr)
s=read('data/baselines/state-scenarios.csv');u=read('data/baselines/county-target-scenarios.csv');sel=read('data/baselines/selected-county-targets.csv');assert len(s)==24 and len(u)==len(sel)==2112
groups=defaultdict(list);selected={}
for r in u:groups[(r['scenario'],r['target_two_party_margin'])].append(r)
for r in sel:
 k=(r['scenario'],r['target_two_party_margin'],r['county_fips']);assert k not in selected;selected[k]=r
for st in s:
 key=(st['scenario'],st['target_two_party_margin']);rows=groups[key];assert len(rows)==88 and {r['county_fips'] for r in rows}==set(tm)
 volume=float(st['scenario_major_party_votes']);target=float(st['target_two_party_margin']);preference=st['preference_comparison'];mix=st['turnout_mix_comparison']
 mixT=sum(int(by[(mix,f)]['two_party_votes']) for f in tm);M=0
 for r in rows:
  f=r['county_fips'];b=by[(preference,f)];w=int(by[(mix,f)]['two_party_votes'])/mixT;t=volume*w;p=int(b['d_votes'])/int(b['two_party_votes']);M+=t*(2*p-1)
  close(r['scenario_major_party_votes'],t);close(r['statewide_weight'],w,1e-12);close(r['baseline_d_share_two_party'],p,1e-12);close(r['baseline_net_contribution'],t*(2*p-1));close(r['net_gain_per_1pp_d_share'],.02*t)
 delta=(target*volume-M)/(2*volume)
 close(st['baseline_d_minus_r_net_votes'],M);close(st['uniform_d_share_shift'],delta,1e-12);close(sum(float(r['target_net_votes']) for r in rows),target*volume)
 for r in rows:
  t=float(r['scenario_major_party_votes']);p=float(r['baseline_d_share_two_party']);q=p+delta
  close(r['target_d_share_two_party'],q,1e-12);close(r['target_net_votes'],t*(2*q-1))
  selected_row=selected[key+(r['county_fips'],)];other=M-t*(2*p-1);need=(target*volume-other+t)/(2*t)
  close(selected_row['all_other_counties_net_votes'],other);close(selected_row['selected_required_d_share'],need,1e-10)
  assert selected_row['status']==('impossible' if need>1 else 'already_secured' if need<0 else 'feasible')
result={'status':'pass','scope':'baselines_only' if '--baselines-only' in sys.argv else 'integrated_package','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_rows':440,'counties':88,'county_contest_checks':264,'candidate_cells':2464,'native_units_2024':8878,'native_units_2022':8933,'state_scenarios':24,'county_scenarios':2112,'selected_county_targets':2112}
if '--baselines-only' not in sys.argv:
 for rel in ('README.md','turnout.md','county-partisanship.md','official-results.md','precinct-maps.md','local-news-results.md','live-polling-strategy.md','research-review.md','research-dispatch.md','maps/index.html'):assert (ROOT/rel).is_file(),rel
 def load(rel):return json.loads((ROOT/rel).read_text())
 def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 official=read('data/official-results-sources.csv');assert len(official)==89
 oc={r['county_fips']:r for r in official if r['county_fips']};assert set(oc)==set(tm)
 priority_fips=[f for f,t in sorted(tm.items(),key=lambda kv:int(kv[1]['rank_2024_senate']))][:32]
 assert len([r for r in official if r['priority_rank']])==32
 assert [f for f,r in sorted(oc.items(),key=lambda kv:int(kv[1]['priority_rank']) if kv[1]['priority_rank'] else 1000) if r['priority_rank']]==priority_fips
 assert all(not r['outstanding_eligible_senate_votes'] and r['local_cadence_measured']=='False' for r in official)
 ov=load('data/results-sources/validation.json');assert ov['status']=='PASS_WITH_EXPLICIT_SOURCE_GAPS' and ov['reparsed_certified_county_candidate_cells']==2464 and ov['Cuyahoga_precinct_source_differences']==1
 assert digest(ROOT/'official-results.md')==ov['report_sha256'] and digest(ROOT/'data/official-results-sources.csv')==ov['inventory_sha256']
 for rel,h in load('data/results-sources/dependency-hashes.json')['sha256'].items():assert digest(ROOT/rel)==h,rel
 mi=load('maps/county-inventory.json');assert len(mi)==88 and {r['county_fips'] for r in mi}==set(tm)
 assert [r['county_fips'] for r in sorted(mi,key=lambda r:r['rank']) if r['priority']]==priority_fips
 for r in mi:
  t=tm[r['county_fips']]
  assert r['county_native_id']==t['county_native_id']
  assert r['native_units_2024']==int(t['native_reporting_units_2024']) and r['native_units_2022']==int(t['native_reporting_units_2022'])
  assert (ROOT/'maps'/r['index_preview_path']).is_file() if r.get('index_preview_path') else not r['priority']
 assert sum(len(r['county_pdf_paths']) for r in mi)==205 and sum(r['county_pdf_pages'] for r in mi)==466
 assert sum(r.get('county_geometry_nonempty_features',0)>0 for r in mi)==20
 mc=read('maps/reporting-unit-compatibility.csv.gz');assert len(mc)==17811
 mcby={r['unit_key']:r for r in mc};assert len(mcby)==17811
 for year in ('2024','2022'):
  for r in read(f'data/turnout/reporting-units-{year}.csv.gz'):
   assert all(mcby[r['unit_key']][k]==v for k,v in r.items()),r['unit_key']
 datasets=load('maps/dataset-manifest.json');assert len(datasets)==60
 assert all(not r.get('approved_nov2026',False) for r in datasets)
 copied=ROOT/'maps/evidence/coordinator-review/tuscarawas-official-render.png'
 assert copied.read_bytes()==(ROOT/'data/map-review/tuscarawas-official-render.png').read_bytes()
 artifact_checks={}
 for directory in ('maps','data/results-sources'):
  entries=load(directory+'/artifact-manifest.json')
  for e in entries:
   p=ROOT/directory/e['path'];assert p.stat().st_size==e['bytes'] and digest(p)==e['sha256'],str(p)
  artifact_checks[directory]=len(entries)
 news=load('data/news/manifest.json')
 for r in news:
  p=ROOT/'data/news'/r['asset'];b=gzip.decompress(p.read_bytes())
  assert digest(p)==r['stored_sha256'] and hashlib.sha256(b).hexdigest()==r['raw_sha256'] and len(b)==r['bytes']
 result.update(official_authorities=89,priority_source_counties=32,map_counties=88,map_priority_sections=32,map_native_unit_matches=17811,map_datasets=60,map_county_GIS_coverage=20,map_pdfs=205,map_pdf_pages=466,artifact_hashes_checked=artifact_checks,news_snapshots_checked=len(news),tuscarawas_exact_raster_copy=True)
 links=0
 for p in ROOT.rglob('*.md'):
  for dest in re.findall(r'\]\(([^)]+)\)',p.read_text()):
   dest=dest.strip().split(' ')[0].strip('<>')
   if not dest or dest.startswith(('#','http:','https:','mailto:','data:')):continue
   assert (p.parent/unquote(dest.split('#')[0])).exists(),(str(p),dest);links+=1
 files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in ('__pycache__','.runtime') for x in p.relative_to(ROOT).parts) and p.suffix not in ('.pyc','.pyo')]
 assert all(p.stat().st_size<40_000_000 for p in files)
 result.update(relative_links_checked=links,files_checked=len(files),all_files_under_40000000_bytes=True)
(ROOT/'data/coordinator-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
