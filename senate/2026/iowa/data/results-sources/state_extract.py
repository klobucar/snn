#!/usr/bin/env python3
"""Offline native current-source identities, all source-view positions and ballot context."""
import collections,csv,gzip,io,json,re,zipfile
import xml.etree.ElementTree as E
import research as r
def main():
 m=r.ledger();by={x['id']:x for x in m};priority=json.loads((r.STATE/'data/turnout/priority-set.json').read_text());counties={x['county']:x for x in priority['all_counties']}
 # Every view link/resource occurrence and PDF layout-line position, including duplicates.
 records=[];identities=[]
 for a in m:
  if not a.get('parts'):
   identities.append({'source_id':a['id'],'format':'no_response_entity','inspection_status':'transport_failure','status':a.get('status'),'error':a.get('error'),'url':a['url'],'source_view_occurrences':0,'november_2026_live_feed_approved':False});continue
  b=r.raw(a);fmt='other';txt=''
  if b.startswith(b'%PDF'):fmt='PDF';p=r.ROOT/'extracts'/(a['id']+'.txt');txt=p.read_text() if p.exists() else ''
  elif a.get('view_path'):fmt='HTML';v=json.loads((r.ROOT/a['view_path']).read_text());txt=v['text']
  elif b.startswith(b'PK'):fmt='ZIP'
  else:
   try:json.loads(b);fmt='JSON'
   except (ValueError,UnicodeDecodeError):pass
  rows=0
  if a.get('view_path'):
   for kind in ['links','resources']:
    for p in v[kind]:records.append({'source_id':a['id'],'context':'HTML_'+kind,**p});rows+=1
  if fmt=='PDF':
   for pg,t in enumerate(txt.split('\f'),1):
    for ln,line in enumerate(t.splitlines(),1):records.append({'source_id':a['id'],'context':'PDF_pdftotext_layout_line','physical_page':pg,'line':ln,'literal_line':line});rows+=1
  route_ids=re.findall(r'/IA/(?:([^/]+)/)?(\d+)(?:/|$)',a.get('final_url',''))
  dates=sorted(set(re.findall(r'\b(?:\d{1,2}/\d{1,2}/20\d\d|(?:November|June)\s+\d{1,2},?\s+20\d\d)\b',txt)))
  evidence='response_'+str(a.get('status'))
  if a.get('status')==200:
   if 'PDF.js viewer' in txt:evidence='viewer_shell_payload_unproven'
   elif re.search(r'dog.application|dog-license|gift.certificat|birth.certificat|death.certificat|measles',a['url']+' '+a.get('link_label',''),re.I):evidence='retained_rejected_irrelevant_publication'
   elif 'Search/Results' in a['url'] or 'calendar.aspx' in a['url']:evidence='retained_navigation_not_election_results'
   elif 'strawpoll' in a['url']:evidence='rejected_straw_poll_not_official_election'
   elif 'electionresults' in a['url'] and fmt=='HTML':evidence='app_shell_election_identity_requires_payload'
   elif fmt=='PDF':
    evidence='actual_PDF_full_layout_text_retained' if txt.strip() else 'image_only_PDF_text_empty_render_review_required'
    qa=r.ROOT/'visual-ballot-checks.json'
    if qa.exists() and a['id'] in {x['source_id'] for x in json.loads(qa.read_text())}:evidence='actual_PDF_visually_verified_render_source_hash_pinned'
   elif fmt=='JSON':
    o=json.loads(b);evidence='JSON_error' if isinstance(o,dict) and 'error' in o else 'native_JSON'
   else:evidence='publication_view_not_numeric_feed'
  identities.append({'source_id':a['id'],'format':fmt,'inspection_status':evidence,'status':a.get('status'),'url':a['url'],'original_sha256':a.get('original_sha256'),'source_view_occurrences':rows,'route_ids_not_fips_or_verified_contest_ids':route_ids,'literal_election_dates_in_view':dates,'source_time_policy':'HTTP Date/Last-Modified and fetch UTC are transport/CMS evidence, not votes-as-of time. Native printed clocks retained separately.','november_2026_live_feed_approved':False})
 (r.ROOT/'source-view-position-inventory.jsonl.gz').write_bytes(gzip.compress(b''.join((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode() for x in records),mtime=0));r.dump(r.ROOT/'source-identity-inventory.json',identities)
 a=by['vendor-current-xml'];z=zipfile.ZipFile(io.BytesIO(r.raw(a)));root=E.fromstring(z.read('detail.xml'));selected=[];primary=[]
 for ci,ct in enumerate(root.findall('Contest'),1):
  if not ct.get('text','').startswith('United States Senator'):continue
  methods=collections.Counter();choices=[]
  for qi,ch in enumerate(ct.findall('Choice'),1):
   choices.append(dict(ch.attrib));total=0
   for vi,v in enumerate(ch.findall('VoteType'),1):
    parts=v.findall('County');assert len(parts)==99
    assert {n.get('name') for n in parts}==set(counties)
    assert sum(int(n.get('votes')) for n in parts)==int(v.get('votes'));total+=int(v.get('votes'))
    for i,n in enumerate(parts,1):
     name=n.get('name');primary.append({'source_id':a['id'],'source_xml_path':f'Contest[{ci}]/Choice[{qi}]/VoteType[{vi}]/County[{i}]','county_fips':counties[name]['county_fips'],'native_county_attributes':dict(n.attrib),'contest_attributes':dict(ct.attrib),'choice_attributes':dict(ch.attrib),'method_attributes':dict(v.attrib)})
    methods[v.get('name')]+=int(v.get('votes'))
   assert total==int(ch.get('totalVotes'))
  selected.append({'contest_position':ci,'attributes':dict(ct.attrib),'choices':choices,'method_candidate_generic_sums':dict(methods)})
 st=json.loads(r.raw(by['vendor-current-status']));settings=json.loads(r.raw(by['vendor-current-settings']));parts=settings['settings']['electiondetails']['participatingcounties']
 assert len(parts)==99
 roster=[]
 for i,s in enumerate(parts):
  label,eid,version,clock,template=s.split('|');name=label.replace('_',' ');assert name in counties
  roster.append({'source_id':'vendor-current-settings','source_json_pointer':'/settings/electiondetails/participatingcounties/'+str(i),'literal':s,'county':name,'county_fips':counties[name]['county_fips'],'native_election_id':eid,'native_version':version,'source_clock':clock,'template':template})
 r.dump(r.ROOT/'primary-2026-identity-schema.json',{'election_name':root.findtext('ElectionName'),'election_date':root.findtext('ElectionDate'),'source_clock':root.findtext('Timestamp'),'region':root.findtext('Region'),'election_id':'126082','version':'377216','scope':'June primary only; all99 county names independently matched to canonical contract, no November ID inferred','senate_contests':selected,'native_status_fields':{k:{'type':type(v).__name__,'length':len(v) if isinstance(v,list) else None} for k,v in st.items()},'county_roster':roster,'status_reported_sum':sum(st['PX']),'status_participating_sum':sum(st['PY'])})
 (r.ROOT/'primary-2026-native-positions.jsonl.gz').write_bytes(gzip.compress(b''.join((json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode() for x in primary),mtime=0))
 # October absentee administration: preserve full layout positions, methods, blanks and clocks.
 admin=[];summary=[]
 for id in ['sos-2026-absentee-county','sos-2026-absentee-state']:
  t=(r.ROOT/'extracts'/(id+'.txt')).read_text();clocks=[]
  for pi,page in enumerate(t.split('\f'),1):
   times=re.findall(r'Data Pulled:[^\n]+',page);dates=re.findall(r'\b\d{1,2}/\d{1,2}/2026\b',page)
   if not page.strip():continue
   clocks.append({'physical_page':pi,'literal_clocks':times,'literal_dates':dates})
   for li,line in enumerate(page.splitlines(),1):
    match=re.match(r'^\s*(.+?)\s{2,}(\d+)\s+(\d+)(?:\s+(\d+))?\s*$',line)
    if not match:continue
    label=match[1].strip();entry={'source_id':id,'physical_page':pi,'line':li,'label_literal':label,'requested':int(match[2]),'issued':int(match[3]),'received':int(match[4]) if match[4] is not None else None,'raw_line':line,'page_clock_context':clocks[-1]}
    if label in counties:entry['county_fips']=counties[label]['county_fips']
    admin.append(entry)
  summary.append({'source_id':id,'page_clocks':clocks,'grand_total_rows':[x for x in admin if x['source_id']==id and x['label_literal']=='Grand Total']})
 countyrows=[x for x in admin if x.get('county_fips')];assert len(countyrows)==99 and len({x['county_fips'] for x in countyrows})==99
 assert [sum(x[k] or 0 for x in countyrows) for k in ['requested','issued','received']]==[176012,176014,33418]
 r.dump(r.ROOT/'absentee-2026-native-rows.json',admin);r.dump(r.ROOT/'absentee-2026-controls.json',summary)
 r.dump(r.ROOT/'state-extraction-validation.json',{'status':'pass_with_source_gaps','source_identity_records':len(identities),'full_view_position_records':len(records),'primary_senate_county_method_cells':len(primary),'primary_county_roster':len(roster),'absentee_county_rows':99,'absentee_state_control':[176012,176014,33418],'november_2026_result_eids_observed':[],'missing_november_fields':['Senate contest key','choice keys','counted candidate totals','method release status','authoritative remaining votes','approved unit roster','tested upload format','demonstrated publication cadence']})
 print('PASS current identity/positions',len(records),'primary native cells',len(primary),'absentee county99')
if __name__=='__main__':main()
