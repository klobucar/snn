#!/usr/bin/env python3
"""Offline integrity, controls, full scenarios and independent arithmetic tests.
Run after build and render_report.py. Writes only owned paths. No downloads.
"""
import collections,datetime,json,math,re
from common import *
from calculate import conditional,bounded_uniform
def near(a,b,tol=1e-7):assert abs(float(a)-float(b))<=tol,(a,b)
def tests():
    r=[{'key':'A','pair_votes':100,'other_votes':20,'d_share':.5}]
    near(conditional(40,60,10,r)['required_d_share'],.6)
    q=conditional(40,60,10,r,margin=.01);near(q['required_d_share'],.61);near(q['final_denominator'],200)
    q=conditional(40,60,10,r,margin=.01,denominator='all-candidate');near(q['required_d_share'],.6115);near(q['final_denominator'],230)
    # The selected county alone varies; other remaining votes and counted lead
    # stay fixed. Final pair denominator is 200, not the 20 selected votes.
    r=[{'key':'A','pair_votes':20,'other_votes':0,'d_share':.2},{'key':'B','pair_votes':80,'other_votes':0,'d_share':.75}]
    near(conditional(40,60,0,r,'A',.01)['required_d_share'],.05)
    assert conditional(10,0,0,[{'key':'A','pair_votes':2,'other_votes':0,'d_share':.5}])['status']=='already-secured'
    assert conditional(0,10,0,[{'key':'A','pair_votes':2,'other_votes':0,'d_share':.5}])['status']=='impossible'
    for d,r,expected in [(3,2,True),(2,3,False),(2,2,True)]:
        q=conditional(d,r,0,[]);assert q['status']=='no-positive-pool' and q['meets_target']==expected
    assert conditional(0,0,0,[])['status']=='no-positive-denominator'
    invalid=[None,[{'key':'A','pair_votes':None,'other_votes':0,'d_share':.5}],[{'key':'A','pair_votes':1,'other_votes':0,'d_share':1.1}],[{'key':'A','pair_votes':-1,'other_votes':0,'d_share':.5}],[{'key':'A','pair_votes':1,'other_votes':0,'d_share':math.nan}]]
    for rs in invalid:assert conditional(0,0,0,rs)['status']=='unavailable'
    rs=[{'key':'A','pair_votes':1,'other_votes':0,'d_share':.5}]
    assert conditional(0,0,0,rs+rs)['status']=='unavailable'
    assert conditional(0,0,0,rs,'missing')['status']=='unavailable'
    assert conditional(None,0,0,rs)['status']=='unavailable'
    assert conditional(0,0,0,rs,margin=2)['status']=='unavailable'
    q=bounded_uniform([.99,.1],[100,900],0);assert q['unbounded_clipped_count']==1 and q['status']=='bounded-feasible';near(sum(t*(2*s-1) for t,s in zip([100,900],q['target_shares'])),0)
    assert q['target_shares'][0]==1
    q=bounded_uniform([.7],[100],0);near(q['solved_share_shift'],-.2);assert q['baseline_meets_target']
    assert bounded_uniform([.5],[0],0)['status']=='no-positive-pool'
    assert bounded_uniform([.5],[100],101)['status']=='impossible'
    assert bounded_uniform([None],[100],0)['status']=='unavailable'
    return 'passed: final pair/all-candidate denominators; selected remainder; fixed counted lead; negative/already-winning shifts; clipping; unavailable/duplicate/negative/no-pool/impossible inputs'
