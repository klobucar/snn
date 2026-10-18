#!/usr/bin/env python3
"""Conditional final-pair arithmetic, not an RCV tabulator or forecast.

Offline: python3 .../scenarios.py
Calculator: --pair gideon-collins --unit <source_row_id or native_key>
Live calculator: --remaining FILE --counted-a N --counted-b N [--unit ID]
Remaining CSV columns: source_row_id,remaining_pair_votes,a_share (fraction).
"""
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path
from build import ROOT, CONFIG, dump_csv, extract, lexical

PAIRS={
 'gideon-collins':('senate-2020','gideon','collins','D-R, same-seat historical candidates'),
 'king-kouzounas':('senate-2024','king','kouzounas','named Independent-R; King is not D'),
 'costello-kouzounas':('senate-2024','costello','kouzounas','D-R, other-seat final-pair hypothetical; King excluded'),
 'cherry-kouzounas':('senate-2024','cherry','kouzounas','named Independent-R; Cherry distinct from King'),
 'harris-trump':('president-2024','harris','trump','D-R presidential context'),
 'mills-lepage':('governor-2022','mills','lepage','D-R governor context, plurality election')}

def clamp(x):return min(1,max(0,x))

def solve_shift(shares,turnouts,target_net):
    """Monotone water-filling: same additive shift, bounded to [0,1]."""
    total=math.fsum(turnouts)
    if not -total<=target_net<=total:raise ValueError('target beyond total pair votes')
    lo,hi=-1.,1.
    for _ in range(90):
        mid=(lo+hi)/2
        net=math.fsum(t*(2*clamp(s+mid)-1) for s,t in zip(shares,turnouts))
        if net<target_net:lo=mid
        else:hi=mid
    shift=(lo+hi)/2
    return shift,[clamp(s+shift) for s in shares]

def selected_share(turnouts,shares,index,target_net=0,others_shift=0,counted_lead=0):
    total=turnouts[index]
    other=math.fsum(t*(2*clamp(s+others_shift)-1) for i,(t,s) in enumerate(zip(turnouts,shares)) if i!=index)
    if total==0:return None,'no pair votes in selected unit'
    q=(total+target_net-counted_lead-other)/(2*total)
    return q,'already secured under other-unit assumptions' if q<0 else 'impossible under other-unit assumptions' if q>1 else 'conditional feasible tie/cushion share'

def pair_arrays(universes,pair):
    source,a,b,_=PAIRS[pair];units=universes[source]
    pool=[u['votes'][a]+u['votes'][b] for u in units]
    # Zero-pair rows retain zero weight and an explicitly arbitrary .5 placeholder.
    # Any nonnative mix is allocated in proportion to pair votes, never to these rows.
    shares=[u['votes'][a]/t if t else .5 for u,t in zip(units,pool)]
    return units,pool,shares

def mix_weights(universes,pair,mix):
    units,pool,shares=pair_arrays(universes,pair);total=sum(pool)
    if mix=='native':return [t/total for t in pool],[]
    source_units=universes['governor-2022'];source_total=sum(u['contest_votes'] for u in source_units)
    if mix=='2022-section':
        observed=defaultdict(int);base=defaultdict(int)
        for u in source_units:observed[u['county_section_code']]+=u['contest_votes']
        for u,t in zip(units,pool):base[u['county_section_code']]+=t
        weights=[observed[u['county_section_code']]/source_total*t/base[u['county_section_code']] for u,t in zip(units,pool)]
        return weights,[]
    if mix!='2022-lexical':raise ValueError('unknown mix')
    observed=defaultdict(int);base=defaultdict(int)
    for u in source_units:observed[(u['native_county_code'],lexical(u['unit_name']))]+=u['contest_votes']
    for u,t in zip(units,pool):base[(u['native_county_code'],lexical(u['unit_name']))]+=t
    matched={k for k in base if k in observed and base[k]>0}
    residual_votes=source_total-sum(observed[k] for k in matched)
    unmatched_pair=sum(v for k,v in base.items() if k not in matched)
    assert unmatched_pair>0 or residual_votes==0
    weights=[];mapping=[]
    for u,t in zip(units,pool):
        k=(u['native_county_code'],lexical(u['unit_name']))
        matched_here=k in matched
        w=(observed[k]/source_total*t/base[k]) if matched_here else (residual_votes/source_total*t/unmatched_pair if unmatched_pair else 0)
        weights.append(w)
        mapping.append(dict(pair=pair,source_row_id=u['source_row_id'],native_key=u['native_key'],native_unit_name=u['native_unit_name'],lexical_key=str(k),
            match_status='county+lexical label match; geography unverified' if matched_here else 'unmatched residual volume allocated by baseline pair votes',
            observed_2022_label_votes=observed[k] if matched_here else '',allocated_weight=w,
            total_unmatched_2022_votes=residual_votes,total_unmatched_baseline_pair_votes=unmatched_pair))
    assert abs(math.fsum(weights)-1)<1e-12
    return weights,mapping

