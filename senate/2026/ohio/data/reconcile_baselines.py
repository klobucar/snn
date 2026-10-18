#!/usr/bin/env python3
"""Independent pre-dispatch reconciliation of written Ohio first-wave outputs."""
from pathlib import Path
import csv,json,hashlib,datetime,gzip,io
ROOT=Path(__file__).resolve().parents[1]
def read(rel):return list(csv.DictReader((ROOT/rel).open()))
turnout=read('data/county-turnout.csv');base=read('data/county-baselines.csv')
assert len(turnout)==88 and len({r['county_fips'] for r in turnout})==88
assert all(r['county_fips'].startswith('39') and len(r['county_fips'])==5 for r in turnout)
assert turnout==sorted(turnout,key=lambda r:(-int(r['senate_2024_votes']),r['county_fips']))
comparisons=0
for comp,col,total in [('2024_senate','senate_2024_votes',5704620),('2024_president','president_2024_votes',5767788),('2022_senate','senate_2022_votes',4133342)]:
 rows={r['county_fips']:r for r in base if r['comparison']==comp};assert len(rows)==88 and set(rows)=={r['county_fips'] for r in turnout}
 for t in turnout:
  b=rows[t['county_fips']];assert b['county']==t['county']==t['county_native_id'];assert int(b['all_candidate_votes'])==int(t[col]);assert int(b['d_votes'])+int(b['r_votes'])+int(b['other_votes'])==int(t[col]);comparisons+=1
 assert sum(int(r[col]) for r in turnout)==total
state=5704620;priority=[r for r in turnout if r['in_minimum80']=='1'];assert len(priority)==32
votes=sum(int(r['senate_2024_votes']) for r in priority);previous=votes-int(priority[-1]['senate_2024_votes']);assert votes==4581738 and previous==4542798
assert 5*previous<4*state<=5*votes
assert sum(int(r['senate_2024_votes']) for r in turnout[:15])==3525320
p=json.loads((ROOT/'data/turnout/priority-set.json').read_text());bp=json.loads((ROOT/'data/baselines/priority-set.json').read_text())
assert p['ordered_county_keys_all88']==[r['county_fips'] for r in turnout]
assert p['ordered_priority_county_keys']==[r['county_fips'] for r in priority]
assert bp['counties']==[r['county'] for r in priority]
tc=read('data/turnout/county-candidate-votes.csv');bc=read('data/baselines/candidate-votes.csv')
tm={(r['election_date'][:4]+'_'+r['contest_key'],r['county_fips'],r['candidate_native_label']):r for r in tc}
bm={(r['comparison'],r['county_fips'],r['source_candidate_label']):r for r in bc if r['comparison'] in ('2024_senate','2024_president','2022_senate')}
assert len(tm)==len(tc)==len(bm)==2464 and set(tm)==set(bm)
for key,t in tm.items():assert int(t['votes'])==int(bm[key]['votes'])
for row in json.loads((ROOT/'data/baselines/turnout-worker-reconciliation.json').read_text())['stable_files']:
 assert hashlib.sha256((ROOT/'data'/row['path']).read_bytes()).hexdigest()==row['sha256']
inputs=['data/county-turnout.csv','data/county-baselines.csv','data/turnout/priority-set.json','data/baselines/priority-set.json','data/turnout/county-candidate-votes.csv','data/baselines/candidate-votes.csv']
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'county_total_comparisons':comparisons,'candidate_cell_comparisons':len(tm),'counties':88,'statewide_votes':state,'top15_votes':3525320,'priority_votes':votes,'previous_votes':previous,'priority_count':32,'ordered_priority_county_keys':p['ordered_priority_county_keys'],'input_hashes':{rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in inputs}}
out=ROOT/'data/coordinator-baseline-reconciliation.json'
if out.exists():
 old=json.loads(out.read_text())
 if {k:v for k,v in old.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=old['checked_utc']
out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('input_hashes','ordered_priority_county_keys')},indent=2))
