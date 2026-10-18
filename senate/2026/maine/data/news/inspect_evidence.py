#!/usr/bin/env python3
"""Offline newsroom snapshot integrity and historical BDN count-scope inspection."""
from pathlib import Path
from collections import Counter,defaultdict
import datetime,gzip,hashlib,json

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'manifest.json').read_text());assert len({r['id'] for r in manifest})==len(manifest)
verified=[];raw={}
for r in manifest:
    p=ROOT/r['asset'];stored=p.read_bytes();b=gzip.decompress(stored)
    assert hashlib.sha256(stored).hexdigest()==r['stored_sha256']
    assert hashlib.sha256(b).hexdigest()==r['raw_sha256'] and len(b)==r['bytes']
    assert r['retrieved_at_utc'] and (r.get('headers') or r.get('raw_headers'))
    raw[r['id']]=b;verified.append({'id':r['id'],'status':r['status'],'bytes':len(b),'sha256':r['raw_sha256']})
d=json.loads(raw['bdn-senate-data']);towns=json.loads(raw['bdn-towns-data'])
assert d['race_date']=='2026-06-09' and d['race_id']==273768 and d['state']=='ME' and not d['test_data']
ids={str(c['cand_id']) for c in d['candidates']};assert len(ids)==4
counties=d['counties'];assert len(counties)==16 and len({c['fips'] for c in counties})==16
vcus=[(c,v) for c in counties for v in c.get('vcus',[])];assert len(vcus)==514
idgroups=defaultdict(list)
for c in counties:
    for ordinal,v in enumerate(c['vcus']):idgroups[(c['fips'],v['id'])].append({'county':c['county'],'source_array_ordinal_zero_based':ordinal,**v})
duplicates=[{'county_fips':county,'native_id':native,'rows':rr} for (county,native),rr in idgroups.items() if len(rr)>1]
county_votes=Counter();vcu_votes=Counter()
for c in counties:
    subtotal=Counter()
    for v in c.get('vcus',[]):
        assert set(v['votes'])==ids;subtotal.update(v['votes']);vcu_votes.update(v['votes'])
    assert dict(subtotal)==c['votes'];county_votes.update(c['votes'])
top=d['topline_results'];assert sum(top['votes'].values())==top['total_votes']==216402
assert all(top['votes'][cid]>=county_votes[cid] for cid in ids)
differences={cid:top['votes'][cid]-county_votes[cid] for cid in sorted(ids)}
call_ids=[str(c['cand_id']) for c in top.get('call_times',[])]
unknown_call_ids=sorted(set(call_ids)-ids)
wagm=raw['wagm-results'].decode();needle='Fusion.contentCache=';start=wagm.index(needle)+len(needle)
cache=json.JSONDecoder().raw_decode(wagm[start:])[0]
election_cache=[x['data'] for x in cache['gsync-elections'].values()]
assert all(x['selectedElection']['id'] is None and not x['elections'] for x in election_cache)
assert '"displayTestData":true' in wagm
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshots':len(manifest),'verified':verified,
        'BDN_primary':{'race_date':d['race_date'],'race_id':d['race_id'],'source_updated':d['last_updated'],'candidate_ids':sorted(ids),
                       'topline_votes':top['votes'],'topline_total':top['total_votes'],'county_rows':16,'native_vcu_rows':514,
                       'county_and_VCU_candidate_sums_exact':True,'county_candidate_sum':dict(county_votes),
                       'topline_minus_county_by_candidate':differences,'total_topline_minus_county':sum(differences.values()),
                       'town_lookup_names':len(towns),'uncontested_flag_with_four_candidates':d['uncontested'],
                       'county_and_native_id_distinct_keys':len(idgroups),'null_native_id_rows':sum(v['id'] is None for c,v in vcus),
                       'reused_native_id_groups':duplicates,
                       'call_times_ids_absent_from_candidate_roster':unknown_call_ids,
                       'limits':'Topline/county residual source not established; no administrative allocation inferred. Five-digit VCU fips is not county FIPS. Method zeros coexist with positive votes and are not validated method counts. 100% flags do not resolve these issues. Primary excluded from November ingestion.'},
        'WAGM_local':'No selected election/races; test display enabled; transformation time is not a vote event',
        'scope':'Original/stored hashes, historical count scope and schema diagnostics; no November feed or cadence certified'}
output=ROOT/'inspection.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':result['status'],'snapshots':len(manifest),'BDN_primary_VCU_rows':len(vcus),
                  'topline_minus_county':sum(differences.values()),'null_native_ids':sum(v['id'] is None for c,v in vcus),
                  'unknown_call_candidate_ids':unknown_call_ids,'WAGM_local':result['WAGM_local']},indent=2))