def volumes(universes,pair):
    # Researched all-candidate contest volumes. Pair participation held at the
    # baseline pair/contest ratio; no coalition is added to the pair.
    source=PAIRS[pair][0];units,pool,_=pair_arrays(universes,pair)
    fraction=sum(pool)/sum(u['contest_votes'] for u in units)
    return {'low-2022-governor':sum(u['contest_votes'] for u in universes['governor-2022'])*fraction,
            'native-observed':sum(pool),
            'high-2024-president':sum(u['contest_votes'] for u in universes['president-2024'])*fraction}

def build_scenarios(universes):
    state=[];mapping=[];preference=[];zero_pairs={}
    for pair,(source,a,b,caveat) in PAIRS.items():
        units,pool,shares=pair_arrays(universes,pair);native_total=sum(pool);native_net=sum(u['votes'][a]-u['votes'][b] for u in units)
        rows=[];zero_pairs[pair]=sum(t==0 for t in pool)
        mixes=['native','2022-section','2022-lexical'] if pair in ['gideon-collins','king-kouzounas','costello-kouzounas'] else ['native']
        for mix in mixes:
            weights,crosswalk=mix_weights(universes,pair,mix);mapping.extend(crosswalk)
            assert abs(math.fsum(weights)-1)<1e-12
            for volume,total in volumes(universes,pair).items():
                turnouts=[total*w for w in weights]
                net=math.fsum(t*(2*s-1) for t,s in zip(turnouts,shares));margin=net/total
                for target,target_fraction in [('tie',0.),('a-plus-1-margin-pp',.01)]:
                    target_net=target_fraction*total;unbounded=(target_fraction-margin)/2
                    bounded,targets=solve_shift(shares,turnouts,target_net)
                    bad=sum(not 0<=s+unbounded<=1 for s,t in zip(shares,turnouts) if t>0)
                    actual_net=math.fsum(t*(2*q-1) for t,q in zip(turnouts,targets))
                    assert abs(actual_net-target_net)<1e-7
                    state.append(dict(pair=pair,source_id=source,candidate_a=a,candidate_b=b,caveat=caveat,mix=mix,volume=volume,target=target,
                        expected_pair_votes=total,fixed_preference_net=net,fixed_preference_margin_pp=100*margin,
                        unbounded_uniform_a_share_shift_pp=100*unbounded,unbounded_out_of_range_units=bad,
                        bounded_common_shift_pp=100*bounded,target_net=target_net,target_sum_net=actual_net,
                        weight_sum=math.fsum(weights),tie_plus_one_expected_net_vote_a_share_pp=.5/total*100,
                        native_observed_a_share_pct=100*(native_total+native_net)/(2*native_total)))
                    for i,(u,t,s,q,w) in enumerate(zip(units,turnouts,shares,targets,weights)):
                        selected,status=selected_share(turnouts,shares,i,target_net)
                        rows.append(dict(pair=pair,candidate_a=a,candidate_b=b,source_row_id=u['source_row_id'],native_key=u['native_key'],
                            native_county_code=u['native_county_code'],county_section_code=u['county_section_code'],native_unit_name=u['native_unit_name'],
                            source_id=source,mix=mix,volume=volume,target=target,baseline_a_votes=u['votes'][a],baseline_b_votes=u['votes'][b],
                            baseline_pair_share=s if pool[i] else '',expected_pair_votes=t,turnout_weight=w,
                            baseline_net_contribution=t*(2*s-1),unbounded_target_share=s+unbounded if pool[i] else '',
                            unbounded_uniform_feasible=int(bad==0),bounded_target_share=q if pool[i] else '',
                            actual_share_shift_pp=100*(q-s) if pool[i] else '',target_margin_pp=100*(2*q-1) if pool[i] else '',
                            target_net_contribution=t*(2*q-1),net_per_plus_1pp_a_share=.02*t,
                            selected_unit_required_share=selected if selected is not None else '',selected_unit_status=status))
        dump_csv(ROOT/(pair+'-unit-targets.csv'),rows)
    # Preference anchors are observed D-R outcomes from distinct named contests.
    # Recenter the 2020 native shape to each statewide share using bounded shifts.
    pref_anchors=[]
    for label,pair in [('low-same-seat-2020','gideon-collins'),('base-president-2024','harris-trump'),('high-governor-2022','mills-lepage')]:
        u,p,s=pair_arrays(universes,pair);a=PAIRS[pair][1]
        pref_anchors.append((label,pair,sum(x['votes'][a] for x in u)/sum(p)))
    units,pool,shares=pair_arrays(universes,'gideon-collins')
    for mix in ['native','2022-section','2022-lexical']:
        weights,_=mix_weights(universes,'gideon-collins',mix)
        for volume,total in volumes(universes,'gideon-collins').items():
            turnouts=[total*w for w in weights]
            for label,anchor_pair,pref in pref_anchors:
                delta,targets=solve_shift(shares,turnouts,(2*pref-1)*total)
                net=math.fsum(t*(2*q-1) for t,q in zip(turnouts,targets))
                preference.append(dict(native_template='2020 Gideon-Collins',mix=mix,volume=volume,preference_anchor=label,anchor_pair=anchor_pair,
                    anchor_a_share_pct=100*pref,expected_pair_votes=total,bounded_shift_to_anchor_pp=100*delta,
                    net_at_anchor=net,margin_at_anchor_pp=100*net/total,tie_additional_aggregate_share_pp=100*(.5-pref),
                    note='different-contest historical anchor; not a 2026 estimate; lower preferences absent'))
    dump_csv(ROOT/'state-scenarios.csv',state)
    dump_csv(ROOT/'mix-label-crosswalk.csv',mapping)
    dump_csv(ROOT/'preference-sensitivity.csv',preference)
    (ROOT/'scenario-settings.json').write_text(json.dumps(dict(pair_definitions=PAIRS,
        turnout_low_observed_contest_votes=676819,
        native_base_by_pair={pair:dict(source_id=spec[0],observed_contest_votes=sum(u['contest_votes'] for u in universes[spec[0]]),observed_pair_votes=sum(u['votes'][spec[1]]+u['votes'][spec[2]] for u in universes[spec[0]])) for pair,spec in PAIRS.items()},
        turnout_high_observed_contest_votes=831375,
        volume_rule='pair total = all-candidate volume anchor * baseline pair/contest participation ratio; native-observed keeps actual pair total',
        midterm_mix='section = observed governor county-block shares, baseline within-block pair distribution fixed; lexical = observed label weights with residual imputation',
        zero_pair_rows=zero_pairs,preference_anchors=pref_anchors),indent=2)+'\n')
    return state

