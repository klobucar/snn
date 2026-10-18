#!/usr/bin/env python3
"""Recompute county scenarios from primary baselines, independent of target builder."""
from pathlib import Path
from collections import defaultdict
import csv,datetime,hashlib,json,math
ROOT=Path(__file__).resolve().parent
def rows(rel):
    with (ROOT/rel).open() as f:return list(csv.DictReader(f))
def near(a,b):assert math.isclose(float(a),float(b),rel_tol=2e-12,abs_tol=2e-6),(a,b)
baseline={(r['contest'],r['county_fips']):r for r in rows('county-baselines.csv')}
states=rows('baselines/state-target-scenarios.csv');targets=rows('baselines/county-target-scenarios.csv')
groups=defaultdict(list)
for r in targets:groups[(r['scenario'],r['target'])].append(r)
assert len(states)==len(groups)==21 and len(targets)==5334
selected_checks=0
for state in states:
    key=(state['scenario'],state['target']);county=groups[key]
    assert len(county)==254 and len({r['county_fips'] for r in county})==254
    pref=state['preference_baseline'];volume=state['volume_basis'];inputs={}
    for row in county:
        fips=row['county_fips'];p=baseline[(pref,fips)];v=baseline[(volume,fips)]
        d,r=int(p['d']),int(p['r']);observed_pair=d+r;observed_all=int(p['candidate_votes'])
        assert observed_pair>0 and observed_all>0
        allvotes=int(v['candidate_votes']);participation=observed_pair/observed_all
        pair=allvotes*participation;share=d/observed_pair;net=pair*(2*share-1)
        inputs[fips]=(allvotes,pair,share,net)
        assert row['preference_baseline'].split()[0]==pref and row['volume_basis'].split()[0]==volume
        near(row['d'],d);near(row['r'],r);near(row['baseline_pair_share'],share)
        near(row['expected_all_candidate_votes'],allvotes);near(row['expected_pair_votes'],pair)
        near(row['pair_participation'],participation);near(row['baseline_net'],net)
        near(row['one_pp_share_net_gain'],.02*pair)
    all_total=sum(x[0] for x in inputs.values());pair_total=sum(x[1] for x in inputs.values());net_total=sum(x[3] for x in inputs.values())
    desired={'tie':0,'A+1-pair-margin':.01*pair_total,'A+1-all-candidate-margin':.01*all_total}[state['target']]
    shift=(desired-net_total)/(2*pair_total)
    near(state['all_candidate_votes'],all_total);near(state['pair_votes'],pair_total)
    near(state['pair_participation'],pair_total/all_total);near(state['baseline_net'],net_total)
    near(state['baseline_pair_margin'],net_total/pair_total);near(state['baseline_all_candidate_margin'],net_total/all_total)
    near(state['target_net'],desired);near(state['target_pair_margin'],desired/pair_total);near(state['target_all_candidate_margin'],desired/all_total)
    near(state['unbounded_shift_share_pp'],100*shift)
    def net_at(delta):return sum(pair*(2*min(1,max(0,share+delta))-1) for allvotes,pair,share,net in inputs.values())
    lo,hi=-1.,1.
    for _ in range(90):
        mid=(lo+hi)/2
        if net_at(mid)<desired:lo=mid
        else:hi=mid
    bounded=(lo+hi)/2;near(state['bounded_shift_share_pp'],100*bounded)
    achieved=0;gains=0
    for row in county:
        allvotes,pair,share,net=inputs[row['county_fips']]
        target_share=min(1,max(0,share+bounded));target_net=pair*(2*target_share-1)
        near(row['pair_weight'],pair/pair_total)
        near(row['unbounded_shift_share_pp'],100*shift);near(row['unbounded_target_share'],share+shift)
        near(row['bounded_shift_share_pp'],100*bounded);near(row['bounded_target_share'],target_share)
        near(row['bounded_target_net'],target_net);near(row['net_gain'],target_net-net)
        near(row['target_margin_on_pair'],desired/pair_total);near(row['target_margin_on_all_candidates'],desired/all_total)
        selected=(1+(desired-(net_total-net))/pair)/2
        near(row['selected_only_required_share'],selected)
        if 0<=selected<=1:assert row['selected_only_status']=='feasible'
        else:assert row['selected_only_status']!='feasible'
        selected_checks+=1;achieved+=target_net;gains+=target_net-net
    near(achieved,desired);near(gains,desired-net_total)
    near(state['bounded_achieved_net'],achieved)
    near(sum(float(r['pair_weight']) for r in county),1)
