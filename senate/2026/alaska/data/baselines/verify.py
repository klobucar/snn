#!/usr/bin/env python3
"""Verify raw hashes, all-unit coverage and independent turnout-worker agreement."""
import argparse,csv,datetime,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    raw=[];failed=[]
    for r in json.loads((ROOT/'manifest.json').read_text()):
        if r['curl_exit_code']:
            failed.append(dict(file=r['file'],url=r['url'],exit_code=r['curl_exit_code']));continue
        if 'preserved_in_parts' in r:
            h=hashlib.sha256()
            for chunk in r['preserved_in_parts']:
                p=ROOT/chunk['file'];assert sha(p)==chunk['sha256'];h.update(p.read_bytes())
            assert h.hexdigest()==r['sha256']
        else:assert sha(ROOT/r['file'])==r['sha256'],r['file']
        assert sha(ROOT/(r['file']+'.headers'))==r['headers_sha256']
        raw.append(r['file'])
    assert all(p.stat().st_size<40*1024**2 for p in ROOT.rglob('*') if p.is_file())
    base=list(csv.DictReader((ROOT.parent/'county-baselines.csv').open()));keys=[(r['election_year'],r['stage'],r['source_unit_id'],r['candidate']) for r in base];assert len(keys)==len(set(keys))==1558
    for y in ['2020','2022','2024']:
        rows=[r for r in base if r['election_year']==y and r['stage']=='first_choices'];assert len({r['source_unit_id'] for r in rows})==41
        assert all(r['county_fips']=='' for r in rows)
    own={(r['election_year'],r['source_unit_id'],r['candidate']):int(r['votes']) for r in base if r['stage']=='first_choices'}
    turnout=ROOT.parent/'turnout/district-reconciliation.csv';comparisons=[]
    for r in csv.DictReader(turnout.open()):
        y={'24GENR':'2024','22GENR':'2022'}.get(r['election_id']);n=str(int(r['district_key'].split('HD')[1]));key=(y,n,r['measure'])
        if key not in own:continue
        assert own[key]==int(r['constituent_sum'])==int(r['official_hd_pdf']) and int(r['difference'])==0,key
        comparisons.append(key)
    assert len(comparisons)==533 and len(set(comparisons))==533
    # Exercise the selected-unit solve, including infeasible and feasible cases.
    pairs={n:{r['candidate']:int(r['votes']) for r in base if r['election_year']=='2024' and r['stage']=='first_choices' and int(r['source_unit_id'])==n} for n in list(range(1,41))+[99]}
    examples=[]
    for n,shift,g in [(99,0,0),(12,6.8,0),(12,6.8,.01),(12,8,0),(12,9,0)]:
        tc=pairs[n]['Harris/Walz']+pairs[n]['Trump/Vance'];T=sum(d['Harris/Walz']+d['Trump/Vance'] for d in pairs.values());other=sum((d['Harris/Walz']+d['Trump/Vance'])*(2*(d['Harris/Walz']/(d['Harris/Walz']+d['Trump/Vance'])+shift/100)-1) for j,d in pairs.items() if j!=n);q=(tc+g*T-other)/(2*tc)
        assert abs(other+tc*(2*q-1)-g*T)<1e-7
        examples.append(dict(unit=n,others_share_shift_pp=shift,target_margin_pp=100*g,required_share_pct=100*q,status='impossible' if q>1 else 'already secured' if q<0 else 'feasible'))
    assert examples[0]['status']=='impossible' and examples[1]['status']=='feasible' and examples[-1]['status']=='already secured'
    report=dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),successful_raw_evidence_files=len(raw),failed_fetches_retained=failed,baseline_rows=len(base),independent_turnout_comparisons=len(comparisons),turnout_input=str(turnout.relative_to(ROOT.parent.parent)),turnout_input_sha256=sha(turnout),county_baselines_sha256=sha(ROOT.parent/'county-baselines.csv'),selected_unit_examples=examples,all_checks_passed=True)
    (ROOT/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
