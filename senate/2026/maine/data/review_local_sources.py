#!/usr/bin/env python3
"""Cross-check source-aware local transcriptions against selected SOS native rows.

This does not independently extract every PDF. The coordinator visually reviewed
Gorham, Falmouth and Rockport; the worker documents the remaining transcriptions.
"""
from pathlib import Path
import csv,datetime,gzip,hashlib,json

ROOT=Path(__file__).resolve().parent
rows={r['native_key']:r for r in csv.DictReader((ROOT/'county-turnout.csv').open())}
local=json.loads((ROOT/'results-sources/local-controls.json').read_text())
assert len(local)>=14 and len({r['native_key'] for r in local})==len(local)
fields=['cherry_independent_2024','costello_democratic_2024','king_independent_2024','kouzounas_republican_2024']
checks=[];source_hashes={}
for item in local:
    baseline=rows[item['native_key']]
    assert item['local_candidate_order']==['Cherry','Costello','King','Kouzounas']
    assert item['rank']==int(baseline['rank']) and item['unit']==baseline['unit_name'].strip()
    official=[int(baseline[field]) for field in fields]
    assert item['SOS_candidate_votes']==official
    differences=[a-b for a,b in zip(item['local_candidate_votes'],official)]
    assert differences==item['local_minus_current_SOS']
    assert item['all_candidate_controls_match']==all(x==0 for x in differences)
    metadata=json.loads((ROOT/'results-sources/requests'/f"{item['request_id']}.json").read_text())
    stored=(ROOT/'results-sources'/metadata['body_path']).read_bytes();raw=gzip.decompress(stored)
    assert metadata['complete'] and metadata['status']==200
    assert hashlib.sha256(stored).hexdigest()==metadata['saved_sha256'] and len(stored)==metadata['saved_bytes']
    assert hashlib.sha256(raw).hexdigest()==metadata['entity_sha256'] and len(raw)==metadata['entity_bytes_retained']
    assert raw.startswith(b'%PDF') and metadata['retrieved_utc'] and metadata['headers']
    source_hashes[item['request_id']]=metadata['entity_sha256']
    optional={}
    for source,target in [('local_BLANK','blank_senate_2024'),('local_TBC','ballots_cast_2024')]:
        optional[source]={'local':item[source],'SOS':int(baseline[target]),
                         'local_minus_SOS':None if item[source] is None else item[source]-int(baseline[target])}
    checks.append({'native_key':item['native_key'],'unit':item['unit'],'candidate_differences':differences,
                   'optional_fields':optional,'source_request':item['request_id']})
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'local_records':len(local),'candidate_baseline_cells':len(local)*4,
        'all_candidate_matches':sum(item['all_candidate_controls_match'] for item in local),
        'differences':[r for r in checks if any(r['candidate_differences'])],
        'source_original_hashes':source_hashes,
        'scope':f'Comparison of worker transcriptions to independently reconciled selected SOS rows; {len(local)} original PDF hashes checked. Coordinator manually viewed Gorham/Falmouth/Rockport. No generic independent extraction, correction cause, publication order or baseline change inferred.',
        'Rockport_scope':'Displayed Write-in row 49 contains Write-In column 3 plus Over/Under 46; no named-candidate allocation. SOS blank 49 remains its separate native field.'}
output=ROOT/'coordinator-local-source-review.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('source_original_hashes','differences')},indent=2))