def rcv_examples(universes):
    examples=[];allocations=[]
    for pair,minor_candidates in [('gideon-collins',['linn','savage','others']),('king-kouzounas',['costello','cherry']),('costello-kouzounas',['king','cherry'])]:
        source,a,b,_=PAIRS[pair];units=universes[source]
        totals={cid:sum(u['votes'][cid] for u in units) for cid in units[0]['votes']}
        blank=sum(u['blank'] for u in units);tbc=sum(u['tbc'] for u in units)
        for scenario,fa,fb in [('all-eliminated-exhaust',0,0),('all-eliminated-to-a',1,0),('all-eliminated-to-b',0,1),('illustrative-60-30-10',.6,.3)]:
            afinal=float(totals[a]);bfinal=float(totals[b]);exhaust=float(blank)
            for cid in minor_candidates:
                votes=totals[cid];ta=fa*votes;tb=fb*votes;ex=(1-fa-fb)*votes
                afinal+=ta;bfinal+=tb;exhaust+=ex
                allocations.append(dict(pair=pair,scenario=scenario,eliminated_candidate=cid,original_votes=votes,to_a=ta,to_b=tb,exhausted=ex))
            assert abs(afinal+bfinal+exhaust-tbc)<1e-7
            examples.append(dict(pair=pair,scenario=scenario,candidate_a=a,candidate_b=b,initial_a=totals[a],initial_b=totals[b],final_a=afinal,final_b=bfinal,
                final_continuing=afinal+bfinal,exhausted_including_blank=exhaust,ballots_control=tbc,net_a_minus_b=afinal-bfinal,
                final_a_share_pct=100*afinal/(afinal+bfinal),
                conditional_status='unreachable from unchanged historical first choices: majority winner stops before transfers',
                assumptions='named pair survives; all other named candidates removed; published Others treated as pool; BLANK exhausted; no promoted lower choice from blank; transfer fractions assumed, not observed'))
    # Explicit coalition, candidate identities remain separate inputs.
    u=universes['senate-2024'];sums={cid:sum(x['votes'][cid] for x in u) for cid in u[0]['votes']}
    coalition=dict(scenario='explicit King+Costello coalition versus Kouzounas; Cherry exhausts',king_ind=sums['king'],costello_d=sums['costello'],
        cherry_ind_exhausted=sums['cherry'],kouzounas_r=sums['kouzounas'],coalition_votes=sums['king']+sums['costello'],
        net_coalition_minus_r=sums['king']+sums['costello']-sums['kouzounas'],
        caveat='bookkeeping only, not D votes, not observed transfers, not a resolved 2026 ballot scenario')
    dump_csv(ROOT/'conditional-rcv-examples.csv',examples)
    dump_csv(ROOT/'conditional-transfer-allocations.csv',allocations)
    (ROOT/'explicit-coalition-example.json').write_text(json.dumps(coalition,indent=2)+'\n')

