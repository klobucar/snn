#!/usr/bin/env python3
"""Retain source-native row identities and all fields, even ambiguous/central units.
This layer is evidence, never a replacement for primary reconciled county values.
"""
from build import *
import zipfile,xml.etree.ElementTree as ET
NORM=lambda s:re.sub('[^A-Z0-9]','',s.upper())
OFFICES={'2024':{'USSENATE','USSENATOR','UNITEDSTATESSENATOR','PRESIDENT','PRESIDENTANDVICEPRESIDENT','PRESIDENTVICEPRESIDENT'},'2020':{'USSENATE','USSENATOR','UNITEDSTATESSENATOR'},'2022':{'GOVERNOR','GOVERNORWRITEIN','GOVERNOR1'}}
MEASURES={'REGISTEREDVOTERS','BALLOTSCAST','BALLOTSCASTTOTAL','VOTERSCAST','VOTERTURNOUT','BALLOTSCASTBLANK'}

def run():
 base=readcsv(DATA/'county-baselines.csv');fm={NORM(r['county_name']):r['county_fips'] for r in base};fm.update({'HILDALGO':'48215','LASALLE':'48283'})
 units=[];anomalies=[];diagnostics=[];rec_counts={};peer_checks={};files=[(p.name.split('.')[0],p,'2024') for p in sorted((PEER/'raw').glob('oe2024-*.body.gz'))]+[(f'oe-tx{y}',PEER/'raw'/f'oe-tx{y}.body.gz',y) for y in ['2020','2022']]
 for year in ['2024','2020','2022']:
  peerpath=PEER/f'native-records-{year}.csv.gz'
  with gzip.open(peerpath,'rt') as f:peerrows={(r['source_id'],int(r['source_row'])):r for r in csv.DictReader(f)}
  seenpeer=set();counts=collections.Counter();mismatches=[]
  with gziptext(P/f'native-cells-{year}.jsonl.gz') as output:
   for source,path,y in files:
    if y!=year:continue
    us={};duplicates=collections.Counter();methods=[];offices=collections.Counter();filecounty=source.removeprefix('oe2024-').replace('_',' ');filefips=fm.get(NORM(filecounty),'') if year=='2024' else '';n=0;selected=0;roles=collections.Counter()
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
     for ordinal,r in enumerate(csv.DictReader(f),2):
      n+=1;cn=r.get('county','');unit=r.get('precinct','');office=r.get('office','');of=NORM(office);offices[office]+=1
      if cn=='county' and office=='office':anomalies.append(dict(source_id=source,source_row=ordinal,source_fields=r,reason='repeated CSV header, not a reporting unit'));continue
      literalFIPS=fm.get(NORM(cn),'');mapped=literalFIPS or (filefips if cn=='' else '');mapping='literal canonical/explicit Hildalgo alias' if literalFIPS else 'blank county mapped from Angelina filename' if cn=='' and source=='oe2024-angelina' else 'unresolved'
      conflict=bool(filefips and literalFIPS and filefips!=literalFIPS)
      key=(cn,unit)
      if key not in us:us[key]=dict(source_id=source,year=year,native_county_name=cn,native_unit_id=unit,native_unit_key=json.dumps([source,cn,unit],separators=(',',':')),literal_county_fips=literalFIPS,file_county_fips=filefips,mapped_county_fips=mapped,mapping_basis=mapping,file_literal_county_conflict=int(conflict),first_source_row=ordinal,source_rows=0,offices=set(),type_status='source reporting/ballot-style identity; physical/administrative/central type unverified; no polygon equivalence')
      us[key]['source_rows']+=1;us[key]['offices'].add(office)
      if of not in OFFICES[year]|MEASURES:continue
      selected+=1;cnorm=NORM(r.get('candidate',''));role='candidate identity; validity not independently resolved'
      if of in MEASURES:role='registration/ballot/participation control; native label retained'
      elif any(x in cnorm for x in ['UNDERVOTE','OVERVOTE','REJECT','INVALID','UNCERTIF','UNASSIGN','NOTASSIGN','BLANK']):role='noncandidate/invalid/unassigned control'
      elif cnorm in ['TOTAL','TOTALVOTES','TOTALVOTESCAST']:role='contest total control'
      elif cnorm in ['WRITEIN','WRITEINS','WRITEINTOTAL','WRITEINTOTALS']:role='generic write-in; valid/named universe unresolved'
      roles[role]+=1
      cell=dict(source_id=source,source_row=ordinal,year=year,native_county_name=cn,native_unit_id=unit,mapped_county_fips=mapped,literal_county_fips=literalFIPS,file_county_fips=filefips,file_literal_county_conflict=int(conflict),record_role=role,source_fields=r)
      output.write(json.dumps(cell,separators=(',',':'),ensure_ascii=False)+'\n')
      pk=(source,ordinal)
      if pk in peerrows:
       pr=peerrows[pk];seenpeer.add(pk)
       if json.loads(pr['source_fields_json'])!=r:mismatches.append(dict(source_id=source,source_row=ordinal,field='source_fields'))
       if pr['source_county_name']!=cn or pr['native_unit_id']!=unit:mismatches.append(dict(source_id=source,source_row=ordinal,field='native_identity'))
      duplicates[(cn,unit,office,r.get('district',''),r.get('candidate',''),r.get('party',''))]+=1
      mm={k:v for k,v in r.items() if k not in ['county','precinct','office','district','candidate','party','votes','id']};nums=[int(v) for v in mm.values() if str(v).lstrip('-').isdigit()]
      try:
       num=int(r.get('votes',''))
       if nums and sum(nums)!=num:methods.append(dict(source_row=ordinal,total=num,numeric_method_sum=sum(nums),native_method_fields=mm))
      except (ValueError,TypeError):pass
    for u in us.values():u['offices']=json.dumps(sorted(u['offices']),separators=(',',':'));units.append(u)
    counts['units']+=len(us);counts['selected_rows']+=selected;counts['sources']+=1
    diagnostics.append(dict(source_id=source,year=year,rows=n,selected_rows=selected,units=len(us),offices=dict(offices),roles=dict(roles),duplicate_candidate_keys=[dict(key=list(k),occurrences=v) for k,v in duplicates.items() if v>1],method_nonadditive_rows=methods,literal_counties=sorted({u['native_county_name'] for u in us.values()}),file_literal_county_conflict=any(u['file_literal_county_conflict'] for u in us.values())))
  counts['peer_rows_compared']=len(seenpeer);counts['peer_rows_missing_from_own']=len(set(peerrows)-seenpeer);counts['peer_raw_field_mismatches']=len(mismatches);rec_counts[year]=dict(counts);peer_checks[year]=dict(counts=counts,mismatches=mismatches,peer_sha256=sha(peerpath.read_bytes()))
 write(P/'native-units.csv.gz',units);jwrite(P/'native-source-diagnostics.json',diagnostics);jwrite(P/'native-source-anomalies.json',anomalies);jwrite(P/'native-peer-reconciliation.json',peer_checks)
 # Native inventories cover every nonheader row/office, including units absent in the selected contest.
 with gzip.open(PEER/'native-reporting-units.csv.gz','rt') as f:pu=list(csv.DictReader(f))
 ours={(u['source_id'],u['native_county_name'],u['native_unit_id']):u for u in units};theirs={(u['source_id'],u['source_county_name'],u['native_unit_id']):u for u in pu}
 invdiff=[]
 for k in set(ours)|set(theirs):
  if k not in ours or k not in theirs:invdiff.append(dict(key=k,status='missing'))
  elif str(ours[k]['source_rows'])!=theirs[k]['source_rows']:invdiff.append(dict(key=k,status='row_count_difference'))
 jwrite(P/'native-coverage.json',dict(years=rec_counts,inventory_keys_compared=len(set(ours)|set(theirs)),inventory_mismatches=invdiff,scope='Every observed source identity retained; sourcefilename versus literalcounty conflicts remain; not all254county native precinct ground truth',county_coverage={y:sorted({u['mapped_county_fips'] for u in units if u['year']==y}) for y in rec_counts}))
 # TLC remains a derived VTD layer; preserve allfive originals and all measures.
 news=json.loads((DATA/'news/manifest.json').read_text());tlc=[];differences=[]
 mappings={'tlc-2024-senate-vtd':('2024-senate',{'AllredD_24G_U.S. Sen':'COLIN ALLRED','AndrusW_24G_U.S. Sen':'TRACY ANDRUS','BrownL_24G_U.S. Sen':'TED BROWN','CruzR_24G_U.S. Sen':'TED CRUZ (I)','RocheW_24G_U.S. Sen':'ANALISA ROCHE'}),'tlc-2024-president-vtd':('2024-president',{'HarrisD_24G_President':'KAMALA D. HARRIS/TIM WALZ','OliverL_24G_President':'CHASE OLIVER/MIKE TER MAAT','SteinG_24G_President':'JILL STEIN/RUDOLPH WARE','TrumpR_24G_President':'DONALD J. TRUMP/JD VANCE'}),'tlc-2022-governor-vtd':('2022-governor',{'AbbottR_22G_Governor':'GREG ABBOTT (I)',"O'RourkeD_22G_Governor":"BETO O'ROURKE",'TippettsL_22G_Governor':'MARK TIPPETTS','BarriosG_22G_Governor':'DELILAH BARRIOS'})}
 cand=readcsv(P/'county-candidates.csv');cm={(r['contest'],r['county_fips'],r['native_candidate_name']):int(r['votes']) for r in cand}
 for m in news:
  if not m['id'].startswith('tlc-') or not m['id'].endswith('-vtd'):continue
  rows=list(csv.DictReader(io.StringIO(gzip.decompress((DATA/'news'/m['asset']).read_bytes()).decode('utf-8-sig'))));ag=collections.Counter();keys=[]
  for r in rows:
   k=(r['CNTYVTD'],r['VTDKEY']);keys.append(k);fips='48'+r['CNTYVTD'][:3];tlc.append(dict(source_id=m['id'],county_fips=fips,CNTYVTD=r['CNTYVTD'],VTDKEY=r['VTDKEY'],geography='TLC derived2024 VTD vintage; not authenticated native precinct',source_fields_json=json.dumps(r,separators=(',',':'))))
   for name,v in r.items():
    if name not in ['CNTYVTD','VTDKEY'] and str(v).lstrip('-').isdigit():ag[(fips,name)]+=int(v)
  assert len(keys)==len(set(keys))==9712
  for (fips,name),v in sorted(ag.items()):
   contest,mp=mappings.get(m['id'],('',{}));canonical=mp.get(name,'');primary=cm.get((contest,fips,canonical));scope='same named candidate' if primary is not None else 'measure not available in primary county canvass'
   if 'Write-In' in name:
    primary=sum(int(r['votes']) for r in cand if r['contest']==contest and r['county_fips']==fips and r['native_party']=='WRI');scope='generic write-in compared with named valid write-ins; universes differ'
   differences.append(dict(source_id=m['id'],county_fips=fips,source_field=name,derived=v,primary=primary if primary is not None else '',derived_minus_primary=v-primary if primary is not None else '',comparison_scope=scope))
 write(P/'tlc-vtd-cells.csv.gz',tlc);write(P/'tlc-county-disagreements.csv',differences)
 # Primary vendor XML: allworksheet row/cell attributes retained; contest unit/candidate subsets derived below.
 ns={'s':'urn:schemas-microsoft-com:office:spreadsheet'};sn='{'+ns['s']+'}';xmlrows=[];xmlunits=[];xmlcounts=[]
 for county in ['dallas','travis']:
  source=f'original-{county}-2024';z=zipfile.ZipFile(io.BytesIO(raw(PEER,source)));assert z.namelist()==['detail.xls'];root=ET.fromstring(z.read('detail.xls'));u=set()
  for wi,ws in enumerate(root.findall('s:Worksheet',ns),1):
   wn=ws.attrib[sn+'Name'];rr=ws.findall('s:Table/s:Row',ns)
   for rn,row in enumerate(rr,1):
    cells=[dict(attributes=c.attrib,data=[dict(attributes=d.attrib,text=d.text) for d in c.findall('s:Data',ns)]) for c in row.findall('s:Cell',ns)];vals=[(c.find('s:Data',ns).text or '') if c.find('s:Data',ns) is not None else '' for c in row.findall('s:Cell',ns)]
    xmlrows.append(dict(source_id=source,worksheet_index=wi,native_worksheet=wn,native_row=rn,row_attributes=row.attrib,cells=cells))
    if vals and vals[0] and len(vals)>2 and vals[0]!='Precinct' and wi>1:
     u.add((wn,vals[0]));xmlunits.append(dict(source_id=source,native_worksheet=wn,native_row=rn,native_unit_label=vals[0],source_values_json=json.dumps(vals,separators=(',',':')),status='raw vendor table label; no dedup or precinctpolygon assertion'))
   if wi in [3,4]:xmlcounts.append(dict(source_id=source,native_worksheet=wn,first_rows=[[d.text or '' for d in r.findall('s:Cell/s:Data',ns)] for r in rr[:12]],last_rows=[[d.text or '' for d in r.findall('s:Cell/s:Data',ns)] for r in rr[-3:]]))
 with gziptext(P/'primary-vendor-xml-rows.jsonl.gz') as f:
  for r in xmlrows:f.write(json.dumps(r,separators=(',',':'))+'\n')
 write(P/'primary-vendor-table-identities.csv.gz',xmlunits);jwrite(P/'primary-vendor-inspection.json',xmlcounts)
 print('Native retained',len(units),'inventory keys;',rec_counts,'TLC',len(tlc),'XML',len(xmlrows),'rows')
if __name__=='__main__':run()
