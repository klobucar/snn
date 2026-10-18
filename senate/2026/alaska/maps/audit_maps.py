"""Independent offline retained-byte/coverage audit. Standard library + pdfinfo.

No network, GIS package, mutation of geometry, or vote allocation.
Writes evidence-manifest.json, artifact-manifest.json and validation.json.
"""
from pathlib import Path
import collections
import csv
import datetime as dt
import gzip
import hashlib
from html.parser import HTMLParser
import json
import math
import re
import struct
import subprocess
from urllib.parse import urlsplit,unquote
import zipfile

ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent
ORDER=[6,9,3,8,23,29,25,30,24,34,11,35,16,7,36,2,26,15,28,4,21,27,33,10,1,12,5,17]
checks=0
def ck(test,msg):
    global checks
    checks+=1
    if not test:raise AssertionError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads((ROOT/p).read_text())
def rows(p):return list(csv.DictReader((ROOT/p).open()))
def save(p,x):(ROOT/p).write_text(json.dumps(x,indent=2)+'\n')
def positions(a):
    if a and isinstance(a[0],(int,float)):yield a
    else:
        for x in a:yield from positions(x)
class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ['href','src']:self.links.append(v)
def dbf_records(b):
    count=struct.unpack('<I',b[4:8])[0];head,length=struct.unpack('<HH',b[8:12]);fields=[]
    for start in range(32,head-1,32):
        f=b[start:start+32]
        if f[0]==13:break
        fields.append((f[:11].split(b'\0')[0].decode(),f[16]))
    for i in range(count):
        rec=b[head+i*length:head+(i+1)*length];offset=1;out={}
        ck(rec[:1]==b' ','DBF deleted row')
        for name,width in fields:out[name]=rec[offset:offset+width].decode().strip();offset+=width
        yield out

