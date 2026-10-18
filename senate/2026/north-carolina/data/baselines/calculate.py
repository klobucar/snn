#!/usr/bin/env python3
"""Offline deterministic targets and selected-county conditional calculator.
Shares/margins are fractions internally; *_pp columns are percentage points.
No election-night counts, probabilities, turnout prediction, or Git operations.
"""
import argparse,csv,json,math,pathlib
BASE=pathlib.Path(__file__).resolve().parent
YEARS=(2022,2020,2024)

def read_csv(path):
    with path.open() as f:return list(csv.DictReader(f))
def write_csv(name,rows):
    with (BASE/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def load():
    rows=read_csv(BASE.parent/'county-baselines.csv');out={}
    for y in YEARS:
        out[y]={r['county_fips']:r for r in rows if int(r['year'])==y}
        assert len(out[y])==100
    for y in YEARS:assert set(out[y])==set(out[2022])
    return out

def levels(data):
    low=sum(int(r['votes']) for r in read_csv(BASE/'2014-senate-state-zip-extract.csv') if r['party'] in ['DEM','REP'])
    return {'low_2014_senate':low,'base_2022_senate':sum(int(r['major_party_votes']) for r in data[2022].values()),'high_2024_president':sum(int(r['major_party_votes']) for r in data[2024].values())}

def scenario(data,preference_year,mix_year,total):
    assert math.isfinite(total) and total>0
    source_total=sum(int(r['major_party_votes']) for r in data[mix_year].values())
    rows=[]
    for fips,r in data[preference_year].items():
        weight=int(data[mix_year][fips]['major_party_votes'])/source_total
        rows.append({'county_fips':fips,'county':r['county'],'s':int(r['dem_votes'])/int(r['major_party_votes']),'T':total*weight,'weight':weight,'baseline':r})
    assert abs(sum(r['weight'] for r in rows)-1)<1e-14
    M=math.fsum(r['T']*(2*r['s']-1) for r in rows)
    return rows,M

def conditional(rows,selected,target_margin,others_shift=0,overrides=None):
    """Solve one county, with other county D shares fixed by inputs.
    Overrides map 5-digit FIPS to other counties' fractional D shares.
    """
    overrides=overrides or {}
    assert isinstance(overrides,dict),'Overrides must be a JSON object mapping county FIPS to fractional shares'
    assert all(isinstance(q,(int,float)) and not isinstance(q,bool) for q in overrides.values()),'Override shares must be numeric fractions'
    known={r['county_fips'] for r in rows}
    assert set(overrides)<=known,('Unknown override FIPS',set(overrides)-known)
    selected_row=next(r for r in rows if r['county_fips']==selected)
    assert selected not in overrides,'Selected county cannot also be fixed by override'
    total=math.fsum(r['T'] for r in rows);other_net=0
    for r in rows:
        if r['county_fips']==selected:continue
        q=overrides.get(r['county_fips'],r['s']+others_shift)
        assert math.isfinite(q) and 0<=q<=1,('Other county share outside [0,1]',r['county'],q)
        other_net+=r['T']*(2*q-1)
    q=(selected_row['T']+target_margin*total-other_net)/(2*selected_row['T'])
    status='already secured even at 0% D share' if q<0 else 'impossible even at 100% D share' if q>1 else 'feasible conditional threshold'
    return {'required_dem_share':q,'required_dem_share_pct':q*100,'change_from_baseline_share_pp':(q-selected_row['s'])*100,'status':status,'other_counties_net_d_minus_r':other_net,'selected_expected_major_party_votes':selected_row['T'],'state_expected_major_party_votes':total,'target_margin_pp':target_margin*100,'target_net_d_minus_r':target_margin*total}

def all_tables(data):
    state_rows=[];county_rows=[];sensitivity=[];native=[]
    lv=levels(data)
    for label,total in lv.items():
        sensitivity.append({'level':label,'expected_state_major_party_votes':total,'scale_relative_to_2022_senate':total/lv['base_2022_senate'],'evidence':'observed historical D+R contest votes, not a 2026 turnout estimate'})
    specs=[(p,m,lv[k],k) for p in YEARS for m in [2022,2024] for k in lv]
    specs.extend((y,y,sum(int(r['major_party_votes']) for r in data[y].values()),'native_historical') for y in YEARS)
    for pref,mix,total,level in specs:
        rows,M=scenario(data,pref,mix,total)
        scenario_id=f'preferences_{pref}_mix_{mix}_{level}'
        for g,label in [(0,'tie'),(.01,'D_plus_1_two_party_margin')]:
            delta=(g-M/total)/2
            assert all(0<=r['s']+delta<=1 for r in rows),(scenario_id,'uniform target infeasible')
            # All current uniform scenarios are feasible; future failures must not be silently clipped.
            target_net=math.fsum(r['T']*(2*(r['s']+delta)-1) for r in rows)
            assert abs(target_net-g*total)<1e-7,(scenario_id,target_net,g*total)
            state_rows.append({'scenario_id':scenario_id,'preference_baseline_year':pref,'preference_contest':data[pref][rows[0]['county_fips']]['contest'],'turnout_weight_year':mix,'turnout_weight_contest':data[mix][rows[0]['county_fips']]['contest'],'turnout_level':level,'target':label,'state_expected_major_party_votes':total,'baseline_net_d_minus_r':M,'baseline_d_minus_r_margin_pp':100*M/total,'required_dem_share_shift_pp':delta*100,'required_margin_shift_pp':delta*200,'target_d_minus_r_margin_pp':g*100,'target_net_d_minus_r':g*total,'sum_county_target_net_votes':target_net,'target_reconciliation_error_votes':target_net-g*total,'uniform_targets_feasible':True,'turnout_weights_sum':math.fsum(r['weight'] for r in rows)})
            for r in rows:
                b=r['baseline'];q=r['s']+delta;one=conditional(rows,r['county_fips'],g)
                county_rows.append({'scenario_id':scenario_id,'target':label,'county':r['county'],'county_fips':r['county_fips'],'preference_baseline_year':pref,'preference_contest':b['contest'],'baseline_dem_votes':int(b['dem_votes']),'baseline_rep_votes':int(b['rep_votes']),'baseline_other_votes':int(b['other_votes']),'baseline_dem_two_party_share':r['s'],'baseline_d_minus_r_margin_pp':(2*r['s']-1)*100,'turnout_weight_year':mix,'turnout_weight_contest':data[mix][r['county_fips']]['contest'],'turnout_level':level,'expected_major_party_votes':r['T'],'turnout_weight':r['weight'],'fixed_share_county_net_d_minus_r':r['T']*(2*r['s']-1),'target_dem_share':q,'target_dem_share_pct':q*100,'target_d_minus_r_margin_pp':(2*q-1)*100,'required_dem_share_shift_pp':delta*100,'required_margin_shift_pp':delta*200,'target_net_d_minus_r':r['T']*(2*q-1),'additional_net_d_minus_r':2*r['T']*delta,'net_vote_value_plus_1pp_dem_share':.02*r['T'],'selected_county_required_share_others_at_baseline':one['required_dem_share'],'selected_county_conditional_status':one['status']})
    write_csv('sensitivity-assumptions.csv',sensitivity)
    write_csv('state-scenarios.csv',state_rows)
    write_csv('county-target-scenarios.csv',county_rows)
    (BASE/'scenario-checks.json').write_text(json.dumps({'state_scenarios':len(state_rows),'county_target_rows':len(county_rows),'counties_per_state_scenario':100,'max_target_error_votes':max(abs(r['target_reconciliation_error_votes']) for r in state_rows),'uniform_share_bounds_pass':True,'probabilities_implemented':False,'statewide_total_levels':lv},indent=2)+'\n')
    print(json.dumps({'state_scenarios':len(state_rows),'county_target_rows':len(county_rows),'levels':lv},indent=2))

def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--county',help='County name or five-digit NC FIPS')
    p.add_argument('--baseline-year',type=int,choices=YEARS,default=2022)
    p.add_argument('--mix-year',type=int,choices=[2022,2024],default=2022)
    p.add_argument('--turnout-level',choices=['low','base','high'],default='base')
    p.add_argument('--state-major-party-votes',type=float,help='Override statewide expected D+R votes')
    p.add_argument('--target-margin-pp',type=float,default=0)
    p.add_argument('--others-share-shift-pp',type=float,default=0)
    p.add_argument('--other-shares-json',type=pathlib.Path,help='JSON object mapping other county FIPS to fractional D shares')
    args=p.parse_args();data=load()
    if args.county:
        hits=[fips for fips,r in data[args.baseline_year].items() if args.county.casefold() in [fips,r['county'].casefold()]]
        if len(hits)!=1:p.error('Choose an exact NC county name or FIPS')
        lv=levels(data);total=args.state_major_party_votes if args.state_major_party_votes is not None else next(v for k,v in lv.items() if k.startswith(args.turnout_level+'_'))
        try:
            assert math.isfinite(args.target_margin_pp) and -100<=args.target_margin_pp<=100,'Target margin must be within [-100,100] pp'
            rows,M=scenario(data,args.baseline_year,args.mix_year,total)
            overrides=json.loads(args.other_shares_json.read_text()) if args.other_shares_json else {}
            out=conditional(rows,hits[0],args.target_margin_pp/100,args.others_share_shift_pp/100,overrides)
        except (AssertionError,ValueError,TypeError) as e:p.error(str(e))
        out.update({'county':data[args.baseline_year][hits[0]]['county'],'county_fips':hits[0],'baseline_year':args.baseline_year,'baseline_contest':data[args.baseline_year][hits[0]]['contest'],'mix_year':args.mix_year,'others_share_shift_pp':args.others_share_shift_pp,'override_shares':overrides,'scenario_only':True})
        print(json.dumps(out,indent=2))
    else:all_tables(data)
if __name__=='__main__':cli()
