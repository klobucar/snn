#!/usr/bin/env python3
"""Coordinator county-control/priority audit, independent of worker builders.

Finer reporting-unit inventories can continue to grow; this accepts county
counts/priorities only and never treats a derivative unit as approved geography.
"""
from pathlib import Path
from collections import defaultdict,Counter
import csv,datetime,hashlib,json

ROOT=Path(__file__).resolve().parent
def rows(rel):
    with (ROOT/rel).open() as stream:return list(csv.DictReader(stream))
def load(rel):return json.loads((ROOT/rel).read_text())
turnout=rows('county-turnout.csv');baselines=rows('county-baselines.csv')
peer=rows('baselines/county-candidates.csv');controls=rows('baselines/state-candidate-controls.csv')
assert len(turnout)==254 and len(baselines)==1016 and len(peer)==6604 and len(controls)==26
assert {r['county_fips'] for r in turnout}=={'48'+str(2*i+1).zfill(3) for i in range(254)}
bindex={(r['contest'],r['county_fips']):r for r in baselines};assert len(bindex)==1016
pindex={(r['contest'],r['county_fips'],r['native_candidate_name']):r for r in peer};assert len(pindex)==6604
cross=[]
for rel,mapping in [('turnout/county-candidates-2024.csv',{'senate':'2024-senate','president':'2024-president'}),
                    ('turnout/county-candidates-comparators.csv',{'senate_2020':'2020-senate','governor_2022':'2022-governor'})]:
    for r in rows(rel):
        contest=mapping[r['contest']];key=(contest,r['county_fips'],r['source_candidate_name'])
        assert key in pindex,key
        other=pindex[key]
        for left,right in [('election_date','election_date'),('source_county_name','native_county_name'),
                           ('source_county_code','native_county_code'),('source_party','native_party'),('write_in','write_in')]:
            assert r[left]==other[right],(key,left)
        assert int(r['votes'])==int(other['votes']) and int(r['source_county_total'])==int(other['county_contest_total']),key
        cross.append(key)
assert len(cross)==len(set(cross))==6604
county=defaultdict(Counter);state=Counter()
for (contest,fips,name),r in pindex.items():
    votes=int(r['votes']);assert votes>=0
    category={'DEM':'d','REP':'r'}.get(r['native_party'],'other')
    county[(contest,fips)][category]+=votes;state[(contest,name)]+=votes
    assert int(r['county_contest_total'])==int(bindex[(contest,fips)]['candidate_votes'])
for key,sums in county.items():
    b=bindex[key]
    assert all(sums[field]==int(b[field]) for field in ('d','r','other')),key
    assert sum(sums.values())==int(b['candidate_votes']) and int(b['pair_votes'])==sums['d']+sums['r'],key
assert len(state)==26
for control in controls:
    key=(control['contest'],control['native_candidate_name'])
    assert state[key]==int(control['votes'])==int(control['county_sum']) and int(control['difference'])==0,key
    assert sum(v for (contest,name),v in state.items() if contest==control['contest'])==int(control['state_contest_total'])

fieldmaps={'2024-senate':'senate_2024','2024-president':'president_2024','2020-senate':'senate_2020','2022-governor':'governor_2022'}
comparisons=0
for t in turnout:
    for contest,prefix in fieldmaps.items():
        b=bindex[(contest,t['county_fips'])]
        for suffix,field in [('d','d'),('r','r'),('other','other'),('total','candidate_votes')]:
            assert int(t[prefix+'_'+suffix])==int(b[field]);comparisons+=1
        assert t['source_county_name']==b['native_county_name'] and t['source_county_code']==b['native_county_code']
        assert t['dispatch_key']==b['dispatch_key']=='TX:'+t['county_fips']
        assert t['rank']==b['senate2024_volume_rank']
ordered=sorted(turnout,key=lambda r:(-int(r['senate_2024_total']),r['county_fips']))
assert ordered==turnout and [int(r['rank']) for r in turnout]==list(range(1,255))
denominator=sum(int(r['senate_2024_total']) for r in turnout);cumulative=0;minimum=None
for rank,t in enumerate(turnout,1):
    cumulative+=int(t['senate_2024_total'])
    assert cumulative==int(t['cumulative_senate_2024'])
    if minimum is None and 5*cumulative>=4*denominator:minimum=rank
assert denominator==11291854 and minimum==34
priority=turnout[:minimum];priority_votes=sum(int(r['senate_2024_total']) for r in priority)
previous_votes=priority_votes-int(priority[-1]['senate_2024_total'])
top15=sum(int(r['senate_2024_total']) for r in turnout[:15])
assert (top15,previous_votes,priority_votes)==(7369697,9018686,9076868)
assert priority[-1]['county_fips']=='48329' and priority[-1]['county']=='Midland'
assert int(priority[-1]['senate_2024_total'])==58182
contract=load('turnout/priority-set.json')
assert contract['source_denominator']==denominator and contract['minimum80_count']==minimum
assert contract['priority_keys']==[r['dispatch_key'] for r in priority]
assert contract['full_order']==[r['dispatch_key'] for r in turnout]
assert contract['remainder_keys']==[r['dispatch_key'] for r in turnout[minimum:]]
assert contract['top15_votes']==top15 and contract['minimum80_votes']==priority_votes and contract['preceding_set_votes']==previous_votes
assert contract['remainder_votes']==denominator-priority_votes==2214986
assert len(contract['groups'])==254
for t,g in zip(turnout,contract['groups']):
    assert (g['dispatch_key'],g['county_fips'],g['native_county_identity'],g['rank'],g['votes'])==(t['dispatch_key'],t['county_fips'],t['source_county_name'],int(t['rank']),int(t['senate_2024_total']))
    assert g['native_constituents'][0]['layer']=='SOS county canvass'
    assert g['native_constituents'][0]['native_id']==t['source_county_name']
    assert bool(g['priority80'])==(int(t['rank'])<=minimum)
assert next(r for r in turnout if r['county_fips']=='48087')['source_county_name']=='COLLINGSWOR'
assert next(r for r in turnout if r['county_fips']=='48447')['source_county_name']=='THROCKMORT'
keybytes=('\n'.join(r['dispatch_key'] for r in priority)+'\n').encode()
(ROOT/'coordinator-priority-keys.txt').write_bytes(keybytes)
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'Primary county candidates/control sums, cross-assignment county identities and exact priority. Finer derivative/native-unit layers are not approved or declared complete.',
        'counties':254,'baseline_rows':1016,'primary_candidate_county_cells':6604,'state_candidate_controls':26,
        'county_summary_cells_compared':comparisons,'senate_denominator':denominator,'top15_votes':top15,
        'priority_count':minimum,'priority_votes':priority_votes,'preceding_votes':previous_votes,'crossing':'Midland / TX:48329 / 58182',
        'priority_keys_sha256':hashlib.sha256(keybytes).hexdigest(),'priority_keys':[r['dispatch_key'] for r in priority],
        'input_hashes':{rel:hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() for rel in ('county-turnout.csv','county-baselines.csv','baselines/county-candidates.csv','baselines/state-candidate-controls.csv','turnout/county-candidates-2024.csv','turnout/county-candidates-comparators.csv')},
        'native_aliases':'COLLINGSWOR and THROCKMORT remain printed identities; FIPS mapping explicit; no reassignment of derivative filenames or fine units.',
        'footer_review':'Coordinator visually checked original page previews: county 07/01/2025 10.42 AM, state 01/07/2025 10:42 AM; no certification/release chronology inferred.'}
output=ROOT/'coordinator-baseline-reconciliation.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('input_hashes','priority_keys')},indent=2))