def main():
    checked=[]
    for r in sources():
        if r.get('path'):
            raw(r);assert r['stored_bytes']<40000000;checked.append(r['id'])
    controls=records('state-controls.csv');assert all(r['difference'] in ['','0'] for r in controls)
    cc=records('county-contests.csv');assert len(cc)==297
    for c in SPECS:
        group=[r for r in cc if r['contest']==c];assert len({r['county_fips'] for r in group})==len(group)==99
        for r in group:
            d=int(r['d']);rr=int(r['r']);other=int(r['named_nonmajor_votes']);wi=int(r['generic_writein_votes']);a=int(r['candidate_writein_votes']);assert d+rr+other+wi==a
            assert a+int(r['under_votes'])+int(r['over_votes'])==int(r['reported_contest_total']);near(float(r['d_pair_share']),(d/(d+rr)))
    wide=records('../county-baselines.csv');assert len(wide)==len({r['county_fips'] for r in wide})==99
    priority=json.loads((ROOT/'priority.json').read_text());rank=records('priority-order.csv');den=priority['denominator'];n=priority['minimum_count'];assert den==1663506 and n==41
    assert int(rank[n-2]['cumulative_votes'])*5<4*den<=int(rank[n-1]['cumulative_votes'])*5
    assert [r['county_fips'] for r in rank]==[r['county_fips'] for r in sorted(rank,key=lambda r:(-int(r['candidate_writein_votes']),r['county_fips']))]
    assert sum(int(r['candidate_writein_votes']) for r in rank[:15])==991869
    natives=records('native-units.csv');assert len(natives)==len({r['unit_key'] for r in natives})==3512
    assert len({(r['year'],r['county_fips']) for r in natives})==198
    nc=records('native-candidate-method.csv');assert len(nc)==len({(r['source_id'],r['sheet'],r['source_row'],r['source_column']) for r in nc})
    ng=collections.defaultdict(dict)
    for r in nc:
        if r['metric']=='candidate_votes':ng[r['unit_key'],r['native_candidate_label']][r['native_method']]=r['votes']
    administrative={r['unit_key'] for r in natives if r['row_scope']=='county total'}
    for key,vals in ng.items():
        total=vals.get('Total Votes',vals.get('Total'));assert total is not None
        if key[0] in administrative and set(vals)=={'Total'}:continue  # Scott PDF prints only county Total footer.
        assert int(vals['Election Day'])+int(vals['Absentee'])==int(total),key
    nativechecks=records('native-checks.csv');assert len(nativechecks)==2385
    assert all(r['sum_minus_primary'] in ['','0'] and r['footer_minus_primary'] in ['','0'] for r in nativechecks)
    duplicate_labels=[];labels=collections.defaultdict(list)
    for r in natives:labels[r['source_id'],r['sheet'],r['native_unit_label']].append(r['unit_key'])
    for key,ks in labels.items():
        if len(ks)>1:duplicate_labels.append({'source_label_key':key,'source_row_keys':ks})
    csvs=records('county-target-scenarios.csv');states=records('state-scenarios.csv');assert len(csvs)==3564 and len(states)==36
    groups=collections.defaultdict(list)
    for r in csvs:groups[r['scenario_id'],r['goal']].append(r)
    other=collections.defaultdict(float)
    for r in records('scenario-other-candidates.csv'):other[r['scenario_id'],r['county_fips']]+=float(r['fixed_scenario_candidate_votes'])
    for s in states:
        group=groups[s['scenario_id'],s['goal']];assert len({r['county_fips'] for r in group})==99
        near(sum(float(r['pair_weight']) for r in group),1);near(sum(float(r['allcandidate_weight']) for r in group),1)
        near(sum(float(r['target_net']) for r in group),s['target_net']);near(sum(float(r['target_net']) for r in group),s['achieved_net'])
        for r in group:
            q=float(r['target_d_share']);t=float(r['pair_volume']);base=float(r['baseline_d_share']);assert 0<=q<=1
            near(r['target_net'],t*(2*q-1));near(r['net_gain'],2*t*(q-base));near(r['net_gain_per_1pp_d_share'],.02*t);near(r['margin_change_points'],2*float(r['d_share_change_points']))
            near(t+other[r['scenario_id'],r['county_fips']],r['all_candidate_volume'])
        assert s['d_exceeds_all_separate_others']=='True'
    selected=records('selected-county-break-even.csv');assert len(selected)==3564
    for r in selected:
        if r['status']=='feasible':near(float(r['fixed_net'])+float(r['selected_pair_pool'])*(2*float(r['required_d_share'])-1),r['target_net'])
        elif r['status']=='impossible':assert float(r['required_d_share'])>1 and float(r['achieved_net_at_boundary'])<float(r['target_net'])
        elif r['status']=='already-secured':assert float(r['required_d_share'])<0
        else:raise AssertionError(r)
    peer=json.loads((ROOT/'peer-reconciliation.json').read_text());stats=json.loads((ROOT/'statistics-verification.json').read_text());assert peer['status']==stats['status']=='pass'
    clarity=json.loads((ROOT/'clarity-2024-summary.json').read_text());assert clarity['status']=='pass'
    assert (clarity['county_count'],clarity['candidate_constituents'],clarity['turnout_constituents'],clarity['status_constituents'],clarity['native_candidate_cells'])==(99,1653,1651,1653,26448)
    assert clarity['party_label_differences']==42 and clarity['party_label_counties']==14
    assert len(clarity['context_conflicts'])==1 and clarity['context_conflicts'][0]['county_fips']=='19117'
    cl=records('clarity-2024-native-candidate-method.csv');assert len(cl)==len({(r['source_id'],r['source_xml_path']) for r in cl})==26448
    clunits=records('clarity-2024-native-units.csv');assert len(clunits)==len({r['unit_key'] for r in clunits})==3304
    assert all(r['source_contest_key']=='' for r in clunits if r['source_xml_path'].startswith('VoterTurnout'))
    for r in peer['peer_artifact_hashes']+stats['peer_artifacts']:
        p=ROOT/r['path'];assert sha(p.read_bytes())==r['sha256'] and p.stat().st_size==r['bytes'],str(p)
    for r in json.loads((ROOT/'review-evidence.json').read_text())['references']:
        p=ROOT/r['path'];assert sha(p.read_bytes())==r['sha256'] and p.stat().st_size==r['bytes'],str(p)
    for r in json.loads((ROOT/'http-refresh.json').read_text()):
        if r.get('path'):
            body=gzip.decompress((ROOT/r['path']).read_bytes());assert sha(body)==r['original_sha256'] and len(body)==r['original_bytes']
    links=[]
    for p in [ROOT/'SCHEMA.md',STATE/'county-partisanship.md']:
        for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',p.read_text()):
            if target.startswith(('https://','http://','#')):continue
            local=(p.parent/target.split('#')[0]).resolve()
            assert local.exists() or local in [ROOT/'validation.json',ROOT/'asset-manifest.json'],(p,target)
            links.append(str(local.relative_to(STATE)))
    for p in ROOT.rglob('*'):
        if p.is_file():assert p.stat().st_size<40000000,str(p)
        assert p.name not in ['__pycache__','node_modules'],str(p)
    result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_source_references_verified':len(checked),'county_contests':297,'county_count':99,'canvass_numeric_cells':7484,'native_unit_rows_2020_2022':len(natives),'native_metric_cells_2020_2022':len(nc),'native_candidate_method_control_groups_2020_2022':len(nativechecks),'native_candidate_cells_2024':len(cl),'native_context_rows_2024':len(clunits),'duplicate_native_labels_preserved':duplicate_labels,'exact80_denominator':den,'exact80_minimum_count':n,'state_scenarios':len(states),'county_target_rows':len(csvs),'selected_county_rows':len(selected),'statistics_numeric_cells_checked':stats['numeric_or_percent_cells_checked'],'peer_reconciliation':'pass','arithmetic_tests':tests(),'relative_links_checked':len(links),'scope':'historical research and deterministic scenarios; no collector, current precinct approval, forecast or calibration'}
    dump('validation.json',result)
    assets=[]
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.name!='asset-manifest.json']+[STATE/'county-partisanship.md',ROOT.parent/'county-baselines.csv']
    for p in sorted(files):
        b=p.read_bytes();assets.append({'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else '../../county-partisanship.md' if p.name=='county-partisanship.md' else '../county-baselines.csv','sha256':sha(b),'bytes':len(b)})
    dump('asset-manifest.json',{'scope':'owned artifacts; self excluded to avoid circular hash; originals separately verified via sources.json; peer artifacts pinned by reconciliation evidence','assets':assets})
    for local in links:assert (STATE/local).exists(),local
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
