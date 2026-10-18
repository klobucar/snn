#!/usr/bin/env python3
"""Offline response integrity and bounded NPR/AP Senate-primary scope audit."""
from pathlib import Path
from collections import Counter
import datetime,gzip,hashlib,json,re

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'manifest.json').read_text());assert len({x['id'] for x in manifest})==len(manifest)
raw={};verified=[]
for row in manifest:
    stored=(ROOT/row['asset']).read_bytes();body=gzip.decompress(stored)
    assert hashlib.sha256(stored).hexdigest()==row['stored_sha256']
    assert hashlib.sha256(body).hexdigest()==row['raw_sha256'] and len(body)==row['bytes']
    assert row['retrieved_at_utc'] and (row.get('headers') or row.get('raw_headers'))
    assert len(stored)<40_000_000
    raw[row['id']]=body;verified.append({'id':row['id'],'status':row['status'],'bytes':len(body),'sha256':row['raw_sha256']})
assert 'Sources: Electoral results from the AP.' in raw['ipr-npr-embed'].decode()
state=json.loads(raw['npr-senate-primary'])['races'];county=json.loads(raw['npr-senate-primary-counties'])['races']
assert len(state)==len(county)==2 and {r['party'] for r in state}=={'Dem','GOP'}
controls=[]
for race in state:
    assert (race['date'],race['state'],race['type'],race['office'],race['seat'],race['test'])==('6/2/2026','IA','Primary','S','2',False)
    other=next(r for r in county if r['id']==race['id'])
    assert all(race[k]==other[k] for k in ('date','state','type','office','seat','party','test'))
    rows=other['results'];assert len(rows)==99 and len({r['fips'] for r in rows})==99
    assert all(re.fullmatch(r'19\d{3}',r['fips']) for r in rows)
    top,=race['results'];candidates={r['id']:r for r in top['candidates']};sums=Counter()
    for row in rows:
        assert {c['id'] for c in row['candidates']}==set(candidates)
        assert sum(c['votes'] for c in row['candidates'])==row['total']
        sums.update({c['id']:c['votes'] for c in row['candidates']})
    assert all(sums[cid]==c['votes'] for cid,c in candidates.items())
    assert sum(sums.values())==top['total']==sum(r['total'] for r in rows)
    assert sum(r['precincts'] for r in rows)==top['precincts']==1659
    reporting=sum(r['reporting'] for r in rows)
    assert reporting==1658 and top['reporting']==1659
    incomplete=[{k:r[k] for k in ('fips','county','precincts','reporting','reportingPercentage','eevp','updated')} for r in rows if r['reporting']!=r['precincts']]
    assert len(incomplete)==1 and incomplete[0]['fips']=='19103'
    controls.append({'race_id':race['id'],'party':race['party'],'county_rows':99,'candidate_county_sums_exact':True,
        'state_total':top['total'],'state_updated_epoch_milliseconds':top['updated'],
        'state_updated_utc_from_epoch':datetime.datetime.fromtimestamp(top['updated']/1000,datetime.timezone.utc).isoformat(),
        'state_precincts_reporting':top['reporting'],'county_precincts_reporting_sum':reporting,
        'state_eevp':top['eevp'],'county_incomplete_reporting':incomplete,
        'scope':'Two displayed named candidates per party. NPR states candidates below 1% are not individually shown; this is not a certified all-candidate total. Completion estimate and reporting flags are separate fields.'})
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshots':len(manifest),'verified':verified,
        'NPR_AP_primary':{'election_date':'2026-06-02','source_credit':'AP electoral results, explicit NPR footer','senate_controls':controls},
        'scope':'Preparation: exact retained bytes and historical displayed-count/coverage checks only; no November feed, primary certification, outstanding inventory or release cadence established.'}
output=ROOT/'inspection.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'pass','snapshots':len(manifest),'county_rows_per_party':99,'candidate_sums_exact':True,
                  'completion_gap':'State 1,659 vs county sum 1,658; Johnson 65/66 in both parties','scope':result['scope']},indent=2))
