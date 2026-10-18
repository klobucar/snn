#!/usr/bin/env python3
"""Conditional arithmetic only. Counted candidate votes are immutable inputs.
CLI --input JSON --output JSON; no network, probabilities or source collector.
"""
import argparse,json,math,pathlib

def solve(counted,remaining,target_margin=0.,denominator='pair',selected=None):
 # counted={candidate:count}; pair identities must be explicitly stated in input.
 A=counted.get('A');B=counted.get('B');O=counted.get('other',0)
 if any(v is None or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in [A,B,O]):return {'status':'invalid-counted-input'}
 if denominator not in ['pair','all-candidate'] or abs(target_margin)>1:return {'status':'invalid-target'}
 for r in remaining:
  if r.get('pair_votes') is None or (denominator=='all-candidate' and r.get('other_votes') is None):return {'status':'unknown-remaining-input','counted_unchanged':counted}
  if any(not isinstance(r.get(k,0),(int,float)) or not math.isfinite(r.get(k,0)) or r.get(k,0)<0 for k in ['pair_votes']+(['other_votes'] if denominator=='all-candidate' or r.get('other_votes') is not None else [])):return {'status':'invalid-remaining-input','counted_unchanged':counted}
 U=sum(r['pair_votes'] for r in remaining);remO=sum(r.get('other_votes',0) or 0 for r in remaining);F=A+B+U+(O+remO if denominator=='all-candidate' else 0);L=A-B
 if F<=0:return {'status':'no-positive-final-denominator','required_share':None,'counted_unchanged':counted}
 target=target_margin*F
 if selected is None:pool=U;othernet=0
 else:
  match=[r for r in remaining if r['unit']==selected]
  if len(match)!=1:return {'status':'unknown-or-duplicate-selected-unit','counted_unchanged':counted}
  pool=match[0]['pair_votes'];othernet=0
  for r in remaining:
   if r['unit']==selected:continue
   q=r.get('A_share')
   if q is None:return {'status':'unknown-other-unit-share','counted_unchanged':counted}
   if not 0<=q<=1:return {'status':'invalid-other-unit-share','counted_unchanged':counted}
   othernet+=r['pair_votes']*(2*q-1)
 fixed=L+othernet
 if pool<=0:return dict(status='no-positive-pool',target_status='already-secured' if fixed>=target else 'impossible',required_share=None,fixed_net=fixed,final_denominator=F,counted_unchanged=counted)
 q=(pool+target-fixed)/(2*pool);status='impossible' if q>1 else 'already-secured' if q<0 else 'feasible'
 achieved=fixed+pool*(2*min(1,max(0,q))-1)
 return dict(status=status,required_share=q,selected=selected,pair_remaining=U,solved_pool=pool,other_units_net=othernet,counted_net=L,final_denominator=F,denominator=denominator,target_margin=target_margin,target_net=target,achieved_bounded_net=achieved,achieved_bounded_margin=achieved/F,counted_unchanged=counted)

def examples():
 counted={'A':3000000,'B':3300000,'other':100000};remaining=[{'unit':'Harris illustrative unmatched remainder','pair_votes':1000000,'other_votes':25000,'A_share':.53},{'unit':'Other253 counties illustrative remainder','pair_votes':3000000,'other_votes':75000,'A_share':.54}];out=[]
 for denominator in ['pair','all-candidate']:
  for target in [0,.01]:
   for selected in [None,remaining[0]['unit']]:out.append(dict(input=dict(counted=counted,remaining=remaining,target_margin=target,denominator=denominator,selected=selected),result=solve(counted,remaining,target,denominator,selected)))
 for U in [2000000,4000000,6000000,None,0,-1]:
  rem=[{'unit':'all-state','pair_votes':U,'other_votes':100000}];out.append(dict(input=dict(counted=counted,remaining=rem,target_margin=.01,denominator='all-candidate'),result=solve(counted,rem,.01,'all-candidate')))
 for c,rem in [({'A':100,'B':0,'other':0},[{'unit':'selected','pair_votes':10,'other_votes':0}]),({'A':0,'B':100,'other':0},[{'unit':'selected','pair_votes':10,'other_votes':0}]),({'A':0,'B':0,'other':0},[])]:out.append(dict(input=dict(counted=c,remaining=rem),result=solve(c,rem)))
 return dict(scope='SYNTHETIC fixed counted votes, not observed2026 results or a remaining-vote estimate; A=historical Democratic pair scenario,B=Republican; other stays separate',cases=out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--examples',action='store_true');a=p.parse_args();result=examples() if a.examples else solve(**json.loads(pathlib.Path(a.input).read_text()));text=json.dumps(result,indent=2)+'\n'
 if a.output:pathlib.Path(a.output).write_text(text)
 else:print(text,end='')
