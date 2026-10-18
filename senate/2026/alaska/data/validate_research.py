#!/usr/bin/env python3
"""Coordinator checks of Alaska cross-assignment scope and scenario arithmetic."""
from pathlib import Path
from collections import defaultdict
import csv,json,math,datetime,sys,re,runpy,hashlib,gzip
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'data/reconcile_baselines.py'))
def read(rel):return list(csv.DictReader((ROOT/rel).open()))
def close(x,y,tol=1e-7):assert math.isfinite(x) and abs(x-y)<tol,(x,y)
base=read('data/county-baselines.csv');assert len(base)==1558
assert all(not r['county_fips'] for r in base)
state_targets=read('data/baselines/state-target-scenarios.csv');unit_targets=read('data/baselines/unit-target-scenarios.csv');groups=defaultdict(list)
for r in unit_targets:groups[(r['scenario'],r['target_statewide_margin_pp'])].append(r)
assert len(state_targets)==16 and len(unit_targets)==656 and len(groups)==16
for s in state_targets:
 rows=groups[(s['scenario'],s['target_margin_pp'])]
 assert len(rows)==41 and {int(r['house_district']) for r in rows}==set(range(1,41))|{99}
 y=s['baseline_year'];assert y in ('2020','2024')
 assert {r['baseline_year'] for r in rows}=={y}
 assert {r['opposition_candidate'] for r in rows}=={s['opposition_candidate']}
 assert s['opposition_candidate']==('Gross, Al' if y=='2020' else 'Harris/Walz')
 T=sum(float(r['expected_pair_votes']) for r in rows);M=sum(float(r['expected_pair_votes'])*(2*float(r['baseline_opposition_pair_share'])-1) for r in rows);goal=float(s['target_margin_pp'])/100*T;delta=(goal-M)/(2*T)
 close(T,float(s['expected_pair_votes']));close(M,float(s['fixed_share_net_votes']));close(sum(float(r['weight']) for r in rows),1)
 close(100*delta,float(s['uniform_opposition_share_shift_pp']))
 close(sum(float(r['expected_pair_votes'])*(2*float(r['target_opposition_share'])-1) for r in rows),goal)
 for r in rows:
  ti=float(r['expected_pair_votes']);q=float(r['target_opposition_share']);bi=float(r['baseline_opposition_pair_share'])
  assert 0<=q<=1;close(q-bi,delta);close(float(r['net_gain_for_one_share_pp']),.02*ti)
  close(float(r['conditional_selected_unit_share']),(ti+goal-(M-ti*(2*bi-1)))/(2*ti))
for y in ('2020','2024'):
 for volume in ('low_2022','base_2024','high_2020','native'):
  rows=[s for s in state_targets if s['baseline_year']==y and volume in s['scenario']]
  if len(rows)==2:
   d={float(s['target_margin_pp']):float(s['uniform_opposition_share_shift_pp']) for s in rows};close(d[1]-d[0],.5)
rcv=read('data/baselines/rcv-district-rounds.csv');assert len(rcv)==861
expected={
1:{'Chesbro, Patricia R.':28233,'Kelley, Buzz A.':8575,'Murkowski, Lisa':114118,'Tshibaka, Kelly C.':112101,'Blanks':3271,'Exhausted':0,'Overvotes':499},
2:{'Chesbro, Patricia R.':29134,'Kelley, Buzz A.':0,'Murkowski, Lisa':115759,'Tshibaka, Kelly C.':115310,'Blanks':3271,'Exhausted':2806,'Overvotes':517},
3:{'Chesbro, Patricia R.':0,'Kelley, Buzz A.':0,'Murkowski, Lisa':136330,'Tshibaka, Kelly C.':117534,'Blanks':3271,'Exhausted':9107,'Overvotes':555}}
for rnd,cats in expected.items():
 rows=[r for r in rcv if int(r['round'])==rnd];assert len(rows)==287
 for cat,value in cats.items():assert sum(int(r['votes']) for r in rows if r['category']==cat)==value
 assert sum(cats.values())==266797
 for hd in list(range(1,41))+[99]:
  rr=[r for r in rows if int(r['house_district'])==hd];assert len(rr)==7
  assert sum(int(r['votes']) for r in rr)==int(rr[0]['cvr_ballots'])
cs=read('data/baselines/rcv-native-turnout-scenarios.csv');cu=read('data/baselines/rcv-native-turnout-contributions.csv');assert len(cs)==3 and len(cu)==123
for s in cs:
 rows=[r for r in cu if r['scenario']==s['scenario']];assert len(rows)==41 and {int(r['house_district']) for r in rows}==set(range(1,41))|{99}
 for name in ('expected_cvr_ballots','murkowski_final','tshibaka_final'):close(sum(float(r[name]) for r in rows),float(s[name]))
 close(sum(float(r['net_contribution']) for r in rows),float(s['net_murkowski_minus_tshibaka']))
 assert float(next(r for r in rows if r['house_district']=='99')['turnout_multiplier'])==1
