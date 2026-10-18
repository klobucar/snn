#!/usr/bin/env python3
"""Independent coordinator checks of all-unit conditional arithmetic; no forecast."""
from pathlib import Path
from collections import defaultdict
import csv, datetime, json, math

ROOT=Path(__file__).resolve().parents[1]
def rows(rel):
    with (ROOT/rel).open(newline='') as f:return list(csv.DictReader(f))
def close(a,b,tol=1e-6):
    assert math.isfinite(float(a)) and abs(float(a)-float(b))<=tol,(a,b)
base=rows('data/county-baselines.csv');by={r['source_row_id']:r for r in base}
sources=defaultdict(list)
for r in base:sources[r['source_id']].append(r)
settings=json.loads((ROOT/'data/baselines/scenario-settings.json').read_text())
states=rows('data/baselines/state-scenarios.csv')
seen=set();checked=0;native=0;section=0;lexical=0
govshares=defaultdict(int)
for r in sources['governor-2022']:govshares[r['county_section_code']]+=int(r['contest_votes'])
govtotal=sum(govshares.values());assert govtotal==676819
for pair,(source,a,b,caveat) in settings['pair_definitions'].items():
    unitrows=rows(f'data/baselines/{pair}-unit-targets.csv');groups=defaultdict(list)
    for r in unitrows:groups[(r['mix'],r['volume'],r['target'])].append(r)
    assert set(groups)=={(r['mix'],r['volume'],r['target']) for r in states if r['pair']==pair}
    pool=sum(int(r[a+'_votes'])+int(r[b+'_votes']) for r in sources[source])
    contest=sum(int(r['contest_votes']) for r in sources[source])
    declared=settings['native_base_by_pair'][pair]
    assert declared=={'source_id':source,'observed_contest_votes':contest,'observed_pair_votes':pool}
    assert 'turnout_base_2024_senate_contest_votes' not in settings
    bysection=defaultdict(int)
    for r in sources[source]:bysection[r['county_section_code']]+=int(r[a+'_votes'])+int(r[b+'_votes'])
    for st in [s for s in states if s['pair']==pair]:
        key=(st['mix'],st['volume'],st['target']);sr=groups[key]
        assert len(sr)==len(sources[source]) and {r['source_row_id'] for r in sr}=={r['source_row_id'] for r in sources[source]}
        assert (pair,)+key not in seen;seen.add((pair,)+key)
        expected=pool if st['volume']=='native-observed' else {'low-2022-governor':676819,'high-2024-president':831375}[st['volume']]*pool/contest
        close(st['expected_pair_votes'],expected)
        target=0 if st['target']=='tie' else .01*expected
        close(st['target_net'],target)
        net=0;weight=0;targetnet=0;bad=0
        shift=float(st['unbounded_uniform_a_share_shift_pp'])/100
        bounded=float(st['bounded_common_shift_pp'])/100
        for r in sr:
            original=by[r['source_row_id']];av=int(original[a+'_votes']);bv=int(original[b+'_votes']);p=av/(av+bv) if av+bv else .5
            w=float(r['turnout_weight']);t=float(r['expected_pair_votes'])
            assert r['native_key']==original['native_key'] and r['native_unit_name']==original['native_unit_name']
            assert int(r['baseline_a_votes'])==av and int(r['baseline_b_votes'])==bv and w>=0
            if st['mix']=='native':close(w,(av+bv)/pool,1e-12);native+=1
            elif st['mix']=='2022-section':close(w,govshares[original['county_section_code']]/govtotal*(av+bv)/bysection[original['county_section_code']],1e-12);section+=1
            else:
                assert st['mix']=='2022-lexical';lexical+=1
                # Lexical matches/imputed residuals are research assumptions; here only the published weights/arithmetic are checked.
            close(t,expected*w);close(r['baseline_net_contribution'],t*(2*p-1));net+=t*(2*p-1);weight+=w
            q=min(1,max(0,p+bounded));targetnet+=t*(2*q-1)
            close(r['target_net_contribution'],t*(2*q-1));close(r['net_per_plus_1pp_a_share'],.02*t)
            if av+bv:
                close(r['baseline_pair_share'],p,1e-12);close(r['unbounded_target_share'],p+shift,1e-12)
                close(r['bounded_target_share'],q,1e-12);close(r['actual_share_shift_pp'],100*(q-p),1e-9);close(r['target_margin_pp'],100*(2*q-1),1e-9)
            else:
                assert t==0 and not r['baseline_pair_share'] and not r['bounded_target_share']
            bad+=int(t>0 and not 0<=p+shift<=1);checked+=1
        close(weight,1,1e-12);close(net,st['fixed_preference_net']);close(st['fixed_preference_margin_pp'],100*net/expected)
        close(shift,(target-net)/(2*expected),1e-12);close(targetnet,target,1e-6)
        close(st['target_sum_net'],targetnet);assert int(st['unbounded_out_of_range_units'])==bad
        close(st['tie_plus_one_expected_net_vote_a_share_pp'],50/expected,1e-12)
        for r in sr:
            assert int(r['unbounded_uniform_feasible'])==int(bad==0)
            t=float(r['expected_pair_votes']);other=net-float(r['baseline_net_contribution'])
            if t:
                need=(target-other+t)/(2*t);close(r['selected_unit_required_share'],need,1e-8)
                status='already secured under other-unit assumptions' if need<0 else 'impossible under other-unit assumptions' if need>1 else 'conditional feasible tie/cushion share'
                assert r['selected_unit_status']==status
            else:assert not r['selected_unit_required_share'] and r['selected_unit_status']=='no pair votes in selected unit'
    assert len(unitrows)==sum(len(v) for v in groups.values())