base=next(r for r in states if r['scenario']=='base-2024-senate-volume' and r['target']=='tie')
assert int(float(base['pair_votes']))==11021990
near(base['baseline_net'],-959492);near(base['unbounded_shift_share_pp'],959492/(2*11021990)*100)
fixtures=json.loads((ROOT/'baselines/live-examples.json').read_text())['cases']
assert len(fixtures)==17
live_statuses=defaultdict(int)
for case in fixtures:
    source=case['input'];result=case['result'];counted=source['counted'];remaining=source['remaining']
    assert result['counted_unchanged']==counted
    live_statuses[result['status']]+=1
    if any(r['pair_votes'] is None for r in remaining):
        assert result['status']=='unknown-remaining-input';continue
    if any(r['pair_votes']<0 for r in remaining):
        assert result['status']=='invalid-remaining-input';continue
    pair_remaining=sum(r['pair_votes'] for r in remaining)
    final_denominator=counted['A']+counted['B']+pair_remaining
    if source.get('denominator','pair')=='all-candidate':
        final_denominator+=counted['other']+sum(r['other_votes'] for r in remaining)
    if final_denominator==0:
        assert result['status']=='no-positive-final-denominator' and result['required_share'] is None;continue
    near(result['final_denominator'],final_denominator)
    desired=source.get('target_margin',0)*final_denominator
    selected=source.get('selected')
    solved=[r for r in remaining if selected is None or r['unit']==selected]
    fixed=counted['A']-counted['B']+sum(r['pair_votes']*(2*r['A_share']-1) for r in remaining if r not in solved)
    pool=sum(r['pair_votes'] for r in solved)
    if pool==0:
        assert result['status']=='no-positive-pool' and result['required_share'] is None
        assert result['target_status']==('already-secured' if fixed>=desired else 'impossible');continue
    # Solve A-B target using final pair-pool conservation, independent of fixture generator.
    required_a=(desired-fixed+pool)/2
    near(result['required_share'],required_a/pool)
    near(result['target_net'],desired)
    near(result['counted_net'],counted['A']-counted['B'])
    achieved=fixed+2*min(pool,max(0,required_a))-pool
    near(result['achieved_bounded_net'],achieved)
    near(result['achieved_bounded_margin'],achieved/final_denominator)
    assert result['status']==('already-secured' if required_a<0 else 'impossible' if required_a>pool else 'feasible')
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state_scenarios':len(states),
        'county_target_rows':len(targets),'selected_county_requirements':selected_checks,'counties_per_scenario':254,
        'preference_volume_mixes':7,'synthetic_fixed_counted_remainder_cases':len(fixtures),'remainder_statuses':dict(live_statuses),'base_pair_votes':11021990,'base_D_minus_R':-959492,
        'base_tie_D_share_pp':959492/(2*11021990)*100,'base_D_plus1_pair_share_pp':959492/(2*11021990)*100+.5,
        'input_hashes':{rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in ('county-baselines.csv','baselines/state-target-scenarios.csv','baselines/county-target-scenarios.csv','baselines/live-examples.json')},
        'scope':'Historical county preference/volume weights, clipped common shifts and selected-county arithmetic independently recomputed. Other candidates/pair denominators retained; no current candidate roster, 2026 turnout forecast or calibrated probability inferred.'}
output=ROOT/'coordinator-target-checks.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='input_hashes'},indent=2))
