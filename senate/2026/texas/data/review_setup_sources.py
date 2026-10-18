#!/usr/bin/env python3
"""Independently audit retained November setup identities; no network or vote admission."""
from pathlib import Path
import base64,csv,datetime,gzip,hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parent
SOURCES=ROOT/'results-sources'
dependencies={}
def sha(body):return hashlib.sha256(body).hexdigest()
def read_body(source):
    meta_path=SOURCES/'raw'/(source+'.json');meta=json.loads(meta_path.read_text())
    assert meta['status']==200 and meta['body_complete'] is True
    assert meta['retrieval_started_utc'] and meta['retrieval_finished_utc'] and meta['headers']
    chunks=[]
    for part in meta['stored_parts']:
        body=(SOURCES/part['path']).read_bytes()
        assert len(body)==part['bytes']<40_000_000 and sha(body)==part['sha256']
        dependencies[str((SOURCES/part['path']).relative_to(ROOT))]=sha(body);chunks.append(body)
    stored=b''.join(chunks)
    assert len(stored)==meta['stored_stream_bytes'] and sha(stored)==meta['stored_stream_sha256']
    original=gzip.decompress(stored)
    assert len(original)==meta['original_bytes'] and sha(original)==meta['original_sha256']
    dependencies[str(meta_path.relative_to(ROOT))]=sha(meta_path.read_bytes())
    return original
def read(source):return json.loads(read_body(source))
def decoded(value):return json.loads(base64.b64decode(value)) if isinstance(value,str) else value

with (ROOT/'county-turnout.csv').open() as f:baseline=list(csv.DictReader(f))
canonical={r['county'].upper():r for r in baseline}
assert len(canonical)==254
state=read('sos-november-data');home=decoded(state['Home'])
assert state['Version']=='enr/53815/1/' and home['ElecDate']=='11032026'
lookup=decoded(state['Lookups'])['County'];counties=decoded(read('sos-november-counties')['upload'])
assert len(lookup)==len(counties)==254
assert {r['CN'] for r in lookup}==set(canonical)
assert {r['ID'] for r in lookup}==set(range(1,255))
assert all(r['MID']==48000+r['ID'] for r in lookup)
assert all(r['CN']==counties[str(r['ID'])]['N'] for r in lookup)
federal=next(r for r in decoded(state['Federal'])['Races'] if r['id']==5075)
candidate_ids={c['ID'] for c in federal['Candidates']}
assert candidate_ids=={33528,41261,42424,44430,44432,44434,44534}
assert all(c['V']==0 for c in federal['Candidates']) and federal['T']==0
def pdf_text(source):
    body=read_body(source);assert body.startswith(b'%PDF-')
    return subprocess.run(['pdftotext','-layout','-','-'],input=body,check=True,stdout=subprocess.PIPE).stdout.decode()
certification=pdf_text('sos-certification')
certified_counties=re.findall(r'County\s+([A-Z][A-Z ]+?)\s+U\. S\. SENATOR\s+KEN PAXTON\s+REP\s+JAMES TALARICO\s+DEM\s+TED BROWN\s+LIB',certification)
assert len(certified_counties)==len(set(certified_counties))==254
assert set(certified_counties)==set(canonical) and certification.count('U. S. SENATOR')==254
writeins=pdf_text('sos-writeins')
declared_writeins=re.findall(r'U\.S\. Senator\s+([^\n]+)',writeins)
assert declared_writeins==['Avery Ayers','Bradford "Brad" Hall','Zul Mohamed','Jade Simmons']
certified_names={'KEN PAXTON','JAMES TALARICO','TED BROWN'}|{n.upper() for n in declared_writeins}
assert {c['N'] for c in federal['Candidates']}==certified_names
sample=pdf_text('sos-sample-ballot')
assert re.search(r'United States Senator\s+.*Ken Paxton.*James Talarico.*Ted Brown',sample)
preview_hashes={}
for name in ('sos-certification','sos-certification-p2','sos-writeins','sos-sample-ballot'):
    p=ROOT/'coordinator-pdf-review'/(name+'.png')
    preview_hashes[str(p.relative_to(ROOT))]=sha(p.read_bytes())
