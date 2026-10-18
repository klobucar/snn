#!/usr/bin/env python3
"""Read-only field comparison with independently built partisanship artifacts."""
import csv,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;D=P.parent

def run():
    a=list(csv.DictReader(open(D/'county-turnout.csv')));b=list(csv.DictReader(open(D/'county-baselines.csv')));m={(r['county_fips'],r['contest']):r for r in b};checked=0;diff=[]
    for r in a:
        for prefix,contest in [('senate_2024','2024-senate'),('president_2024','2024-president'),('governor_2022','2022-governor'),('senate_2020','2020-senate')]:
            q=m[(r['county_fips'],contest)]
            for k,l in [(prefix+'_total','candidate_votes'),(prefix+'_d','d'),(prefix+'_r','r'),(prefix+'_other','other'),('source_county_name','native_county_name'),('source_county_code','native_county_code'),('dispatch_key','dispatch_key'),('rank','senate2024_volume_rank'),('cumulative_senate_2024','senate2024_cumulative_votes'),('top15','senate2024_top15'),('priority80','senate2024_priority80')]:
                checked+=1
                if str(r[k])!=q[l]:diff.append((r['county_fips'],contest,k,r[k],q[l]))
    ca=list(csv.DictReader(open(P/'county-candidates-2024.csv')))+list(csv.DictReader(open(P/'county-candidates-comparators.csv')));cb=list(csv.DictReader(open(D/'baselines/county-candidates.csv')));trans={'senate':'2024-senate','president':'2024-president','governor_2022':'2022-governor','senate_2020':'2020-senate'};cm={(r['contest'],r['county_fips'],r['native_candidate_name']):r for r in cb}
    assert len(ca)==len(cb)==len(cm)==6604
    for r in ca:
        key=(trans[r['contest']],r['county_fips'],r['source_candidate_name']);q=cm.get(key)
        if not q:diff.append(('missing',key));continue
        for k,l in [('source_county_name','native_county_name'),('source_county_code','native_county_code'),('source_party','native_party'),('write_in','write_in'),('votes','votes'),('source_county_total','county_contest_total'),('source_id','source_id')]:
            checked+=1
            if r[k]!=q[l]:diff.append((key,k,r[k],q[l]))
    priority=json.load(open(P/'priority-set.json'));other=json.load(open(D/'baselines/priority-set.json')) if (D/'baselines/priority-set.json').exists() else None
    # Reconstruct complete order independently from peer county integers, no field-name assumption.
    bs=[r for r in b if r['contest']=='2024-senate'];order=sorted(bs,key=lambda r:(-int(r['candidate_votes']),r['county_fips']));assert [r['dispatch_key'] for r in order]==priority['full_order'];cum=0;keys=[]
    for r in order:
        keys.append(r['dispatch_key']);cum+=int(r['candidate_votes'])
        if 5*cum>=4*priority['source_denominator']:break
    assert keys==priority['priority_keys']
    j={'status':'pass' if not diff else 'fail','county_rows':len(a),'baseline_contest_rows':len(b),'candidate_rows_compared':len(ca),'field_checks':checked,'differences':diff,'full_254_order_match':True,'exact_minimum80_keys_match':True,'scope':'Independent turnout-side comparison to read-only partisanship extraction; zero tolerance on shared integers, candidate identities, native names/codes, parties/write-ins, source IDs and ranks. Optional ballots differ in availability and are source-scoped, not substituted.','input_sha256':{str(f.relative_to(D)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [D/'county-turnout.csv',D/'county-baselines.csv',P/'county-candidates-2024.csv',P/'county-candidates-comparators.csv',D/'baselines/county-candidates.csv']}}
    (P/'peer-reconciliation.json').write_text(json.dumps(j,indent=2)+'\n');assert not diff,diff[:10];print('Independent peer reconciliation:',checked,'fields, full order and exact priority pass')
if __name__=='__main__':run()
