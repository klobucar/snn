#!/usr/bin/env python3
"""Offline source integrity, newsroom admission and derived-data preflight checks."""
from pathlib import Path
from collections import Counter
import csv, datetime, gzip, hashlib, io, json, re, zipfile

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'manifest.json').read_text())
assert len({r['id'] for r in manifest})==len(manifest)
raw={};verified=[]
for row in manifest:
    stored=(ROOT/row['asset']).read_bytes();body=gzip.decompress(stored)
    assert hashlib.sha256(stored).hexdigest()==row['stored_sha256']
    assert hashlib.sha256(body).hexdigest()==row['raw_sha256'] and len(body)==row['bytes']
    assert row['retrieved_at_utc'] and (row.get('headers') or row.get('raw_headers'))
    assert len(stored)<40_000_000
    raw[row['id']]=body
    verified.append({'id':row['id'],'status':row['status'],'bytes':len(body),'sha256':row['raw_sha256']})

gsync={}
for key in ('kltv-results','kfda-results','kcbd-results'):
    html=raw[key].decode();marker='Fusion.contentCache='
    cache=json.JSONDecoder().raw_decode(html[html.index(marker)+len(marker):])[0]
    samples=[]
    for entry in cache['gsync-elections'].values():
        data=entry['data'];selected=data['selectedElection'];races=selected.get('races',[])
        votes=sum(int(c['votes']) for race in races for c in race.get('candidates',[]))
        samples.append({'selected':{k:v for k,v in selected.items() if k!='races'},'races':len(races),
                        'candidate_votes':votes,'senate_race_names':[r['name'] for r in races if 'senat' in r['name'].lower()]})
    gsync[key]={'samples':samples,'test_display_enabled':'"displayTestData":true' in html}
assert gsync['kltv-results']['samples'][0]['selected']['id']=='2668'
assert gsync['kltv-results']['samples'][0]['races']==64
assert gsync['kltv-results']['samples'][0]['candidate_votes']==0
assert not gsync['kltv-results']['samples'][0]['senate_race_names']
assert gsync['kfda-results']['samples'][0]['selected']['id'] is None

tribune=json.loads(raw['tribune-primary-public-json'])
assert len(tribune)==435 and {(r['election_type'],r['election_date']) for r in tribune}=={('primary','2026-03-03')}
senate=[r for r in tribune if r['office']=='U.S. Senate'];assert len(senate)==2
tribune_controls=[]
for race in senate:
    assert race['office_division']==2 and race['source']=='Associated Press'
    candidates={c['id']:c for c in race['candidacies']};counties=race['counties']
    assert len(counties)==254 and len({c['fips'] for c in counties})==254
    assert all(re.fullmatch(r'\d{3}',c['fips']) for c in counties)
    sums=Counter()
    for county in counties:
        assert set(county['results'])==set(candidates)
        assert sum(county['results'].values())==county['total_votes']
        sums.update(county['results'])
    assert all(sums[cid]==c['votes'] for cid,c in candidates.items())
    assert sum(sums.values())==race['total_votes']==sum(c['total_votes'] for c in counties)
    assert sum(c['total_precincts'] for c in counties)==race['total_precincts']==10006
    assert sum(c['precincts_reporting'] for c in counties)==race['precincts_reporting']==10006
    tribune_controls.append({'race_id':race['id'],'party':race['party'],'county_rows':254,
        'candidate_rows':len(candidates),'total_votes':race['total_votes'],'precincts_reporting':10006,
        'candidate_county_totals_match':True,'source':race['source'],'contest_result':race['contest_result'],
        'estimated_votes_high_mid_low':[race['estimated_votes_high'],race['estimated_votes_mid'],race['estimated_votes_low']],
        'county_code_schema':'Three-digit county suffix, not full five-digit FIPS; no precinct rows exposed here',
        'scope':'March primary; no publisher count timestamp in these race records; zero estimate/method/registration fields do not establish zero remaining ballots or a method split'})

with zipfile.ZipFile(io.BytesIO(raw['tarrant-november-download'])) as archive:
    assert archive.testzip() is None
    notice={name:archive.read(name).decode('utf-8-sig') for name in archive.namelist()}
assert list(notice)==['ENR_1126.txt'] and 'will be posted as soon as it becomes available' in notice['ENR_1126.txt']

vtd={}
for key in ('tlc-2024-senate-vtd','tlc-2024-president-vtd','tlc-2024-voterdata-vtd','tlc-2022-governor-vtd','tlc-2022-voterdata-vtd'):
    reader=csv.DictReader(io.StringIO(raw[key].decode('utf-8-sig')));rows=list(reader)
    assert len(rows)==9712 and len({r['CNTYVTD'] for r in rows})==len(rows)
    assert len({r['VTDKEY'] for r in rows})==len(rows)
    assert len({r['CNTYVTD'][:3] for r in rows})==254
    fields=reader.fieldnames[2:] if 'voterdata' not in key else ['Voter_Registration','Turnout']
    totals={field:sum(int(r[field]) for r in rows) for field in fields}
    assert all(int(r[field])>=0 for field in fields for r in rows)
    vtd[key]={'rows':len(rows),'county_prefixes':254,'totals':totals}

# Read the retained primary publication, rather than manufacturing a residual allocation.
clerk=ROOT.parents[2]/'ohio/data/baselines/house-2024.txt'
text=clerk.read_text();start=re.search(r'^\s*TEXAS\s*$',text,re.MULTILINE).start()
section=text[start:text.index('FOR UNITED STATES REPRESENTATIVE',start)]
def control(label):
    line=next(line for line in section.splitlines() if line.strip().startswith(label))
    return int(re.search(r'([\d,]+)\s*$',line).group(1).replace(',',''))
senate_pairs={'AllredD_24G_U.S. Sen':'Colin Z. Allred,','AndrusW_24G_U.S. Sen':'Tracy Andrus,',
              'BrownL_24G_U.S. Sen':'Ted Brown,','CruzR_24G_U.S. Sen':'Ted Cruz,','RocheW_24G_U.S. Sen':'Analisa Roche,'}
president_pairs={'HarrisD_24G_President':'Democratic','OliverL_24G_President':'Libertarian',
                 'SteinG_24G_President':'Green','TrumpR_24G_President':'Republican','Write-InW_24G_President':'Write-in'}
differences={}
for key,pairs in (('tlc-2024-senate-vtd',senate_pairs),('tlc-2024-president-vtd',president_pairs)):
    differences[key]={field:{'TLC_derived':vtd[key]['totals'][field],'Clerk':control(label),
                             'TLC_minus_Clerk':vtd[key]['totals'][field]-control(label)} for field,label in pairs.items()}
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'snapshots':len(manifest),
        'verified':verified,'newsroom_gsync':gsync,'Tribune_primary':{'race_records':435,'election_date':'2026-03-03','senate_controls':tribune_controls},
        'Tarrant_download_contents':notice,'TLC_derived_samples':vtd,
        'Clerk_text_sha256':hashlib.sha256(clerk.read_bytes()).hexdigest(),'derived_minus_primary':differences,
        'scope':'Preparation diagnostics only. Differing derived VTD counts are not accepted certified/native precinct baselines. No November Senate feed or cadence verified; no rescaling or residual allocation.'}
output=ROOT/'inspection.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'pass','snapshots':len(manifest),'TLC_rows_per_sample':9712,'TLC_county_prefixes':254,
                  'Tarrant_download':'future notice only','KLTV':'64 zero local races; no Senate row','scope':result['scope']},indent=2))
