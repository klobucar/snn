#!/usr/bin/env python3
"""Independent original vendor controls, cell reconciliation and PDF unit evidence.
Full primary PDF text retained. Presence checks do not certify every parsed vote.
"""
from build import *
import zipfile,xml.etree.ElementTree as E

def main():
 ns={'s':'urn:schemas-microsoft-com:office:spreadsheet'};sn='{'+ns['s']+'}';records=[];checks=[];controls=[];rawmap={};unitrows=[]
 cm={(r['county_fips'],r['native_candidate_name']):int(r['votes']) for r in readcsv(P/'county-candidates.csv') if r['contest']=='2024-senate'}
 for county,fips in [('dallas','48113'),('travis','48453')]:
  source=f'original-{county}-2024';z=zipfile.ZipFile(io.BytesIO(raw(PEER,source)));root=E.fromstring(z.read('detail.xls'));sheets=root.findall('s:Worksheet',ns)
  for ws in sheets:
   name=ws.attrib[sn+'Name'];rows=ws.findall('s:Table/s:Row',ns);values=[[d.text or '' for d in r.findall('s:Cell/s:Data',ns)] for r in rows]
   for rn,vals in enumerate(values,1):rawmap[(source,name,rn)]=vals
   if name not in ['Registered Voters','2','3']:continue
   first=0 if name=='Registered Voters' else 2;headers=values[first];data=values[first+1:];assert data[-1][0]=='Total:';data_rows=data[:-1];tot=data[-1];assert all(len(r)==len(tot) for r in data_rows)
   for i,h in enumerate(headers):
    if i==0 or '%' in tot[i]:continue
    assert sum(int(r[i]) for r in data_rows)==int(tot[i]),(county,name,h)
   checks.append(dict(source_id=source,worksheet=name,units=len(data_rows),numeric_columns=len(headers)-2,source_total_row=tot,all_numeric_column_sums_match=True))
   for rn,vals in enumerate(data,first+2):
    unitrows.append(dict(source_id=source,native_worksheet=name,native_row=rn,native_unit_label=vals[0],source_values_json=json.dumps(vals,separators=(',',':')),role='source total control' if vals[0]=='Total:' else 'native unit; administrative labels retained'))
   if name=='Registered Voters':
    controls.extend(dict(source_id=source,county_fips=fips,native_measure=h,value=tot[i],status='vendor snapshot; not statewide SOS denominator') for i,h in enumerate(headers) if i>0);continue
   total_cols=[i for i,h in enumerate(headers) if h=='Total Votes'];candidate_labels=values[1][2:-1];assert len(total_cols)==len(candidate_labels)
   for label,col in zip(candidate_labels,total_cols):
    canonical='TED CRUZ (I)' if 'Ted Cruz' in label else 'COLIN ALLRED' if 'Colin Allred' in label else 'TED BROWN' if 'Ted Brown' in label else ''
    val=int(tot[col]);pri=cm.get((fips,canonical)) if name=='3' and canonical else None
    if name=='3' and label=='Write-in':pri=sum(v for (fk,n),v in cm.items() if fk==fips and n in ['TRACY ANDRUS','ANALISA ROCHE'])
    records.append(dict(source_id=source,county_fips=fips,native_contest=values[0][0],native_candidate=label,native_total_column=col+1,vendor_votes=val,sos_primary_votes=pri if pri is not None else '',vendor_minus_sos=val-pri if pri is not None else '',comparison_scope='generic versus named valid write-ins; incompatible universes' if label=='Write-in' else 'named candidate; conflicting source vintage' if pri is not None else 'separate presidential vendor snapshot',vendor_contest_total=tot[-1]))
    # Each candidate's methods occupy the contiguous block since the preceding total.
   prev=1
   for col in total_cols:
    assert all(sum(int(v) for v in row[prev+1:col])==int(row[col]) for row in data_rows),(county,name,col)
    prev=col
 # Independent raw XML equality for every shared vendor row, including registration and totalcontrols.
 with gzip.open(PEER/'primary-native-records.csv.gz','rt') as f:peer=list(csv.DictReader(f))
 diff=[];n=0
 for r in peer:
  if r['source_id'] not in ['original-dallas-2024','original-travis-2024']:continue
  key=(r['source_id'],r['source_worksheet'],int(r['source_row']));n+=1
  if rawmap.get(key)!=json.loads(r['source_values_json']):diff.append(dict(key=key,field='raw native values'))
 write(P/'primary-vendor-candidate-conflicts.csv',records);write(P/'primary-vendor-registration-controls.csv',controls);write(P/'primary-vendor-selected-unit-rows.csv.gz',unitrows)
 # Independently extract allpages from the actual primary originals; keep the text compressed.
 evidence=[];pdfcounts=[]
 with gzip.open(PEER/'primary-native-units.csv.gz','rt') as f:peerunits=list(csv.DictReader(f))
 for county in ['harris','bexar','angelina','midland']:
  source=f'original-{county}-2024';text=pdftext(PEER,source);(P/(source+'.txt.gz')).write_bytes(gzip.compress(text.encode(),mtime=0));pages=text.split('\f');native={}
  patterns={'harris':r'^\s*(\d{4}\s*-\s*\S+)\s{2,}\d','bexar':r'^\s*(\d+\s+BS\s+\d+)\s*$','angelina':r'^\s*(Precinct\s+\S+)\s*$','midland':r'^\s*(\d+[A-Z]?)\s{2,}[\d,]'}
  for page_no,page in enumerate(pages,1):
   for line_no,line in enumerate(page.splitlines(),1):
    m=re.search(patterns[county],line)
    if m:
     label=re.sub(r'\s+',' ',m[1].strip());native.setdefault(label,(page_no,line_no,line))
  for label,(pg,ln,line) in native.items():evidence.append(dict(source_id=source,native_unit_id=label,pdf_page=pg,page_line=ln,literal=line,status='literal primary reporting label; no polygon/2026 matching'))
  relevant=[u for u in peerunits if u['source_id']==source];absent=[]
  for u in relevant:
   lab=u['native_unit_id'];pattern=r'(?m)^\s*'+r'\s+'.join(re.escape(x) for x in lab.split())+r'(?:\s{2,}|\s*$)'
   if not re.search(pattern,text):absent.append(lab)
  pdfcounts.append(dict(source_id=source,pages=len([p for p in pages if p.strip()]),independently_observed_labels=len(native),peer_units_checked=len(relevant),peer_label_absent=absent,scope='allpages label presence only; fullcandidate/method tablecertification not claimed'))
 write(P/'primary-pdf-unit-identities.csv',evidence);jwrite(P/'primary-unit-audit.json',dict(vendor_column_and_method_checks=checks,vendor_peer_rows_compared=n,vendor_peer_differences=diff,pdf_checks=pdfcounts,scope='Primary originals remain conflicting observations; no residual allocation or newer-vintage inference'))
 print('Primary vendor rows compared',n,'diff',len(diff),'PDF labels',len(evidence));assert not diff,diff[:3]
if __name__=='__main__':main()
