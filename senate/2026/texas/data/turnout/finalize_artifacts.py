#!/usr/bin/env python3
"""Document owned evidence and read-only dependencies; hash each deliverable."""
import datetime,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;STATE=ROOT.parent.parent

def sha(b):return hashlib.sha256(b).hexdigest()
def ledger():
    sources=[]
    for f in sorted((ROOT/'raw').glob('*.meta.json')):
        m=json.load(open(f));m['metadata_path']=str(f.relative_to(ROOT));m['ownership']='turnout';sources.append(m)
    used=['sos2020-county-20201216','sos2020-county-20241003','sos2020-state-20210510','sos2020-state-20241211','sos2022-county-20241003','sos2022-state-20230627']
    for key in used:
        f=ROOT.parent/'baselines/raw'/(key+'.meta.json');m=json.load(open(f));m['metadata_path']='../baselines/raw/'+f.name;m['dependency_root']='../baselines';m['ownership']='partisanship read-only dependency';sources.append(m)
    news=json.load(open(ROOT.parent/'news/manifest.json'))
    for m in news:
        if m['id'].startswith('tlc-') or m['id']=='sos-turnout-controls':
            mm=dict(m);mm.update(metadata_path='../news/manifest.json',dependency_root='../news',ownership='coordinator read-only dependency');sources.append(mm)
    # resolve from Texas root, not an inferred filesystem relocation
    clerk=STATE.parent/'ohio/data/baselines/house-2024.txt'
    result={'research_observed_utc_date':'2026-10-18','sources':sources,'shared_primary_clerk':{'path':'../../ohio/data/baselines/house-2024.txt','url':'https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf','sha256':sha(clerk.read_bytes()),'ownership':'published Ohio evidence read-only'},'source_clock_policy':'source footer literal, archive memento time, HTTP Last-Modified, Date and retrieval UTC kept separately; no certification or release chronology inferred from ambiguous numeric footer dates','source_precedence':'Archived official SOS county/state canvass selected only after candidate/row/state controls and cross-vintage equality; Clerk2024 exact check; source-native precinct/vendor/derived VTD differences retained separately, never residual-allocated','source_layer_limits':'Historical county priority accepted. Full native reporting geography, source fine-unit controls and2026 approved polygon crosswalk incomplete; current historical SOS app403 does not establish human-browser outage.'}
    (ROOT/'source-ledger.json').write_text(json.dumps(result,indent=2)+'\n')

def manifest():
    paths=[STATE/'turnout.md',STATE/'data/county-turnout.csv']+[p for p in ROOT.rglob('*') if p.is_file() and p.name!='asset-manifest.json' and '__pycache__' not in p.parts]
    entries=[]
    for p in sorted(paths):
        b=p.read_bytes();assert len(b)<40000000,(p,len(b));entries.append({'path':str(p.relative_to(STATE)),'bytes':len(b),'sha256':sha(b)})
    (ROOT/'asset-manifest.json').write_text(json.dumps({'ownership':'turnout.md; data/county-turnout.csv; data/turnout/** only','asset_limit_bytes_strictly_less_than':40000000,'self_excluded':'asset-manifest.json cannot hash itself; all other retained owned files included; interpreter __pycache__ is not a retained asset','assets':entries},indent=2)+'\n')
    return entries
if __name__=='__main__':ledger();manifest()
