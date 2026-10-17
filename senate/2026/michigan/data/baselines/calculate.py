#!/usr/bin/env python3
"""Deterministic county baselines and conditional targets; stdlib only.
Run from anywhere. --county Wayne --others-share-shift-pp 0 --target-margin-pp 0
outputs the selected county tie/cushion requirement with other counties fixed.
"""
import csv,json,pathlib,collections,argparse,math,gzip
P=pathlib.Path(__file__).resolve().parent
ROOT=P.parent.parent
meta={x['file']:x for x in json.loads((P/'manifest.json').read_text())}
def read(n):return list(csv.DictReader(gzip.open(P/n,'rt') if n.endswith('.gz') else (P/n).open()))
def write(n,rows):
 with n.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
rows=[]
candidate_sums=collections.Counter()
for r in read('2024-senate-mi.csv'):
 assert r['unofficial']=='FALSE' and r['mode']=='TOTAL'
 candidate_sums[r['candidate']]+=int(r['votes'])
assert dict(candidate_sums)=={'ELISSA SLOTKIN':2712686,'MIKE ROGERS':2693680,'JOSEPH SOLIS-MULLEN':56697,'DOUGLAS P. MARSH':53978,'DAVE STEIN':41363,'DOUG DERN':18779,'VALERIE LEE WILLIS':2,'JAMES CHAPMAN':1,'MARCUS A. IRVINE':1},candidate_sums
configs=[('2024-senate-mi.csv',2024,'senate','party_simplified','county_name','county_fips'),('2024-president-mi.csv.gz',2024,'president','party_simplified','county_name','county_fips'),('2022-county.csv',2022,'governor','party','county',None),('2020-senate-mi.csv',2020,'senate','party_group','county_name','county_fips')]
fips={r['county_name'].replace('.','').upper():r['county_fips'] for r in read('2024-senate-mi.csv')}
for n,y,office,party,county,fc in configs:
 groups={}
 for r in read(n):
  if y==2022 and r['office']!='Governor':continue
  c=r[county].replace('.','').upper(); c={'GD TRAVERSE':'GRAND TRAVERSE'}.get(c,c); key=r[fc] if fc else fips[c]
  g=groups.setdefault(key,dict(county=c.title(),fips=key,year=y,contest=office,d_votes=0,r_votes=0,other_votes=0))
  typ='d_votes' if r[party] in ('DEMOCRAT','DEM') else 'r_votes' if r[party] in ('REPUBLICAN','REP') else 'other_votes'
  g[typ]+=int(r['votes'])
 assert len(groups)==83,(n,len(groups))
 major=sum(g['d_votes']+g['r_votes'] for g in groups.values()); contest=sum(sum(g[k] for k in ('d_votes','r_votes','other_votes')) for g in groups.values())
 for g in sorted(groups.values(),key=lambda x:x['fips']):
  d,r,o=(g[k] for k in ('d_votes','r_votes','other_votes'));t=d+r;s=d/t;m=(d-r)/t*100
  g.update(contest_votes=t+o,major_party_votes=t,d_two_party_share_pct=100*s,d_minus_r_two_party_margin_pp=m,d_minus_r_all_vote_margin_pp=100*(d-r)/(t+o),winner='D' if d>r else 'R' if r>d else 'tie',closeness='within 5 margin pp' if abs(m)<=5 else '5–10 margin pp' if abs(m)<=10 else 'over 10 margin pp',major_party_vote_weight_pct=100*t/major,contest_vote_weight_pct=100*(t+o)/contest,net_d_minus_r_votes=d-r,net_votes_per_plus_1pp_d_share=.02*t,source_url=meta[n]['url'],source_status='official-result secondary transcription; statewide reconciled' if y!=2020 else 'secondary precinct aggregate; DOES NOT reconcile to certified statewide counts',research_date='2026-10-17')
  rows.append(g)
