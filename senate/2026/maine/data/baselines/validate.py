#!/usr/bin/env python3
"""Independent output checks, primary controls, boundary cases and live arithmetic."""
import argparse, csv, datetime, gzip, hashlib, json, math, re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote
from build import ROOT, CONFIG, COUNTIES
from scenarios import PAIRS, calculator, selected_share

def rows(path):return list(csv.DictReader(Path(path).open()))
def close(a,b):assert abs(a-b)<1e-7,(a,b)

def main():
    verified=[]
    for m in json.loads((ROOT/'manifest.json').read_text()):
        p=ROOT/m['saved_path'];b=p.read_bytes();raw=gzip.decompress(b)
        assert hashlib.sha256(b).hexdigest()==m['saved_sha256']
        assert hashlib.sha256(raw).hexdigest()==m['original_sha256']
        assert len(raw)==m['original_bytes'] and len(b)<40_000_000
        assert m['http_status']==200
        verified.append(m['source_id'])
    base=rows(ROOT.parent/'county-baselines.csv');assert len(base)==2052
    official_counties={r[3].removesuffix(' County'):r[1]+r[2] for r in csv.reader(gzip.decompress((ROOT/'raw/county-fips.txt.gz').read_bytes()).decode().splitlines())}
    assert len(official_counties)==16
    assert all(official_counties[name]==fips for name,fips in COUNTIES.values())
    assert len({r['source_row_id'] for r in base})==2052
    rawc=rows(ROOT/'candidate-votes.csv');assert len(rawc)==9241
    assert len({(r['source_row_id'],r['candidate_id']) for r in rawc})==9241
    candidate_sums=defaultdict(int)
    for r in rawc:candidate_sums[(r['source_id'],r['candidate_id'])]+=int(r['votes'])
    for source,cfg in CONFIG.items():
        rr=[r for r in base if r['source_id']==source];assert len(rr)==cfg['n']
        for (col,(cid,_,_)),control in zip(cfg['candidates'].items(),cfg['controls']):
            assert sum(int(r[cid+'_votes']) for r in rr)==control==candidate_sums[(source,cid)]
        close(sum(float(r['contest_weight']) for r in rr),1)
        close(sum(float(r['d_r_pair_weight']) for r in rr),1)
        for r in rr:
            assert int(r['d_votes'])+int(r['r_votes'])+int(r['other_votes'])==int(r['contest_votes'])
            assert int(r['contest_votes'])+int(r['blank'])==int(r['tbc'])
            assert int(r['d_votes'])-int(r['r_votes'])==int(r['d_minus_r_votes'])
            assert r['unit_name']==r['native_unit_name'].strip()
    anomalies=[r for r in base if r['native_county_code']!=r['county_section_code']]
    assert len(anomalies)==1
    assert (anomalies[0]['source_id'],anomalies[0]['source_row'],anomalies[0]['native_unit_name'],anomalies[0]['native_county_code'],anomalies[0]['county_section_code'],anomalies[0]['contest_votes'])==('governor-2022','190','T3 ND Twp','PEN','HAN','4')
    cranberry=[r for r in base if r['source_id']=='governor-2022' and r['unit_name']=='Cranberry Isles']
    assert [r['source_row'] for r in cranberry]==['165','166']
    assert sum(int(r['contest_votes']) for r in cranberry)==115 and sum(int(r['tbc']) for r in cranberry)==117
    state=rows(ROOT/'state-scenarios.csv');assert len(state)==72
    settings=json.loads((ROOT/'scenario-settings.json').read_text())
    assert 'turnout_base_2024_senate_contest_votes' not in settings
    for pair,(source,a,b,_) in PAIRS.items():
        rr=[r for r in base if r['source_id']==source]
        assert settings['native_base_by_pair'][pair]['observed_contest_votes']==sum(int(r['contest_votes']) for r in rr)
        assert settings['native_base_by_pair'][pair]['observed_pair_votes']==sum(int(r[a+'_votes'])+int(r[b+'_votes']) for r in rr)
    scenario_checks=[];target_rows=0
    for pair,(source,a,b,caveat) in PAIRS.items():
        rr=rows(ROOT/(pair+'-unit-targets.csv'));target_rows+=len(rr)
        groups=defaultdict(list)
        for r in rr:groups[(r['mix'],r['volume'],r['target'])].append(r)
        for (mix,volume,target),group in groups.items():
            assert len(group)==CONFIG[source]['n']
            assert len({r['source_row_id'] for r in group})==len(group)
            s=next(x for x in state if (x['pair'],x['mix'],x['volume'],x['target'])==(pair,mix,volume,target))
            total=math.fsum(float(r['expected_pair_votes']) for r in group)
            net=math.fsum(float(r['target_net_contribution']) for r in group)
            baseline=math.fsum(float(r['baseline_net_contribution']) for r in group)
            close(total,float(s['expected_pair_votes']));close(net,0 if target=='tie' else .01*total)
            close(baseline,float(s['fixed_preference_net']))
            close(math.fsum(float(r['turnout_weight']) for r in group),1)
            for r in group:
                t=float(r['expected_pair_votes']);close(float(r['net_per_plus_1pp_a_share']),.02*t)
                if r['bounded_target_share']!='':
                    q=float(r['bounded_target_share']);assert 0<=q<=1
                    close(float(r['target_net_contribution']),t*(2*q-1))
            scenario_checks.append(dict(pair=pair,mix=mix,volume=volume,target=target,rows=len(group),sum_pair_votes=total,sum_target_net=net))
    assert target_rows==36948
    # Share points vs margin points, zero turnout, and impossible selected units.
    close(100*(2*.51-1)-100*(2*.50-1),2)
    q,status=selected_share([100,100],[.5,.5],0);close(q,.5)
    q,status=selected_share([100,100],[.5,.5],0,target_net=2);close(q,.51)
    q,status=selected_share([0,100],[.5,.5],0);assert q is None
    q,status=selected_share([1,100],[.5,1],0);assert q<0 and 'secured' in status
    q,status=selected_share([1,100],[.5,0],0);assert q>1 and 'impossible' in status
    # Live synthetic fixture: counted 100 A and 120 B are immutable; 200 remain.
    live=ROOT/'live-calculator-example.csv'
    live.write_text('source_row_id,remaining_pair_votes,a_share\nnorth,100,0.6\nsouth,100,0.5\n')
    args=argparse.Namespace(remaining=str(live),counted_a=100,counted_b=120,unit=None,target_net_votes=None,target_margin_pp=0,others_share_shift_pp=0)
    aggregate=calculator(args,{})
    close(aggregate['required_a_share'],.55);close(aggregate['projected_net_at_input_shares'],0)
    args.unit='north';selected=calculator(args,{})
    close(selected['required_a_share'],.6)
    args.unit=None;args.target_margin_pp=1;cushion=calculator(args,{})
    close(cushion['required_a_share'],.5605)
    assert aggregate['counted_a']==selected['counted_a']==cushion['counted_a']==100
    assert aggregate['counted_b']==selected['counted_b']==cushion['counted_b']==120
    transfers=rows(ROOT/'conditional-transfer-allocations.csv')
    for r in transfers:close(float(r['original_votes']),float(r['to_a'])+float(r['to_b'])+float(r['exhausted']))
    for r in rows(ROOT/'conditional-rcv-examples.csv'):
        close(float(r['final_a'])+float(r['final_b'])+float(r['exhausted_including_blank']),float(r['ballots_control']))
    v=rows(ROOT/'source-vintage-state-controls.csv')
    assert all(r['legislature_archive']==r['house_clerk_2024'] for r in v)
    assert all(r['current_sos']==r['nara_dec9'] for r in v if r['nara_dec9'])
    diff=rows(ROOT/'source-vintage-cell-differences.csv')
    assert {r['native_unit_name'] for r in diff if r['row_type']=='native disjoint reporting row'}=={'Alfred'}
    pr=json.loads((ROOT/'turnout-reconciliation.json').read_text())
    assert pr['all512_keys_order_candidates_blank_tbc_source_rows_exact'] and pr['priority_file_exact']
    link_count=0
    report=ROOT.parent.parent/'county-partisanship.md'
    if report.exists():
        for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
            if target.startswith(('https:','http:','#')):continue
            assert (report.parent/unquote(target.split('#')[0])).exists(),target
            link_count+=1
    (ROOT/'calculator-examples.json').write_text(json.dumps(dict(synthetic_live_aggregate=aggregate,synthetic_live_selected=selected,synthetic_live_plus1_margin=cushion),indent=2)+'\n')
    assets=[]
    paths=[ROOT.parent/'county-baselines.csv']+([report] if report.exists() else [])+[x for x in ROOT.rglob('*') if x.is_file() and '__pycache__' not in str(x) and x.name not in ['validation.json','asset-manifest.json']]
    for path in paths:
        assert path.stat().st_size<40_000_000,path
        assets.append(dict(path=str(path.relative_to(ROOT.parent.parent)),bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT/'asset-manifest.json').write_text(json.dumps(assets,indent=2)+'\n')
    result=dict(validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS',source_captures_verified=len(verified),source_ids=verified,
        source_rows=2052,candidate_cells=9241,state_controls=26,county_section_control_cells=len(rows(ROOT/'county-section-checks.csv')),
        scenarios=len(state),all_unit_target_rows=target_rows,scenario_sums=scenario_checks,priority=pr,official_county_fips_verified=16,native_volume_settings_exact=True,
        source_defects_preserved=dict(county_code_section_mismatches=1,cranberry_native_rows=2),
        synthetic_live_counted_votes_fixed=True,relative_report_links=link_count,maximum_asset_bytes=max(x['bytes'] for x in assets),
        visual_review='Clerk 2020 Maine PDF34/printed32; Clerk2024 PDF31/printed29; 2026 Senate sample; Alfred current results first page 2026 primary, rejected as 2024 evidence')
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','source_rows','candidate_cells','state_controls','scenarios','all_unit_target_rows','relative_report_links','maximum_asset_bytes']},indent=2))

if __name__=='__main__':main()