inventory=[]
for entry in lookup:
    name=entry['CN'];county=counties[str(entry['ID'])];senate=county['Races']['5075']
    assert {int(i) for i in senate['C']}==candidate_ids
    assert senate['OID']==5075 and senate['T']==0 and all(c['V']==0 for c in senate['C'].values())
    inventory.append({'county':name,'county_fips':canonical[name]['county_fips'],'native_ID':entry['ID'],
                      'native_MID':entry['MID'],'state_senate_TP':senate['TP'],'state_senate_TPR':senate['TPR'],
                      'status':'zero setup; current geography and completion meanings unapproved'})
assert sum(str(r['native_MID'])==r['county_fips'] for r in inventory)==1
with (ROOT/'coordinator-current-county-keys.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(inventory[0]));writer.writeheader();writer.writerows(inventory)

harris=read('harris-senate-precinct');reporting=read('harris-reporting')
assert harris['i']==9189 and len(harris['p'])==len(set(harris['p']))==1224
assert harris['p']==reporting['p']
for key,value in harris.items():
    if isinstance(value,list):assert len(value)==1224,(key,len(value))
assert all(isinstance(unit,str) and unit.isdigit() and len(unit)==4 for unit in harris['p'])
assert all(len(v)==4 and sum(v)==0 for v in harris['v'])
assert sum(harris['bc'])==sum(harris['t'])==0
state_harris=next(r for r in inventory if r['county']=='HARRIS')
assert state_harris['state_senate_TP']==1225

observations=[]
for fips,test,expected_date,tp in [('48439','1','11/3/2026',2985),('48141','1','11/3/2026',236),('48029','0','11/3/2026',806),('48027','0','5/26/2026',None)]:
    settings=read('clarity-'+fips+'-electionsettings')['settings']['electiondetails']
    assert settings['istestmode']==test and settings['electiondate']==expected_date
    assert settings['showtestdatawatermark']=='0'
    if tp is not None:
        summaries=read('clarity-'+fips+'-summary')
        races=[r for r in summaries if 'senator' in r['C'].lower() and 'paxton' in ' '.join(r['CH']).lower()]
        assert len(races)==1
        race=races[0];assert race['TP']==tp and race['TV']==0 and sum(race['V'])==0
    observations.append({'county_fips':fips,'electiondate':expected_date,'istestmode':test,'showtestdatawatermark':'0',
                         'observed_Senate_TP':tp,'admission':'excluded test' if test=='1' else 'excluded wrong election' if tp is None else 'November zero setup only'})

result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'Independent identity/hash/zero-setup and hidden-test checks only; no genuine vote release or geographic compatibility established.',
        'state_election':53815,'state_Senate_contest':5075,'complete_named_counties':254,'county_candidate_cells':254*7,
        'primary_ballot_certification_county_blocks':254,'certified_declared_Senate_writeins':declared_writeins,
        'PDF_review':'Coordinator visually inspected certification cover/first county block, full one-page write-in certification and sample Senate page. Full254 county nominee blocks match; source originals retained in results-sources.',
        'PDF_preview_hashes':preview_hashes,
        'MID_semantics':'48000 plus native alphabetical ordinal, not FIPS; complete published names used for the join',
        'accidental_MID_FIPS_matches':1,'state_Home_precincts':home['PrecinctsReporting'],
        'state_county_Senate_TP_sum':sum(r['state_senate_TP'] for r in inventory),
        'state_Home_polling_reporting':home['PollingReporting'],'Harris_Senate_literal_units':1224,'Harris_state_Senate_TP':1225,
        'Clarity_observations':observations,'dependencies':dependencies,
        'limitations':['Home and county completion denominators have different unexplained scopes; neither measures votes remaining.',
                       'Harris has four vendor candidate columns versus seven named statewide candidates; write-in scope/crosswalk unestablished.',
                       'Test flags override November labels and hidden watermark; client refresh and page clocks do not establish count cadence.',
                       'No collector, votes allocated, approved 2026 boundary crosswalk or calibrated probability.']}
output=ROOT/'coordinator-setup-source-checks.json'
if output.exists():
    old=json.loads(output.read_text())
    if {k:v for k,v in old.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=old['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='dependencies'},indent=2))