write(P.parent/'county-baselines.csv',rows)
by={(r['year'],r['contest'],r['fips']):r for r in rows}
base=[r for r in rows if r['year']==2024 and r['contest']=='senate'];N=sum(r['major_party_votes'] for r in base)
scenarios=[];summaries=[]
for mix,scale in [('2024',1),('2022',1),('2022',.9),('2022',1.1)]:
 weights={r['fips']:by[(2022,'governor',r['fips'])]['major_party_votes'] if mix=='2022' else r['major_party_votes'] for r in base}
 W=sum(weights.values());turn={k:v/W*N*scale for k,v in weights.items()};T=sum(turn.values());M=sum(turn[r['fips']]*(2*r['d_two_party_share_pct']/100-1) for r in base)
 for target in [0,1]:
  delta=(target/100-M/T)/2;name=f'{mix}-mix-scale-{scale:g}-D+{target}'
  net=0
  for r in base:
   t=turn[r['fips']];s=r['d_two_party_share_pct']/100;ts=s+delta;assert 0<=ts<=1
   cn=t*(2*ts-1);net+=cn
   otherM=M-t*(2*s-1);conditional=(t+target/100*T-otherM)/(2*t)
   scenarios.append(dict(scenario=name,county=r['county'],fips=r['fips'],baseline_year=2024,baseline_contest='senate',d_votes=r['d_votes'],r_votes=r['r_votes'],baseline_d_share_pct=100*s,baseline_d_minus_r_margin_pp=200*s-100,expected_major_party_votes=t,turnout_weight_pct=100*t/T,target_d_share_pct=100*ts,target_d_minus_r_margin_pp=200*ts-100,required_d_share_change_pp=100*delta,target_net_d_minus_r_votes=cn,net_votes_per_plus_1pp_d_share=.02*t,conditional_d_share_pct_others_at_baseline=100*conditional,conditional_status='already secured' if conditional<0 else 'impossible' if conditional>1 else 'feasible'))
  assert math.isclose(net,target/100*T,abs_tol=1e-7)
  summaries.append(dict(scenario=name,major_party_votes=T,unchanged_share_net_votes=M,unchanged_share_margin_pp=100*M/T,uniform_d_share_change_pp=100*delta,target_margin_pp=target,target_net_votes=net))
write(P/'county-target-scenarios.csv',scenarios);write(P/'state-scenarios.csv',summaries)
checks=[]
expected={(2024,'senate'):(2712686,2693680,5577187),(2024,'president'):(2736533,2816636,5664186),(2022,'governor'):(2430505,1960635,4461972),(2020,'senate'):(2734568,2642233,5479720)}
for (y,o),exp in expected.items():
 rr=[r for r in rows if r['year']==y and r['contest']==o];D=sum(r['d_votes'] for r in rr);R=sum(r['r_votes'] for r in rr);O=sum(r['other_votes'] for r in rr)
 checks.append(dict(year=y,contest=o,counties=len(rr),d_votes=D,r_votes=R,other_votes=O,contest_votes=D+R+O,certified_d=exp[0],certified_r=exp[1],certified_contest=exp[2],d_difference=D-exp[0],r_difference=R-exp[1],total_difference=D+R+O-exp[2],d_winning_counties=sum(r['winner']=='D' for r in rr),two_party_d_share_pct=100*D/(D+R),two_party_d_margin_pp=100*(D-R)/(D+R)))
assert all(x['total_difference']==x['d_difference']==x['r_difference']==0 for x in checks if x['year']!=2020)
write(P/'state-checks.csv',checks)
args=argparse.ArgumentParser();args.add_argument('--county');args.add_argument('--others-share-shift-pp',type=float,default=0);args.add_argument('--target-margin-pp',type=float,default=0);a=args.parse_args()
if a.county:
 if not math.isfinite(a.others_share_shift_pp) or not math.isfinite(a.target_margin_pp):
  args.error('share shift and target margin must be finite numbers')
 if not -100<=a.target_margin_pp<=100:
  args.error('target margin must be between -100 and 100 percentage points')
 matches=[r for r in base if r['county'].casefold().replace('.','')==a.county.casefold().replace('.','')]
 if not matches:
  args.error('unknown county; use a county name from county-baselines.csv')
 c=matches[0]
 if any(not 0<=r['d_two_party_share_pct']/100+a.others_share_shift_pp/100<=1 for r in base if r!=c):
  args.error('the requested shift puts another county D share outside 0–100%')
 t=c['major_party_votes'];others=sum(r['major_party_votes']*(2*(r['d_two_party_share_pct']/100+a.others_share_shift_pp/100)-1) for r in base if r!=c);q=(t+a.target_margin_pp/100*N-others)/(2*t)
 print(json.dumps(dict(county=c['county'],required_d_share_pct=q*100,change_from_baseline_share_pp=100*q-c['d_two_party_share_pct'],status='already secured' if q<0 else 'impossible' if q>1 else 'feasible'),indent=2))
else:print(json.dumps({'state_checks':checks,'scenarios':summaries},indent=2))