def main():
    # These are this audit's generated outputs, also linked from the index.
    # A failed/interrupted run must not leave an old pass label in place.
    save('validation.json',dict(status='audit_running'))
    if not (ROOT/'artifact-manifest.json').exists():save('artifact-manifest.json',[])
    evidence=[];failures=[]
    for mp in sorted(ROOT.rglob('*.retrieval.json')):
        m=json.loads(mp.read_text());p=ROOT/m['local_path'];b=p.read_bytes()
        ck(sha(b)==m['stored_sha256'] and len(b)==m['stored_bytes'],str(p)+' stored hash/size')
        rb=gzip.decompress(b) if p.suffix=='.gz' else b
        ck(sha(rb)==m['raw_sha256'] and len(rb)==m['raw_bytes'],str(p)+' original hash/size')
        ck(sha((ROOT/m['headers_path']).read_bytes())==m['headers_sha256'],'headers '+str(p))
        ck('default certificate validation' in m['tls_validation'],'TLS policy')
        ck(m['curl'].get('ssl_verify_result')==0,'curl TLS validation result')
        ck('T' in m['retrieved_utc'] and '+' in m['retrieved_utc'],'UTC retrieval timestamp')
        evidence.append(m)
        if m['curl_exit_code']!=0 or m['curl'].get('http_code')!=200:
            failures.append(dict(source_url=m['source_url'],http_code=m['curl'].get('http_code'),
                curl_exit_code=m['curl_exit_code'],local_path=m['local_path']))
    save('evidence-manifest.json',evidence)
    priority=json.loads((STATE/'data/turnout/priority-set.json').read_text())
    ck([int(d['native_house_district']) for d in priority['districts']]==ORDER,'exact ordered priority')
    ck(sum(d['votes'] for d in priority['districts'])==271492 and priority['statewide_votes']==338177,'priority denominator')
    ck(5*271492>=4*338177 and 5*263774<4*338177,'minimal 80 percent cutoff')
    inputs=load('checks.json')['inputs_sha256']
    for p,h in inputs.items():ck(sha((STATE/p).read_bytes())==h,'pinned upstream '+p)
    units={y:list(csv.DictReader((STATE/f'data/turnout/reporting-units-{y}.csv').open())) for y in [2024,2022]}
    for y,count in [(2024,523),(2022,522)]:
        ck(len(units[y])==len({r['source_unit_key'] for r in units[y]})==count,'all results units '+str(y))
        ck({int(r['native_house_district']) for r in units[y]}=={*range(1,41),99},'all native HDs '+str(y))
    physical={r['native_pct_id']:r for r in units[2024] if r['unit_type']=='physical_precinct'}
    with zipfile.ZipFile(ROOT/'originals/AK_Election_Precincts_2023Final.zip') as z:
        ck(z.testzip() is None,'ZIP CRCs')
        shp=z.read('Precincts.shp');shx=z.read('Precincts.shx')
        ck(struct.unpack('>I',shp[:4])[0]==9994,'SHP magic')
        ck(struct.unpack('>I',shp[24:28])[0]*2==len(shp),'SHP size')
        ck((len(shx)-100)//8==402 and (len(shx)-100)%8==0,'SHX 402 records')
        native=list(dbf_records(z.read('Precincts.dbf')))
        ck(len(native)==402 and {r['Precinct_N'][:6] for r in native}==set(physical),'ZIP/results native ID inventory')
        for member in load('archive-members.json'):
            b=z.read(member['name']);ck(len(b)==member['bytes'] and sha(b)==member['sha256'],'ZIP member hash')
        ck('Mercator_Auxiliary_Sphere' in z.read('Precincts.prj').decode(),'native CRS evidence')
    ids=load('raw/locator-ids.json');count=load('raw/locator-count.json')['count'];got=[];liveids=[]
    for i,p in enumerate(sorted((ROOT/'raw').glob('locator-features-*.json.gz'))):
        d=json.loads(gzip.decompress(p.read_bytes()));expected=sorted(ids['objectIds'])[i*50:(i+1)*50]
        batch=[f['attributes'][ids['objectIdFieldName']] for f in d['features']]
        ck(sorted(batch)==expected and not d.get('exceededTransferLimit',False),'complete batch '+p.name)
        got+=batch;liveids.extend(f['attributes']['Precinct_Number'][:6] for f in d['features'])
    ck(len(got)==len(set(got))==count==402 and sorted(got)==sorted(ids['objectIds']),'all service IDs paginated')
    ck(set(liveids)==set(physical),'current/results native ID inventory')
    inventory=rows('native-hd-inventory.csv')
    ck(len(inventory)==41 and [int(r['native_house_district']) for r in inventory]==[*range(1,41),99],'41 inventory rows')
    ck(all(r['state_fips']=='02' and not r['county_fips'] for r in inventory),'no fabricated county FIPS')
    ck(inventory[-1]['baseline2024_polygon_features']=='0' and inventory[-1]['current_locator_polygon_features']=='0','HD99 no polygon')
    compat=rows('reporting-unit-compatibility.csv')
    ck(len(compat)==1045,'1045 compatibility rows')
    for y in [2024,2022]:
        a={r['source_unit_key']:r for r in compat if int(r['election_year'])==y}
        ck(set(a)=={u['source_unit_key'] for u in units[y]},'every source key '+str(y))
        for u in units[y]:
            c=a[u['source_unit_key']]
            ck(all(c[k]==u[k] for k in ['source_label','native_pct_id','native_pct_seq_nbr','native_house_district','unit_type']),'native ID/label fidelity')
            ck(c['vote_allocation_performed']=='no','no votes allocated')
            if y==2022 or u['unit_type']!='physical_precinct':
                ck(not c['baseline2024_id_inventory_match'] and not c['current_id_inventory_match'],'administrative/year units not allocated')
    mixed=[r for r in compat if r['mixed_actual_methods']=='multiple methods in one named unit']
    ck({int(r['native_house_district']) for r in mixed}=={6,7,8,37},'four mixed early-label units retained')
    pages=rows('pdf-page-inventory.csv');byhd=collections.defaultdict(list)
    for r in pages:byhd[int(r['native_house_district'])].append(r)
    ck(len(pages)==256 and set(byhd)==set(ORDER),'all 256 physical PDF pages')
    for hd in ORDER:
        p=ROOT/f'originals/HD{hd}_May2023Final_Maps.pdf';b=p.read_bytes()
        ck(b.startswith(b'%PDF-') and b'%%EOF' in b[-1024:],'actual PDF bytes')
        info=subprocess.check_output(['pdfinfo',str(p)],text=True)
        n=int(re.search(r'^Pages:\s+(\d+)',info,re.M)[1])
        expected={k for k,v in physical.items() if int(v['native_house_district'])==hd}
        ck(len(byhd[hd])==n==len(expected),'PDF pages match physical roster '+str(hd))
        ck({r['native_precinct_id'] for r in byhd[hd]}==expected,'PDF exact precinct IDs '+str(hd))
        ck({int(r['page']) for r in byhd[hd]}==set(range(1,n+1)),'PDF no skipped pages '+str(hd))
    coverage=rows('coverage-by-vintage.csv')
    ck(len(coverage)==56 and len({(r['native_house_district'],r['vintage']) for r in coverage})==56,'28 times 2 unique coverage')
    for r in coverage:
        hd=int(r['native_house_district']);d=load(r['geojson_path']);fs=d['features']
        expected={k for k,v in physical.items() if int(v['native_house_district'])==hd}
        ck(d['type']=='FeatureCollection' and len(fs)==len(expected)==int(r['polygon_features']),'HD/vintage feature count')
        ck({f['id'] for f in fs}==expected,'HD/vintage ID coverage')
        ck(r['november2026_approval']=='unknown','approval not inferred')
        for f in fs:
            g=f['geometry'];ck(g['type'] in ['Polygon','MultiPolygon'],'polygon type')
            pos=list(positions(g['coordinates']))
            ck(bool(pos) and all(math.isfinite(x) and math.isfinite(y) and -180<=x<=180 and 45<=y<=85 for x,y,*_ in pos),'finite Alaska geographic bounds')
            rings=g['coordinates'] if g['type']=='Polygon' else [ring for poly in g['coordinates'] for ring in poly]
            ck(all(len(ring)>=4 and ring[0]==ring[-1] for ring in rings),'closed geographic rings')
    manifests=rows('manifest.csv')
    ck(len(manifests)==len({m['local_path'] for m in manifests})==210,'unique asset manifest')
    for m in manifests:
        p=ROOT/m['local_path'];b=p.read_bytes()
        ck(len(b)==int(m['bytes']) and sha(b)==m['sha256'],'manifest hash/bytes '+m['local_path'])
        ck(bool(m['source_url']) and bool(m['official_owner']) and bool(m['retrieved_utc']),'manifest provenance')
        ck('unknown' in m['approval_status'],'manifest November approval')
    visual=load('visual-review.json')
    ck(len(visual['contact_sheets_reviewed'])==28 and len(visual['representative_full_pages_reviewed'])==4,'visual review coverage')
    for r in visual['contact_sheets_reviewed']+visual['representative_full_pages_reviewed']:
        ck(sha((ROOT/r['local_path']).read_bytes())==r['sha256'],'visually reviewed bytes retained')
    link_count=0
    for p in [ROOT/'index.html',ROOT/'REPRODUCE.md',STATE/'precinct-maps.md']:
        s=p.read_text()
        if p.suffix=='.html':parser=Links();parser.feed(s);links=parser.links
        else:links=re.findall(r'\]\(([^)]+)\)',s)
        for u in links:
            if urlsplit(u).scheme or u.startswith('#'):continue
            target=(p.parent/unquote(u.split('#')[0])).resolve();link_count+=1
            ck(target.exists(),'relative link '+str(p)+' -> '+u)
    artifacts=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file():continue
        ck('__pycache__' not in p.parts and p.name!='.DS_Store','no runtime cache')
        ck(p.stat().st_size<40*1024*1024,'file below 40 MiB '+str(p))
        if p.name in ['artifact-manifest.json','validation.json']:continue
        artifacts.append(dict(local_path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
    save('artifact-manifest.json',artifacts)
    save('validation.json',dict(status='pass',checked_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        assertion_count=checks,evidence_responses=len(evidence),successful_responses=len(evidence)-len(failures),
        bounded_access_failures=failures,asset_manifest_rows=len(manifests),artifact_files_hashed=len(artifacts),
        priority_districts=ORDER,hd_vintage_rows=56,all_hd_inventory=41,reporting_units_2024=523,reporting_units_2022=522,
        official_pdf_packets=28,official_pdf_pages=256,priority_physical_precincts=256,
        statewide_baseline_gis_features=402,statewide_current_gis_features=402,current_service_batches=9,
        relative_links_checked=link_count,november2026_approval='unknown',cross_year_crosswalk_established=False,
        report_sha256=sha((STATE/'precinct-maps.md').read_bytes()),
        votes_allocated=False,geometry_defects='retained in topology-checks.json and ring-orientation-checks.json; passing artifact audit does not approve geometry'))
    print('PASS',checks,'checks;',len(evidence),'source responses;',len(failures),'bounded access failures;',link_count,'relative links')

if __name__=='__main__':main()
