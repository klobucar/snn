#!/usr/bin/env python3
"""Conditional deterministic scenarios. No 2026 turnout estimation or collection."""
import collections, json, math
from common import *

def finite(v):return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
def bounded_uniform(shares,weights,target):
    if not shares or len(shares)!=len(weights) or not finite(target) or any(not finite(x) or not 0<=x<=1 for x in shares) or any(not finite(t) or t<0 for t in weights):return {'status':'unavailable'}
    total=sum(weights)
    if total<=0:return {'status':'no-positive-pool','feasible':False}
    if abs(target)>total+1e-8:return {'status':'impossible','feasible':False}
    base=sum(t*(2*s-1) for t,s in zip(weights,shares));unbounded=(target-base)/(2*total)
    lo=-1.;hi=1.
    for _ in range(100):
        mid=(lo+hi)/2;lead=sum(t*(2*min(1,max(0,s+mid))-1) for t,s in zip(weights,shares))
        if lead<target:lo=mid
        else:hi=mid
    shift=(lo+hi)/2;targets=[min(1,max(0,s+shift)) for s in shares]
    clips=sum(s+unbounded<0 or s+unbounded>1 for s in shares)
    return {'status':'bounded-feasible' if clips else 'unbounded-feasible','feasible':True,'unbounded_share_shift':unbounded,'solved_share_shift':shift,'unbounded_clipped_count':clips,'baseline_net':base,'baseline_meets_target':base>=target,'target_shares':targets}

def conditional(counted_d,counted_r,counted_other,remainder,selected='ALL',margin=0.,denominator='pair'):
    """Counted candidates fixed. Remainder rows: key, pair_votes, other_votes, d_share.
    selected=ALL solves aggregate remaining pair share; otherwise other rows fixed.
    Fractions are expectations, not rounded ballots; one net vote must be specified
    separately to turn an exact tie into an integer plurality.
    """
    if not isinstance(remainder,list) or any(not finite(x) or x<0 for x in [counted_d,counted_r,counted_other]) or not finite(margin) or not -1<=margin<=1 or denominator not in ['pair','all-candidate']:return {'status':'unavailable'}
    keys=[]
    for r in remainder:
        if not isinstance(r,dict) or any(k not in r for k in ['key','pair_votes','other_votes','d_share']):return {'status':'unavailable'}
        if not isinstance(r['key'],str) or not r['key'] or any(not finite(r[k]) or r[k]<0 for k in ['pair_votes','other_votes']) or not finite(r['d_share']) or not 0<=r['d_share']<=1:return {'status':'unavailable'}
        keys.append(r['key'])
    if len(keys)!=len(set(keys)) or (selected!='ALL' and selected not in keys):return {'status':'unavailable'}
    final_pair=counted_d+counted_r+sum(r['pair_votes'] for r in remainder)
    final_all=final_pair+counted_other+sum(r['other_votes'] for r in remainder)
    den=final_pair if denominator=='pair' else final_all
    if den<=0:return {'status':'no-positive-denominator'}
    target=margin*den;pool=sum(r['pair_votes'] for r in remainder if selected=='ALL' or r['key']==selected)
    fixed=counted_d-counted_r+sum(r['pair_votes']*(2*r['d_share']-1) for r in remainder if selected!='ALL' and r['key']!=selected)
    result={'selected':selected,'denominator_scope':denominator,'final_pair_votes':final_pair,'final_all_candidate_votes':final_all,'final_denominator':den,'target_net':target,'fixed_net':fixed,'selected_pair_pool':pool}
    if pool<=0:return result|{'status':'no-positive-pool','meets_target':fixed>=target,'required_d_share':None}
    q=(target-fixed+pool)/(2*pool)
    return result|{'required_d_share':q,'bounded_display_share':min(1,max(0,q)),'status':'already-secured' if q<0 else 'impossible' if q>1 else 'feasible','achieved_net_at_boundary':fixed+pool*(2*min(1,max(0,q))-1)}