def calculator(args,universes):
    if args.remaining:
        if args.counted_a is None or args.counted_b is None:raise ValueError('live calculation requires both counted totals')
        raw=list(csv.DictReader(Path(args.remaining).open()))
        ids=[x['source_row_id'] for x in raw];assert len(set(ids))==len(ids)
        turns=[float(x['remaining_pair_votes']) for x in raw];shares=[float(x['a_share']) for x in raw]
        assert all(t>=0 for t in turns) and all(0<=s<=1 for s in shares)
        total=math.fsum(turns);lead=args.counted_a-args.counted_b
        target=args.target_net_votes if args.target_net_votes is not None else args.target_margin_pp/100*(total+args.counted_a+args.counted_b)
        result=dict(mode='remaining only; counted totals fixed',counted_a=args.counted_a,counted_b=args.counted_b,counted_lead=lead,remaining_pair_votes=total,target_final_net=target)
        if args.unit:
            i=ids.index(args.unit);q,status=selected_share(turns,shares,i,target,args.others_share_shift_pp/100,lead)
        else:
            q=(total+target-lead)/(2*total) if total else None
            status='no remaining pair votes' if q is None else 'already secured' if q<0 else 'impossible' if q>1 else 'conditional feasible'
        result.update(required_a_share=q,status=status,projected_net_at_input_shares=lead+math.fsum(t*(2*s-1) for t,s in zip(turns,shares)))
        return result
    units,pool,shares=pair_arrays(universes,args.pair);weights,_=mix_weights(universes,args.pair,args.mix)
    total=volumes(universes,args.pair)[args.volume];turns=[total*w for w in weights]
    found=[i for i,u in enumerate(units) if args.unit in [u['source_row_id'],u['native_key'],u['unit_name']]]
    if len(found)!=1:raise ValueError('unit must match exactly one source row; use source_row_id for duplicate labels')
    i=found[0];target=args.target_net_votes if args.target_net_votes is not None else args.target_margin_pp/100*total
    q,status=selected_share(turns,shares,i,target,args.others_share_shift_pp/100)
    return dict(pair=args.pair,mix=args.mix,volume=args.volume,source_row_id=units[i]['source_row_id'],native_key=units[i]['native_key'],
        expected_state_pair_votes=total,selected_pair_votes=turns[i],baseline_a_share=shares[i],others_a_share_shift_pp=args.others_share_shift_pp,
        target_state_net=target,required_a_share=q,status=status,
        other_units_clipped_to_share_bounds=sum(not 0<=s+args.others_share_shift_pp/100<=1 for j,s in enumerate(shares) if j!=i and turns[j]>0),
        conditional_on='fixed other-unit preferences and chosen pair participation; no lower preferences inferred')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pair',choices=PAIRS,default='gideon-collins');p.add_argument('--unit')
    p.add_argument('--mix',choices=['native','2022-section','2022-lexical'],default='native')
    p.add_argument('--volume',choices=['native-observed','low-2022-governor','high-2024-president'],default='native-observed')
    p.add_argument('--others-share-shift-pp',type=float,default=0);p.add_argument('--target-margin-pp',type=float,default=0)
    p.add_argument('--target-net-votes',type=float);p.add_argument('--remaining');p.add_argument('--counted-a',type=int);p.add_argument('--counted-b',type=int)
    args=p.parse_args();data=extract()
    if args.unit or args.remaining:print(json.dumps(calculator(args,data),indent=2))
    else:
        states=build_scenarios(data);rcv_examples(data)
        print('Built',len(states),'state scenarios and all-native-unit target tables; target sums PASS')
