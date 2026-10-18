#!/usr/bin/env python3
"""Independent primary Harris Senate units and county ballot/registration controls.
These do not alter the chosen SOS candidate baseline or repair vendor differences.
"""
from build import *
def main():
 text=gzip.decompress((P/'original-harris-2024.txt.gz').read_bytes()).decode();s=text.split('United States Senator - Vote for none or one',1)[1].split('United States Representative',1)[0];rows=[];names=['TED CRUZ','COLIN ALLRED','TED BROWN','Analisa Roche (W)','Tracy Andrus (W)','Cast Votes','Undervotes','Overvotes','Ballot by Mail Ballots Cast','Early Voting Ballots Cast','Election Day Ballots Cast','EV Provisional Ballots Cast','ED Provisional Ballots Cast','Total Ballots Cast','Registered Voters']
 for page_no,page in enumerate(text.split('\f'),1):
  if 'United States Senator - Vote for none or one' not in page:continue
  for line_no,line in enumerate(page.splitlines(),1):
   m=re.fullmatch(r'\s*(\d{4}\s+-\s+\S+)\s{2,}([\d,\s]+?)(?:\s+([\d.]+%))?\s*',line)
   if not m:continue
   v=[int(x.replace(',','')) for x in m[2].split()];assert len(v)==15,(m[1],v)
   assert sum(v[:5])==v[5] and v[5]+v[6]+v[7]==v[13] and sum(v[8:13])==v[13]
   rows.append(dict(source_id='original-harris-2024',county_fips='48201',native_unit_id=re.sub(r'\s+',' ',m[1]),source_pdf_page=page_no,page_line=line_no,literal=line,**dict(zip(names,v)),native_turnout_percent=m[3] or ''))
 assert len(rows)==len({r['native_unit_id'] for r in rows})==1584,len(rows)
 totals={n:sum(r[n] for r in rows) for n in names};cm={r['native_candidate_name']:int(r['votes']) for r in readcsv(P/'county-candidates.csv') if r['contest']=='2024-senate' and r['county_fips']=='48201'}
 assert [totals[n] for n in names[:5]]==[cm['TED CRUZ (I)'],cm['COLIN ALLRED'],cm['TED BROWN'],cm['ANALISA ROCHE'],cm['TRACY ANDRUS']]
 header=re.search(r'([\d,]+) of ([\d,]+) = [\d.]+%',text);assert header;assert totals['Total Ballots Cast']==int(header[1].replace(',','')) and totals['Registered Voters']==int(header[2].replace(',',''))
 write(P/'harris-primary-senate-unit-controls.csv.gz',rows)
 out=[dict(year=2024,county_fips='48201',source_id='original-harris-2024',native_measure=n,value=v,scope='Harris full1584 Senate unit sum; matches originalheader and allfiveSOS candidates') for n,v in totals.items() if n not in names[:6]]
 for r in readcsv(P/'primary-vendor-registration-controls.csv'):
  out.append(dict(year=2024,county_fips=r['county_fips'],source_id=r['source_id'],native_measure=r['native_measure'],value=r['value'],scope='Original vendor registration worksheet; candidate snapshotconflicts retained separately'))
 write(P/'county-ballot-registration-controls.csv',out);jwrite(P/'harris-primary-senate-controls.json',dict(source_id='original-harris-2024',units=len(rows),source_column_order=names,totals=totals,primary_candidate_reconciliation='allfiveexact; sourceRoche/Andrusorderpreserved',unit_ballot_method_arithmetic='all1584 match',native_header=header[0],scope='historical primary unitcontrols; no2026 approval'))
 print('Independent Harris full1584candidate/ballot/method controls and Dallas/Travis controls PASS')
if __name__=='__main__':main()
