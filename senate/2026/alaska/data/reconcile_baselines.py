#!/usr/bin/env python3
"""Independent same-election candidate/HD cross-assignment reconciliation."""
from pathlib import Path
import csv,json,hashlib,datetime,io
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'data/county-baselines.csv';raw=p.read_bytes();baseline=list(csv.DictReader(io.StringIO(raw.decode())))
def read(rel):return list(csv.DictReader((ROOT/rel).open()))
maps={
'2024':{'Harris/Walz':'harris_walz','Kennedy/Shanahan':'kennedy_shanahan','Oliver/Maat':'oliver_maat','Sonski/Onak':'sonski_onak','Stein/Ware':'stein_ware','Terry/Broden':'terry_broden','Trump/Vance':'trump_vance','West/Abdullah':'west_abdullah'},
'2022':{'Chesbro, Patricia R.':'chesbro','Kelley, Buzz A.':'kelley','Murkowski, Lisa':'murkowski','Tshibaka, Kelly C.':'tshibaka','Write-in':'write_in'}}
checks=0;totals=0
for year,path in [('2024','data/county-turnout.csv'),('2022','data/turnout/district-turnout-2022.csv')]:
 rr=read(path);assert len(rr)==41 and {int(r['native_house_district']) for r in rr}==set(range(1,41))|{99}
 br=[r for r in baseline if r['election_year']==year and r['stage']=='first_choices']
 assert len(br)==41*len(maps[year]),(year,len(br))
 bm={(int(r['source_unit_id']),r['candidate']):r for r in br};assert len(bm)==len(br)
 for r in rr:
  hd=int(r['native_house_district']);candidate_sum=0
  for candidate,col in maps[year].items():
   x=bm[(hd,candidate)];assert int(x['votes'])==int(r[col]),(year,hd,candidate)
   assert int(x['candidate_vote_denominator'])==int(r['all_candidate_votes'])
   candidate_sum+=int(x['votes']);checks+=1
  assert candidate_sum==int(r['all_candidate_votes']);totals+=1
assert checks==533 and totals==82
turnout=read('data/county-turnout.csv');ranked=sorted(turnout,key=lambda r:(-int(r['all_candidate_votes']),r['district_key']));assert turnout==ranked
state=sum(int(r['all_candidate_votes']) for r in ranked);assert state==338177
priority=[r for r in ranked if r['smallest_80pct_set']=='1'];assert len(priority)==28
votes=sum(int(r['all_candidate_votes']) for r in priority);assert votes==271492 and votes-int(priority[-1]['all_candidate_votes'])==263774
assert 5*(votes-int(priority[-1]['all_candidate_votes']))<4*state<=5*votes
assert sum(int(r['all_candidate_votes']) for r in ranked[:15])==156277
keys=json.loads((ROOT/'data/turnout/priority-set.json').read_text());assert [r['district_key'] for r in priority]==[r['district_key'] for r in keys['districts']]
assert p.read_bytes()==raw,'Baseline changed during independent read; rerun against stable snapshot.'
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'same_election_candidate_hd_cells':checks,'same_election_hd_totals':totals,'baseline_sha256':hashlib.sha256(raw).hexdigest(),'statewide_votes':state,'priority_votes':votes,'priority_count':28,'priority_districts':[r['native_house_district'] for r in priority],'cross_year_geography_join':False}
output=ROOT/'data/coordinator-baseline-reconciliation.json'
# Keep the observation timestamp when the checked substantive result is unchanged.
# Other assignments pin this evidence file by hash.
if output.exists():
 previous=json.loads(output.read_text())
 if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:
  result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
