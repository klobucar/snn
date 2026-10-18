#!/usr/bin/env python3
"""Independent saved-output checks plus calculator edge cases.
Only writes validation/derived manifests inside the assigned baselines directory.
"""
import collections,csv,datetime,hashlib,json,math,pathlib,platform,re,subprocess,sys
from calculate import conditional,load,scenario,levels
BASE=pathlib.Path(__file__).resolve().parent
ROOT=BASE.parent.parent

def rows(p):
 with p.open() as f:return list(csv.DictReader(f))
def f(r,k):return float(r[k])
def near(a,b,tol=1e-7):assert abs(a-b)<tol,(a,b,a-b)

def main():
    primary=json.loads((BASE/'manifest.json').read_text())['sources']
    assert len({m['file'] for m in primary})==len(primary)
    for m in primary:
        assert (BASE/m['file']).stat().st_size==m['bytes']
        assert hashlib.sha256((BASE/m['file']).read_bytes()).hexdigest()==m['sha256'],m['file']
        assert m['http_status']==200 and '+00:00' in m['retrieved_at_utc']
    b=rows(BASE.parent/'county-baselines.csv');c=rows(BASE/'county-candidates.csv');sc=rows(BASE/'state-scenarios.csv');targets=rows(BASE/'county-target-scenarios.csv')
    assert len(b)==300 and len(c)==1685 and len(sc)==42 and len(targets)==4200
    by={(r['year'],r['county_fips']):r for r in b};assert len(by)==300
    census={r['STATEFP']+r['COUNTYFP'] for r in csv.DictReader((BASE/'census-national-county2020.txt').open(),delimiter='|') if r['STATE']=='NC'}
    expected_totals={2022:(1784049,1905786,84089,3773924),2024:(2715378,2898424,85343,5699145),2020:(2569965,2665598,239389,5474952)}
    for y,expected in expected_totals.items():
        rs=[r for r in b if r['year']==str(y)]
        assert {r['county_fips'] for r in rs}==census and len(rs)==100
        assert tuple(sum(int(r[k]) for r in rs) for k in ['dem_votes','rep_votes','other_votes','contest_votes'])==expected
        near(sum(f(r,'major_party_turnout_weight') for r in rs),1,1e-14)
        near(sum(f(r,'contest_turnout_weight') for r in rs),1,1e-14)
        for r in rs:
            D,R,O,T=[int(r[k]) for k in ['dem_votes','rep_votes','other_votes','contest_votes']]
            assert D+R+O==T and int(r['major_party_votes'])==D+R and int(r['net_d_minus_r'])==D-R
            near(f(r,'dem_two_party_share'),D/(D+R),1e-14)
            near(f(r,'d_minus_r_two_party_margin'),(D-R)/(D+R),1e-14)
            near(f(r,'d_minus_r_all_vote_margin'),(D-R)/T,1e-14)
            assert int(r['other_votes'])==sum(o['votes'] for o in json.loads(r['other_candidates_json']))
            assert all(r[k]=='' for k in ['ballots_cast','undervotes','overvotes','registered_voters'])
    assert len({(r['year'],r['county_fips'],r['candidate'],r['party']) for r in c})==len(c)
    grouped=collections.defaultdict(list)
    for r in c:
        grouped[(r['year'],r['county_fips'])].append(r)
        assert int(r['votes'])==sum(int(r[k]) for k in ['election_day','early_voting','absentee_by_mail','provisional'])
    for key,rs in grouped.items():
        br=by[key]
        for parties,field in [({'DEM'},'dem_votes'),({'REP'},'rep_votes'),({'LIB','GRE','CST','JFA',''},'other_votes')]:
            assert sum(int(r['votes']) for r in rs if r['party'] in parties)==int(br[field])
    # Independently reconcile every saved candidate and voting-method sum.
    state_candidates=rows(BASE/'certified-state-candidates.csv')
    assert len(state_candidates)==19
    for r in state_candidates:
        match=[x for x in c if (x['year'],x['candidate'],x['party'])==(r['year'],r['candidate'],r['party'])]
        for field in ['votes','election_day','early_voting','absentee_by_mail','provisional']:
            assert sum(int(x[field]) for x in match)==int(r[field]),(r['year'],r['candidate'],field)
    classifications=collections.Counter(r['cross_election_classification'] for r in b if r['year']=='2022')
    assert classifications=={'D_all_three':21,'R_all_three':76,'mixed_winners':3}
    rec=rows(BASE/'candidate-reconciliation.csv');assert len(rec)==19
    assert all(int(r['county_minus_state'])==0 for r in rec)
    assert sum(int(r['zip_minus_certified']) for r in rec if r['year']=='2024')==-4
    anchor=rows(BASE/'2014-anchor-reconciliation.csv');assert len(anchor)==7 and all(int(r['difference'])==0 for r in anchor)
    # Reopen all scenario CSV rows and recompute independently from integer inputs.
    gtargets=collections.defaultdict(list)
    for r in targets:gtargets[(r['scenario_id'],r['target'])].append(r)
    state_lookup={(r['scenario_id'],r['target']):r for r in sc}
    maxerr=0
    for key,rs in gtargets.items():
        sr=state_lookup[key];assert len(rs)==100 and {r['county_fips'] for r in rs}==census
        T=f(sr,'state_expected_major_party_votes');goal=f(sr,'target_d_minus_r_margin_pp')/100
        weights_source=[r for r in b if r['year']==sr['turnout_weight_year']]
        wden=sum(int(r['major_party_votes']) for r in weights_source)
        baselineM=0;targetM=0
        for r in rs:
            pref=by[(sr['preference_baseline_year'],r['county_fips'])];turn=by[(sr['turnout_weight_year'],r['county_fips'])]
            q0=int(pref['dem_votes'])/int(pref['major_party_votes']);expectedT=T*int(turn['major_party_votes'])/wden
            near(f(r,'expected_major_party_votes'),expectedT)
            near(f(r,'turnout_weight'),int(turn['major_party_votes'])/wden,1e-14)
            q=f(r,'target_dem_share');assert 0<=q<=1
            near(q-q0,f(sr,'required_dem_share_shift_pp')/100,1e-14)
            near(f(r,'target_d_minus_r_margin_pp'),100*(2*q-1),1e-11)
            near(f(r,'target_net_d_minus_r'),expectedT*(2*q-1))
            near(f(r,'additional_net_d_minus_r'),2*expectedT*(q-q0))
            near(f(r,'net_vote_value_plus_1pp_dem_share'),.02*expectedT)
            baselineM+=expectedT*(2*q0-1);targetM+=expectedT*(2*q-1)
            # Reconstruct the statewide target using the conditional selected share.
            req=f(r,'selected_county_required_share_others_at_baseline')
            otherM=f(sr,'baseline_net_d_minus_r')-expectedT*(2*q0-1)
            near(otherM+expectedT*(2*req-1),goal*T)
            expected_status='already secured even at 0% D share' if req<0 else 'impossible even at 100% D share' if req>1 else 'feasible conditional threshold'
            assert r['selected_county_conditional_status']==expected_status
        near(sum(f(r,'turnout_weight') for r in rs),1,1e-14)
        near(sum(f(r,'expected_major_party_votes') for r in rs),T)
        near(baselineM,f(sr,'baseline_net_d_minus_r'))
        near(targetM,goal*T);maxerr=max(maxerr,abs(targetM-goal*T))
        otherlabel='D_plus_1_two_party_margin' if key[1]=='tie' else 'tie'
        peer=state_lookup[(key[0],otherlabel)]
        near(abs(f(sr,'required_dem_share_shift_pp')-f(peer,'required_dem_share_shift_pp')),.5,1e-12)
    # Uniform statewide scaling must not change a mix's share threshold.
    sg=collections.defaultdict(list)
    for r in sc:
        if r['turnout_level']!='native_historical':sg[(r['preference_baseline_year'],r['turnout_weight_year'],r['target'])].append(r)
    for rs in sg.values():
        assert len(rs)==3
        assert max(f(r,'required_dem_share_shift_pp') for r in rs)-min(f(r,'required_dem_share_shift_pp') for r in rs)<1e-12
    # Boundary conditions and per-county overrides, using simple independently solvable fixtures.
    fixture=[{'county_fips':'37001','county':'A','T':40.,'s':.4},{'county_fips':'37003','county':'B','T':60.,'s':.6}]
    near(conditional(fixture,'37001',0)['required_dem_share'],.35,1e-14)
    near(conditional(fixture,'37001',.01)['required_dem_share'],.3625,1e-14)
    assert conditional(fixture,'37001',0,overrides={'37003':1.})['required_dem_share']<0
    assert conditional(fixture,'37001',0,overrides={'37003':0.})['required_dem_share']>1
    near(conditional(fixture,'37001',0,overrides={'37003':.5})['required_dem_share'],.5,1e-14)
    for overrides in [{'37003':1.01},{'37003':-.01},{'99999':.5},{'37001':.5},{'37003':'0.5'},['37003']]:
        try:conditional(fixture,'37001',0,overrides=overrides)
        except AssertionError:pass
        else:raise AssertionError(('invalid override accepted',overrides))
    d=load()
    for invalidtotal in [0,-10,float('inf'),float('nan')]:
        try:scenario(d,2022,2022,invalidtotal)
        except AssertionError:pass
        else:raise AssertionError(('invalid turnout accepted',invalidtotal))
    for args in [['--county','Unknown'],['--county','Wake','--state-major-party-votes','0'],['--county','Wake','--others-share-shift-pp','100'],['--county','Wake','--target-margin-pp','101']]:
        p=subprocess.run([sys.executable,str(BASE/'calculate.py'),*args],capture_output=True,text=True)
        assert p.returncode!=0,args
    cross=json.loads((BASE/'turnout-reconciliation.json').read_text())
    assert cross['passed'] and cross['county_count_differences']==0 and cross['candidate_cell_differences']==0
    for dep in cross['dependency_snapshots']:
        assert hashlib.sha256((ROOT/dep['path']).read_bytes()).hexdigest()==dep['sha256'],('Turnout dependency changed; rerun reconcile_turnout.py',dep['path'])
    cross_rows=rows(BASE/'turnout-reconciliation.csv');assert len(cross_rows)==200
    turnout_by={r['county_fips']:r for r in rows(BASE.parent/'county-turnout.csv')}
    for row in cross_rows:
        br=by[(row['year'],row['county_fips'])];tr=turnout_by[row['county_fips']]
        prefix='president_2024' if row['year']=='2024' else 'senate_2022'
        for bk,tk in [('dem_votes',prefix+'_d'),('rep_votes',prefix+'_r'),('other_votes',prefix+'_other'),('contest_votes',prefix+'_total')]:
            assert int(row[bk+'_difference'])==0
            assert int(br[bk])==int(tr[tk])==int(row[bk+'_partisanship'])==int(row[bk+'_turnout'])
    report=(ROOT/'county-partisanship.md').read_text()
    local_links=[]
    for target in re.findall(r'\]\(([^)]+)\)',report):
        if re.match(r'^[a-z]+://',target):continue
        path=(ROOT/target.split('#')[0]).resolve()
        # validation/artifact manifests are created later in this same successful run.
        assert path.exists() or path.name in ['validation.json','artifact-manifest.json'],target
        local_links.append(target)
    files=[*BASE.glob('*'),BASE.parent/'county-baselines.csv',ROOT/'county-partisanship.md']
    assert all(p.stat().st_size<40_000_000 for p in files if p.is_file())
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result={'validated_at_utc':now,'passed':True,'source_hashes_checked':len(primary),'county_baseline_rows':len(b),'county_candidate_rows':len(c),'primary_candidate_reconciliations':19,'candidate_voting_method_reconciliations':76,'cross_election_county_classes':dict(classifications),'supplemental_2014_candidate_reconciliations':7,'baseline_counties_per_election':100,'state_scenarios_checked':len(sc),'county_target_rows_checked':len(targets),'max_target_net_error_votes':maxerr,'tolerance_votes':1e-7,'conditional_reconstruction_all_rows':True,'turnout_county_summary_cells_exact':800,'turnout_candidate_total_method_cells_exact':6500,'turnout_same_primary_pdf_vintages':4,'boundary_and_invalid_input_checks':True,'local_report_links_checked':len(local_links),'all_individual_files_below_40MB':True,'known_raw_source_differences':'four 2024 county/candidate entries; authoritative certified baseline reconciles exactly','forecast_or_probability_implemented':False}
    (BASE/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    artifacts=[]
    for path in sorted([p for p in BASE.iterdir() if p.is_file() and p.name!='artifact-manifest.json']+[BASE.parent/'county-baselines.csv',ROOT/'county-partisanship.md']):
        artifacts.append({'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (BASE/'artifact-manifest.json').write_text(json.dumps({'generated_at_utc':now,'parser_version':'1','python':platform.python_version(),'poppler':subprocess.run(['pdftotext','-v'],capture_output=True,text=True).stderr.splitlines()[0],'offline_rebuild':['build_baselines.py','calculate.py','reconcile_turnout.py','render_report.py','validate.py'],'original_source_manifest':'manifest.json','files':artifacts},indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
