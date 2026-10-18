#!/usr/bin/env python3
"""Independent coordinator PDF preflight; does not approve worker geography/dispatch."""
from pathlib import Path
import datetime,gzip,hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parent
NEWS=ROOT/'news'
manifest={r['id']:r for r in json.loads((NEWS/'manifest.json').read_text())}
specs={
    '2024-president':('2024','President and Vice President',11,['Harris/Walz','Trump/Vance','Oliver/ter Maat','Ayyadurai/Ellis','De la Cruz/Garcia','Stodden/Cholensky','Kennedy/Shanahan','Write-in'],0,1),
    '2022-senate':('2022','United States Senator',6,['Grassley','Franken','Write-in'],1,0),
    '2020-senate':('2020','United States Senator',8,['Ernst','Greenfield','Stewart','Herzog','Write-in'],1,0)}
results={}
for contest,(year,title,width,labels,d_index,r_index) in specs.items():
    meta=manifest['sos-'+year+'-canvass'];stored=(NEWS/meta['asset']).read_bytes();body=gzip.decompress(stored)
    assert meta['status']==200 and body.startswith(b'%PDF-')
    assert len(body)==meta['bytes'] and hashlib.sha256(body).hexdigest()==meta['raw_sha256']
    assert hashlib.sha256(stored).hexdigest()==meta['stored_sha256']
    text=subprocess.run(['pdftotext','-layout','-','-'],input=body,check=True,stdout=subprocess.PIPE).stdout.decode()
    section=text.split(title,1)[1].split('United States Representative District 1',1)[0]
    county=None;county_rows=[];state_rows=[];footer=False
    for lineno,line in enumerate(section.splitlines(),1):
        clean=line.lstrip('\f')
        if clean.startswith('TOTAL '):footer=True
        if clean and clean[0].isalpha() and re.search(r'\s\d[\d,]*\s',clean):
            prefix=re.split(r'\s+\d',clean,maxsplit=1)[0].strip()
            prefix=re.sub(r'\s+Election(?:\s+Day)?$','',prefix).strip()
            # Page is also an actual county; exclude only a complete pagination label.
            if prefix not in ('TOTAL','Total') and not re.match(r'^Page \d+ of',prefix):county=prefix
        match=re.fullmatch(r'\s*Total\s+([\d, ]+)\s*',line)
        if not match:continue
        numbers=[int(n.replace(',','')) for n in match[1].split()]
        if len(numbers)!=width:continue
        row={'native_county':county,'column_counts':numbers,'section_text_line':lineno,'raw_line':line}
        (state_rows if footer else county_rows).append(row)
    # The 2020 report has a final statewide total, without the two method footer rows.
    if year=='2020':
        assert not state_rows and len(county_rows)==100
        state_rows=[county_rows.pop()]
    assert len(county_rows)==len({r['native_county'] for r in county_rows})==99
    assert len(state_rows)==1
    control=state_rows[0]['column_counts']
    assert list(map(sum,zip(*(r['column_counts'] for r in county_rows))))==control
    for row in county_rows:
        counts=row['column_counts'];assert sum(counts[:-1])==counts[-1]
        row.update(candidate_writein_votes=sum(counts[:-3]),under_votes=counts[-3],over_votes=counts[-2],reported_contest_total=counts[-1],d=counts[d_index],r=counts[r_index])
    assert sum(control[:-1])==control[-1]
    results[contest]={'primary_url':meta['url'],'original_sha256':meta['raw_sha256'],'candidate_column_labels_shorthand':labels,
                      'source_column_scope':'Named columns plus generic Write-in; final three columns are under, over, reported contest Total.',
                      'state_control':control,'counties':county_rows}
assert all({r['native_county'] for r in item['counties']}=={r['native_county'] for r in results['2024-president']['counties']} for item in results.values())
assert any(r['native_county']=='Page' for r in results['2024-president']['counties'])
ranked=sorted(results['2024-president']['counties'],key=lambda r:(-r['candidate_writein_votes'],r['native_county']))
denominator=sum(r['candidate_writein_votes'] for r in ranked);cumulative=0;priority=[]
for row in ranked:
    if cumulative*5>=denominator*4:break
    priority.append(row['native_county']);cumulative+=row['candidate_writein_votes']
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'Coordinator primary county PDF preflight only; independent worker candidate/method/native-unit controls and priority reconciliation remain required before second-wave dispatch.',
        'county_count':99,'primary_county_contest_rows':297,'source_column_cells':99*(11+6+8),
        'candidate_writein_denominator':denominator,'top15_candidate_writein_votes':sum(r['candidate_writein_votes'] for r in ranked[:15]),
        'provisional_priority_native_names':priority,'provisional_priority_count':len(priority),'provisional_priority_votes':cumulative,
        'provisional_preceding_votes':cumulative-ranked[len(priority)-1]['candidate_writein_votes'],'contests':results,
        'limits':['No finer reporting-unit inventory, FIPS join or November boundary approval established.',
                  'Reported Total includes undervotes and overvotes; it is not the candidate/write-in ranking denominator.',
                  'Candidate labels here are shorthand; primary worker must preserve full source identities, write-in scope and provenance.',
                  'County Page must not be removed as a pagination marker.']}
output=ROOT/'coordinator-primary-preflight.json'
if output.exists():
    old=json.loads(output.read_text())
    if {k:v for k,v in old.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=old['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='contests'},indent=2))