def build():
    county=records('county-contests.csv');contests={c:{r['county_fips']:r for r in county if r['contest']==c} for c in SPECS};fips=sorted(next(iter(contests.values())))
    candidates={(r['contest'],r['county_fips'],int(r['source_column'])):int(r['votes']) for r in records('canvass-candidate-method.csv') if r['native_method']=='Total'}
    ranks={r['county_fips']:r for r in records('priority-order.csv')};turn={(r['year'],r['county_fips']):r for r in records('turnout-report.csv')}
    wide=[]
    for f in fips:
        row={'county':contests['2024-president'][f]['county'],'county_fips':f,'native_county_label':contests['2024-president'][f]['county'],'native_county_numeric_id':'','rank_2024':ranks[f]['rank'],'priority80':ranks[f]['priority80']}
        for c,rs in contests.items():
            for k,v in rs[f].items():
                if k not in ['county','county_fips','year','contest']:row[c.replace('-','_')+'_'+k]=v
            y=str(SPECS[c]['year']);t=turn[(y,f)]
            for k in ['election_day_voters','absentee_voters','total_voters','active_registered','inactive_registered','registration_as_of','published_active_turnout_pct','published_total_turnout_pct']:row[f'turnout_{y}_'+k]=t[k]
        wide.append(row)
    csvout('../county-baselines.csv',wide)
    state=[];targets=[];selected=[];settings=[];other_rows=[]
    mixes={'low-historical-2022':'2022-senate','base-historical-2024':'2024-president','high-historical-2020':'2020-senate'}
    for preference,rs in contests.items():
        for mix,volume in list(mixes.items())+[('native-pair-'+preference,preference)]:
            native=mix.startswith('native-pair');v=[float(contests[volume][f]['candidate_writein_votes']) for f in fips]
            participation=[float(rs[f]['pair_participation']) for f in fips];w=[a*p for a,p in zip(v,participation)];s=[float(rs[f]['d_pair_share']) for f in fips]
            # Native pair volumes are exact source integers, not rounded fractions.
            if native:w=[int(rs[f]['pair_votes']) for f in fips]
            sid=preference+'__'+mix;settings.append({'scenario_id':sid,'preference_contest':preference,'allcandidate_volume_contest':volume,'volume_rule':'actual historical county candidate+generic-writein counts','pair_rule':'same preference county D+R / candidate+generic-writein fraction times volume; exact D+R for native-pair','low_base_high_status':'historical participation/mix sensitivity only; no 2026 projection','other_candidate_rule':'each named other and generic Write-in share held separately at preference county source fraction'})
            spec=SPECS[preference]
            for f,vol in zip(fips,v):
                for col,(label,party) in enumerate(zip(spec['labels'],spec['parties']),1):
                    if col-1 in [spec['d'],spec['r']]:continue
                    actual=candidates[preference,f,col]
                    other_rows.append({'scenario_id':sid,'county_fips':f,'preference_contest':preference,'native_candidate_label':label,'party_header':party,'historical_candidate_votes':actual,'historical_candidate_generic_denominator':rs[f]['candidate_writein_votes'],'scenario_allcandidate_volume':vol,'fixed_scenario_candidate_votes':vol*actual/int(rs[f]['candidate_writein_votes']),'role':'generic write-in category; named validity unknown' if label=='Write-in' else 'separate named nonmajor candidate'})
            tot=sum(w);a=sum(v)
            other_sums=collections.defaultdict(float)
            for row in other_rows:
                if row['scenario_id']==sid:other_sums[row['native_candidate_label']]+=row['fixed_scenario_candidate_votes']
            for goal,net in [('tie',0.),('D+1-pair-margin',.01*tot),('D+1-allcandidate-margin',.01*a)]:
                result=bounded_uniform(s,w,net);assert result['feasible']
                state.append({'scenario_id':sid,'goal':goal,'preference_contest':preference,'volume_contest':volume,'all_candidate_volume':a,'pair_volume':tot,'pair_participation':tot/a,'baseline_net':result['baseline_net'],'baseline_pair_margin':result['baseline_net']/tot,'target_net':net,'target_pair_margin':net/tot,'target_allcandidate_margin':net/a,'unbounded_share_shift':result['unbounded_share_shift'],'solved_share_shift':result['solved_share_shift'],'unbounded_clipped_count':result['unbounded_clipped_count'],'status':result['status'],'baseline_meets_target':result['baseline_meets_target'],'achieved_net':sum(t*(2*q-1) for t,q in zip(w,result['target_shares'])),'scenario_d_votes':(tot+net)/2,'scenario_r_votes':(tot-net)/2,'largest_separate_other_votes':max(other_sums.values(),default=0),'d_exceeds_all_separate_others':(tot+net)/2>max(other_sums.values(),default=0)})
                for f,vol,t,base,q in zip(fips,v,w,s,result['target_shares']):
                    targets.append({'scenario_id':sid,'goal':goal,'county':rs[f]['county'],'county_fips':f,'preference_contest':preference,'allcandidate_volume_contest':volume,'all_candidate_volume':vol,'pair_participation':float(rs[f]['pair_participation']),'pair_volume':t,'pair_weight':t/tot,'allcandidate_weight':vol/a,'baseline_d_share':base,'baseline_pair_margin':2*base-1,'baseline_net':t*(2*base-1),'target_d_share':q,'target_pair_margin':2*q-1,'d_share_change_points':100*(q-base),'margin_change_points':200*(q-base),'target_net':t*(2*q-1),'net_gain':2*t*(q-base),'net_gain_per_1pp_d_share':.02*t,'state_pair_margin_contribution_points':100*t*(2*q-1)/tot,'unbounded_target_share':base+result['unbounded_share_shift'],'bound_applied':not 0<=base+result['unbounded_share_shift']<=1})
            # Every selected county, holding ALL other county shares and volumes
            # at the explicitly same preference/mix; solve tie and D+1 separately.
            rem=[{'key':f,'pair_votes':t,'other_votes':vol-t,'d_share':base} for f,t,vol,base in zip(fips,w,v,s)]
            for f in fips:
                for goal,margin,den in [('tie',0.,'pair'),('D+1-pair-margin',.01,'pair'),('D+1-allcandidate-margin',.01,'all-candidate')]:
                    selected.append({'scenario_id':sid,'goal':goal,'county':rs[f]['county'],'county_fips':f,'others_preference_contest':preference,'all_county_volume_contest':volume,**conditional(0,0,0,rem,f,margin,den)})
    csvout('state-scenarios.csv',state);csvout('county-target-scenarios.csv',targets);csvout('selected-county-break-even.csv',selected);csvout('scenario-other-candidates.csv',other_rows);dump('scenario-settings.json',settings)
    # Pin a real historical method/unit, no 2026 geographic interpretation.
    native=[r for r in records('native-candidate-method.csv') if r['year']=='2022' and r['county_fips']=='19153' and r['native_unit_label']=='DES MOINES 1' and r['native_method']=='Absentee' and r['metric']=='candidate_votes']
    assert len(native)==3
    dd=int(next(r['votes'] for r in native if r['native_candidate_label']=='Michael Franken'));rr=int(next(r['votes'] for r in native if r['native_candidate_label']=='Chuck Grassley'));oo=int(next(r['votes'] for r in native if r['native_candidate_label']=='Write-in'))
    allD=sum(int(r['d']) for r in contests['2022-senate'].values());allR=sum(int(r['r']) for r in contests['2022-senate'].values());allO=sum(int(r['generic_writein_votes']) for r in contests['2022-senate'].values())
    unit=conditional(allD-dd,allR-rr,allO-oo,[{'key':native[0]['unit_key']+'/Absentee','pair_votes':dd+rr,'other_votes':oo,'d_share':dd/(dd+rr)}],margin=.01)
    dump('selected-native-unit-example.json',{'scope':'2022 native DES MOINES 1 Absentee alone varies; every other historical2022 statewide vote fixed; impossible is an honest result','source_rows':native,'calculation':unit})
    synthetic=[{'name':'tie','result':conditional(40,60,10,[{'key':'A','pair_votes':100,'other_votes':20,'d_share':.5}])},{'name':'D+1 pair','result':conditional(40,60,10,[{'key':'A','pair_votes':100,'other_votes':20,'d_share':.5}],margin=.01)},{'name':'D+1 all-candidate','result':conditional(40,60,10,[{'key':'A','pair_votes':100,'other_votes':20,'d_share':.5}],margin=.01,denominator='all-candidate')}]
    dump('live-remainder-examples.json',{'scope':'synthetic arithmetic only; counted D40 R60 other10 fixed; pair remainder100 and other20','examples':synthetic})
    print('Scenarios:',len(state),'state,',len(targets),'county targets,',len(selected),'selected-county solves')
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--live-json',help='JSON input path for conditional(); offline, no fetch');args=p.parse_args()
    if args.live_json:print(json.dumps(conditional(**json.loads(Path(args.live_json).read_text())),indent=2))
    else:build()
