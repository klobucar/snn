#!/usr/bin/env python3
"""Select a county; hold every other county at stated fixed shares and volumes."""
import argparse,csv,json,pathlib
P=pathlib.Path(__file__).resolve().parent

def calculate(scenario,county_fips,others_share_shift_pp=0,target_margin_pp=0,denominator='pair'):
 rows=[r for r in csv.DictReader(open(P/'county-target-scenarios.csv')) if r['scenario']==scenario and r['target']=='tie'];selected=[r for r in rows if r['county_fips']==county_fips]
 if not rows or len(selected)!=1:raise ValueError('Unknown scenario or selected county FIPS')
 t=float(selected[0]['expected_pair_votes']);T=sum(float(r['expected_pair_votes']) for r in rows);V=sum(float(r['expected_all_candidate_votes']) for r in rows);F=T if denominator=='pair' else V;g=target_margin_pp/100;othernet=0;clipped=[]
 for r in rows:
  if r['county_fips']==county_fips:continue
  s=float(r['baseline_pair_share'])+others_share_shift_pp/100;q=min(1,max(0,s));othernet+=float(r['expected_pair_votes'])*(2*q-1)
  if s!=q:clipped.append(r['county_fips'])
 q=(t+g*F-othernet)/(2*t) if t>0 else None
 return dict(scenario=scenario,county_fips=county_fips,county_name=selected[0]['county_name'],selected_pair_votes=t,final_state_denominator=F,denominator=denominator,other_counties_net=othernet,others_share_shift_pp=others_share_shift_pp,others_clipped_fips=clipped,target_margin_pp=target_margin_pp,target_net=g*F,required_selected_pair_share=q,share_change_pp=(q-float(selected[0]['baseline_pair_share']))*100 if q is not None else None,status='no-positive-pool' if q is None else 'impossible' if q>1 else 'already-secured' if q<0 else 'feasible',scope='conditional arithmetic; countyvolume and historical preference assumptions, not a2026 forecast')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scenario',default='base-2024-senate-volume');p.add_argument('--county-fips',required=True);p.add_argument('--others-share-shift-pp',type=float,default=0);p.add_argument('--margin-pp',type=float,default=0);p.add_argument('--denominator',choices=['pair','all-candidate'],default='pair');a=p.parse_args();print(json.dumps(calculate(a.scenario,a.county_fips,a.others_share_shift_pp,a.margin_pp,a.denominator),indent=2))