assert len(seen)==len(states)
preference=rows('data/baselines/preference-sensitivity.csv');assert len(preference)==27
gideon=rows('data/baselines/gideon-collins-unit-targets.csv');template=defaultdict(list)
for r in gideon:
    if r['target']=='tie':template[(r['mix'],r['volume'])].append(r)
for r in preference:
    source,a,b,_=settings['pair_definitions'][r['anchor_pair']]
    av=sum(int(u[a+'_votes']) for u in sources[source]);bv=sum(int(u[b+'_votes']) for u in sources[source]);p=av/(av+bv)
    close(r['anchor_a_share_pct'],100*p);close(r['tie_additional_aggregate_share_pp'],100*(.5-p))
    net=0;total=0;delta=float(r['bounded_shift_to_anchor_pp'])/100
    for u in template[(r['mix'],r['volume'])]:
        t=float(u['expected_pair_votes']);base_share=float(u['baseline_pair_share']) if u['baseline_pair_share'] else .5
        net+=t*(2*min(1,max(0,base_share+delta))-1);total+=t
    close(total,r['expected_pair_votes']);close(net,r['net_at_anchor']);close(net,(2*p-1)*total);close(r['margin_at_anchor_pp'],100*net/total)
transfers=rows('data/baselines/conditional-transfer-allocations.csv');tg=defaultdict(list)
for r in transfers:
    close(float(r['to_a'])+float(r['to_b'])+float(r['exhausted']),r['original_votes']);tg[(r['pair'],r['scenario'])].append(r)
examples=rows('data/baselines/conditional-rcv-examples.csv')
for r in examples:
    t=tg[(r['pair'],r['scenario'])];source,a,b,_=settings['pair_definitions'][r['pair']]
    blank=sum(int(u['blank']) for u in sources[source]);ballots=sum(int(u['tbc']) for u in sources[source])
    close(r['final_a'],float(r['initial_a'])+sum(float(x['to_a']) for x in t));close(r['final_b'],float(r['initial_b'])+sum(float(x['to_b']) for x in t))
    close(r['exhausted_including_blank'],blank+sum(float(x['exhausted']) for x in t));close(float(r['final_a'])+float(r['final_b'])+float(r['exhausted_including_blank']),ballots)
    assert 'unreachable' in r['conditional_status']
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state_scenarios':len(states),'native_unit_target_rows':checked,
        'independently_recomputed_native_weights':native,'independently_recomputed_section_weights':section,
        'lexical_rows_arithmetic_checked_using_reported_weights':lexical,'conditional_transfer_rows':len(transfers),'conditional_rcv_examples':len(examples),
        'preference_anchor_scenarios':len(preference),'declared_native_base_settings_match_sources':True,
        'scope':'Exact baseline counts, source-native row identity, complete all-unit contribution/target/selected-unit arithmetic. Lexical cross-year matches/residual imputation and synthetic transfers are assumptions, not validated geography or observed preferences. No calibration established.'}
output=ROOT/'data/coordinator-target-checks.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