result={'status':'pass','scope':'baselines_only' if '--baselines-only' in sys.argv else 'integrated_package','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_rows':1558,'independent_candidate_hd_cells':533,'independent_hd_totals':82,'state_scenarios':16,'unit_targets':656,'rcv_district_round_cells':861,'rcv_turnout_scenarios':3,'rcv_turnout_contributions':123,'cross_year_geography_join':False}
if '--baselines-only' not in sys.argv:
 priority=json.loads((ROOT/'data/turnout/priority-set.json').read_text())['districts']
 hd=[str(int(r['native_house_district'])) for r in priority]
 turnout={r['native_house_district']:r for r in read('data/county-turnout.csv')}
 inv=read('data/official-results-sources.csv');assert len(inv)==41
 assert {r['native_house_district'] for r in inv}==set(turnout)
 assert [r['native_house_district'] for r in sorted((r for r in inv if r['priority_rank']),key=lambda r:int(r['priority_rank']))]==hd
 for r in inv:
  t=turnout[r['native_house_district']]
  assert not r['county_fips'] and int(r['baseline_votes_2024'])==int(t['all_candidate_votes'])
  assert not r['november_2026_results_url']
 coverage=read('data/results-sources/unit-coverage.csv');assert len(coverage)==1568
 assert len({(r['election_id'],r['source_unit_key']) for r in coverage})==1568
 for election,n in [('24GENR',523),('22GENR',522),('26PRIM',523)]:
  rows=[r for r in coverage if r['election_id']==election];assert len(rows)==n
  assert {r['native_house_district'] for r in rows}==set(turnout)
 mapinv=read('maps/native-hd-inventory.csv');assert len(mapinv)==41
 assert {r['native_house_district'] for r in mapinv}==set(turnout)
 assert all(not r['county_fips'] and r['november2026_approval']=='unknown' for r in mapinv)
 mv=read('maps/coverage-by-vintage.csv');assert len(mv)==56
 for vintage in ('baseline-2024','current-retrieved-2026'):
  rows=sorted((r for r in mv if r['vintage']==vintage),key=lambda r:int(r['priority_rank']))
  assert [r['native_house_district'] for r in rows]==hd
  assert sum(int(r['polygon_features']) for r in rows)==256
  for r in rows:
   assert len(json.loads((ROOT/'maps'/r['geojson_path']).read_text())['features'])==int(r['polygon_features'])
 compat=read('maps/reporting-unit-compatibility.csv');assert len(compat)==1045
 for year,n in [('2024',523),('2022',522)]:
  rows=[r for r in compat if r['election_year']==year];assert len(rows)==n
  assert len({r['source_unit_key'] for r in rows})==n
  assert all(r['vote_allocation_performed']=='no' for r in rows)
 manifest=read('maps/manifest.csv');assert len(manifest)==210
 for r in manifest:
  p=ROOT/'maps'/r['local_path'];raw=p.read_bytes()
  assert len(raw)==int(r['bytes']) and hashlib.sha256(raw).hexdigest()==r['sha256'],str(p)
 result.update(official_inventory_groups=41,official_unit_coverage=1568,map_inventory_groups=41,map_unit_compatibility=1045,map_manifest_assets=210,map_district_vintages=56)
 for rel in ('turnout.md','county-partisanship.md','official-results.md','precinct-maps.md','local-news-results.md','live-polling-strategy.md','research-review.md','research-dispatch.md','README.md','maps/index.html'):assert (ROOT/rel).is_file(),rel
 links=0
 for f in ROOT.rglob('*.md'):
  for dest in re.findall(r'\]\(([^)]+)\)',f.read_text()):
   dest=dest.strip().split(' ')[0].strip('<>')
   if not dest or dest.startswith(('#','http:','https:','mailto:','data:')):continue
   assert (f.parent/unquote(dest.split('#')[0])).exists(),(str(f),dest);links+=1
 files=[f for f in ROOT.rglob('*') if f.is_file() and not any(p in ('__pycache__','.runtime') for p in f.relative_to(ROOT).parts) and f.suffix not in ('.pyc','.pyo')]
 assert all(f.stat().st_size<40*1024**2 for f in files)
 result.update(relative_links_checked=links,files_checked=len(files),all_files_under_40MiB=True)
(ROOT/'data/coordinator-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
