#!/usr/bin/env python3
"""Cross-assignment integrity checks for the saved North Carolina package."""
from pathlib import Path
from collections import defaultdict
import csv,datetime,hashlib,json,math,re,sys
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
def read(rel):
 with (ROOT/rel).open(newline='') as f:return list(csv.DictReader(f))
def close(x,y,tol=1e-7):assert math.isfinite(x) and abs(x-y)<=tol,(x,y)
t=read('data/county-turnout.csv');b=read('data/county-baselines.csv')
assert len(t)==100 and len({r['county_fips'] for r in t})==100
assert len(b)==300 and len({(r['year'],r['contest'],r['county_fips']) for r in b})==300
bm={(r['year'],r['contest'],r['county_fips']):r for r in b}
for r in b:
 assert int(r['dem_votes'])+int(r['rep_votes'])+int(r['other_votes'])==int(r['contest_votes'])
 assert int(r['dem_votes'])+int(r['rep_votes'])==int(r['major_party_votes'])
n=0
for r in t:
 for y,c,p in [('2024','US PRESIDENT','president_2024'),('2022','US SENATE','senate_2022')]:
  other=bm[(y,c,r['county_fips'])]
  for a,z in [('d','dem_votes'),('r','rep_votes'),('other','other_votes'),('total','contest_votes')]:
   assert int(r[p+'_'+a])==int(other[z]),(r['county'],y,a);n+=1
ranked=sorted(t,key=lambda r:-int(r['president_2024_total']))
assert [r['county_fips'] for r in ranked]==[r['county_fips'] for r in t]
state=sum(int(r['president_2024_total']) for r in t);assert state==5699145
p=[r for r in t if r['research_priority']=='1'];assert len(p)==38
pv=sum(int(r['president_2024_total']) for r in p);assert pv==4576486
assert 5*(pv-int(p[-1]['president_2024_total']))<4*state<=5*pv
assert set(r['county_fips'] for r in t if r['top15']=='1')<=set(r['county_fips'] for r in p)
sc=read('data/baselines/state-scenarios.csv');targets=read('data/baselines/county-target-scenarios.csv');groups=defaultdict(list)
for r in targets:groups[(r['scenario_id'],r['target'])].append(r)
assert len(sc)==42 and len(targets)==4200 and len(groups)==42
for s in sc:
 rr=groups[(s['scenario_id'],s['target'])];assert len(rr)==100 and {r['county_fips'] for r in rr}=={r['county_fips'] for r in t}
 T=sum(float(r['expected_major_party_votes']) for r in rr);M0=sum(float(r['expected_major_party_votes'])*(2*float(r['baseline_dem_two_party_share'])-1) for r in rr)
 goal=float(s['target_d_minus_r_margin_pp'])/100*T
 close(T,float(s['state_expected_major_party_votes']));close(sum(float(r['turnout_weight']) for r in rr),1)
 close(sum(float(r['expected_major_party_votes'])*(2*float(r['target_dem_share'])-1) for r in rr),goal)
 delta=(goal-M0)/(2*T)
 close(delta*100,float(s['required_dem_share_shift_pp']))
 for r in rr:
  Tc=float(r['expected_major_party_votes']);q=float(r['target_dem_share']);base=float(r['baseline_dem_two_party_share'])
  assert 0<=q<=1;close(q-base,delta);close(float(r['net_vote_value_plus_1pp_dem_share']),.02*Tc)
  conditional=(Tc+goal-(M0-Tc*(2*base-1)))/(2*Tc)
  close(conditional,float(r['selected_county_required_share_others_at_baseline']))
# Native 2022 tie threshold and the share-vs-margin factor of two.
D=sum(int(r['dem_votes']) for r in b if r['year']=='2022');R=sum(int(r['rep_votes']) for r in b if r['year']=='2022')
close((R-D)/(2*(D+R))*100,1.6496266093199277)
close(((.01*(D+R)-(D-R))/(2*(D+R))-(R-D)/(2*(D+R)))*100,.5)
result={'scope':'baselines_only' if '--baselines-only' in sys.argv else 'integrated_package','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_cells_exact':n,'counties':100,'baseline_rows':300,'priority_count':len(p),'priority_votes':pv,'state_votes':state,'scenario_rows':len(sc),'county_target_rows':len(targets)}
if '--baselines-only' not in sys.argv:
 inventory=read('data/official-results-sources.csv');coverage=read('data/results-sources/coverage.csv')
 county_sources=[r for r in inventory if r['scope']=='county']
 all_fips={r['county_fips'] for r in t};priority_fips={r['county_fips'] for r in p}
 assert len(inventory)==104 and len(county_sources)==100
 assert {r['county_fips'] for r in county_sources}==all_fips
 assert {r['county_fips'] for r in county_sources if r['priority']=='1'}==priority_fips
 assert len(coverage)==100 and {r['county_fips'] for r in coverage}==all_fips
 for r in coverage:
  assert r['priority']==('1' if r['county_fips'] in priority_fips else '0')
  assert r['outstanding_aggregate_row_present']=='1'
 maps=read('maps/manifest.csv');assert len(maps)==152
 for date in ('2024-07-23','2026-08-24'):
  for fmt in ('GeoJSON','SVG preview derivative'):
   group=[r for r in maps if r['geometry_vintage']==date and r['format']==fmt]
   assert len(group)==38 and {r['county_fips'] for r in group}==priority_fips
 for r in maps:
  asset=ROOT/'maps'/r['local_path'];raw=asset.read_bytes()
  assert len(raw)==int(r['bytes']) and hashlib.sha256(raw).hexdigest()==r['sha256']
 result.update(official_source_rows=len(inventory),official_counties=len(coverage),map_assets=len(maps),priority_sets_reconciled=True)
 required=['turnout.md','county-partisanship.md','official-results.md','precinct-maps.md','local-news-results.md','live-polling-strategy.md','research-review.md','research-dispatch.md','README.md','maps/index.html']
 for rel in required:assert (ROOT/rel).is_file(),rel
 links=0
 for f in ROOT.rglob('*.md'):
  for dest in re.findall(r'\]\(([^)]+)\)',f.read_text()):
   dest=dest.strip().split(' ')[0].strip('<>')
   if not dest or dest.startswith(('#','http:','https:','mailto:','data:')):continue
   path=unquote(dest.split('#')[0]);assert (f.parent/path).exists(),(str(f),dest);links+=1
 files=[f for f in ROOT.rglob('*') if f.is_file() and not any(p in ('__pycache__','.runtime') for p in f.relative_to(ROOT).parts) and f.suffix not in ('.pyc','.pyo')]
 assert all(f.stat().st_size<40*1024*1024 for f in files)
 result.update(relative_links_checked=links,files_checked=len(files),all_files_under_40MiB=True)
result['status']='pass';(ROOT/'data/coordinator-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
