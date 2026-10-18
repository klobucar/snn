#!/usr/bin/env python3
"""Offline inventory/audit rebuild. Reads other workers' completed evidence only."""
from research import *
from collections import Counter,defaultdict
from zoneinfo import ZoneInfo
BASE=ROOT.parent/'turnout';STATE=ROOT.parent.parent
contract=json.loads((BASE/'priority-set.json').read_text());recon=json.loads((ROOT/'authority-reconciliation.json').read_text());routes={r['native_key']:r for r in json.loads((ROOT/'municipal-route-discovery.json').read_text())};ins={r['native_key']:r for r in json.loads((ROOT/'priority-inspections.json').read_text())}
clerks=json.loads((ROOT/'current-clerk-roster.json').read_text())['rows'];voting=json.loads((ROOT/'current-voting-places.json').read_text())['rows'];directory=json.loads((ROOT/'directory-audit.json').read_text());htnames={n.upper() for pg in directory['pages'] for n in pg['names']}
bykey={r['authority_key']:r for r in clerks};requests={}
for f in (ROOT/'requests').glob('*.json'):
 if f.name.endswith('.links.json'):continue
 m=json.loads(f.read_text());requests[m['id']]=m

def norm(s):return re.sub(r'\s+',' ',s.strip().upper().replace('SAINT ','ST ').replace('ST. ','ST ').replace('PLANTATION','PLT').replace('TOWNSHIP','TWP'))
def voting_components(label):
 # The source explicitly separates the full municipality from parenthetical
 # associations. A word inside a different full name is not an association:
 # Portland must not match New Portland or South Portland.
 bare=re.split(r'\s*\(',label)[0].strip()
 components={norm(bare)}
 for group in re.findall(r'\(([^)]*)\)',label):
  for part in re.split(r'\s*(?:,|&|\band\b|\bwith\b)\s*',group,flags=re.I):
   if part.strip():components.add(norm(part))
 return components
def textfile(where,id):
 f=ROOT/where/f'{id}.txt'
 if f.exists():return f.read_text(errors='replace')
 if f.with_suffix('.txt.gz').exists():return gzip.decompress(f.with_suffix('.txt.gz').read_bytes()).decode(errors='replace')
 return ''
def bodytype(m):
 b=gzip.decompress((ROOT/m['body_path']).read_bytes())
 if m.get('status') not in (200,206):return 'failed HTTP/transport response'
 if b.startswith(b'%PDF'):return 'PDF'
 if b.startswith(b'PK'):return 'OOXML/archive'
 if b.startswith(b'<?'):return 'unexecuted public PHP source; unusable directory response'
 if b.startswith(b'\x89PNG') or b.startswith(b'\xff\xd8') or b.startswith(b'GIF8'):return 'image'
 if 'application/json' in {k.lower():v for k,v in m['headers']}.get('content-type','').lower():return 'JSON; content semantics require separate audit'
 if b'<html' in b[:2000].lower() or b'<!doctype html' in b[:2000].lower() or b'<li' in b[:2000].lower():return 'HTML/page/menu; not a verified result feed'
 return 'other public entity'
allnative=[];priorityfacts=[];edge=[]
for r in recon:
 route=routes[r['native_key']];ir=ins.get(r['native_key']);names=r['native_name'].strip().split('/');lead=norm(names[0]);context_rows=[]
 # Exact full-name components in the printed source, not substring search hits.
 for v in voting:
  components=voting_components(v['municipality'])
  if any(norm(n) in components for n in names if norm(n) not in ('TWPS','CONNOR')):context_rows.append(v)
 current_candidates=[]
 for v in context_rows:
  # A 'with' label explicitly identifies a host; a bare label with 'and' identifies its printed host.
  ma=re.search(r'\(with ([^)&]+)',v['municipality'],re.I)
  host=ma.group(1).split(' & ')[0].split(' and ')[0].strip() if ma else re.split(r'\s*\(',v['municipality'])[0].strip()
  match=[c for c in clerks if norm(c['municipality'])==norm(host)]
  for c in match:
   if c['authority_key'] not in current_candidates:current_candidates.append(c['authority_key'])
 facts={**r,'clerk_source_line_by_key':{k:bykey[k]['source_line'] for k in r['clerk_authority_keys']},'current_membership_mentions':context_rows,'current_serving_authority_candidates':current_candidates,'relationship_warning':'Current source relationships only. No split of historical combined counts, no 2026 reporting-boundary equivalence, and no legal-authority census inferred from row counts.','discovery_routes':route['discovery_routes'],'rejected_discovery_routes':route.get('rejected_discovery_routes',[]),'rejection_reason':route.get('rejection_reason'),'roster_page_source':'7ce88c366d25718425bc','current_vote_return_ids':None,'current_Senate_feed_or_candidate_ids':None,'outstanding_votes':None,'observed_count_update_cadence':None}
 pages=ir['pages'] if ir else route['route_request_ids'];facts['tested_request_ids']=pages
 facts['web_only_observations']=json.loads((ROOT/'web-only-observations.json').read_text()).get(str(r['rank']))
 facts['test_responses']=[{'request_id':id,'status':requests[id].get('status'),'publisher_url':requests[id]['publisher_url'],'request_url':requests[id]['request_url'],'final_url':requests[id].get('final_url'),'retrieved_utc':requests[id]['retrieved_utc'],'response_kind':bodytype(requests[id]),'complete_entity':requests[id]['complete'],'source_clock_is_http_file_clock':dict((k.lower(),v) for k,v in requests[id].get('headers',[])).get('last-modified')} for id in pages]
 facts['downloads']=ir['downloads'] if ir else []
 for d in facts['downloads']:
  id=d.get('request_id')
  if not id:continue
  m=requests[id];s=textfile('extracted',id);ocr=False
  if len(s.strip())<40:s=textfile('ocr',id);ocr=bool(s)
  d['status']=m.get('status');d['response_kind']=bodytype(m);d['parsed_text_chars']=len(s.strip());d['text_scope']='first-page OCR only' if ocr else ('PDF cached text extraction' if s else 'not text-parsed; original bytes retained')
  d['detected_source_terms']={name:bool(re.search(pat,s,re.I)) for name,pat in {'absentee':r'\babsentee','ward_precinct':r'\bward|\bprecinct','test':r'\bTEST\b','unofficial_preliminary':r'\bunofficial|\bpreliminary','official_certified':r'\bofficial|\bcertified','Senate_2024_roster':r'Kouzounas.*Demi|Demi.*Kouzounas','round':r'\bround','remaining':r'\bremaining|\boutstanding'}.items()}
  d['source_clock_candidates']=[z.strip() for z in s.splitlines() if re.search(r'report created|generated|updated|\b\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM)',z,re.I)][:5]
  d['source_timezone']=None;d['current_November_result_payload']=False
 successful=[m for m in facts['test_responses'] if m['status']==200 and 'PHP source' not in m['response_kind']]
 usable_docs=[d for d in facts['downloads'] if d.get('status',d.get('http_status'))==200 and d.get('response_kind') in ('PDF','image','OOXML/archive')]
 facts['inspection_outcome']='state administration and publication schemas inspected; no current November counts' if r['rank']==22 else ('official route/document response retained; no current November feed established' if successful or usable_docs else 'direct route blocked/unavailable after documented repair attempts; SOS contact/roster retained')
 if not r['priority']:facts['inspection_outcome']='native unit inventoried against current SOS rosters; municipal website is discovery-level only, current election channel not deeply validated'
 facts['verified_current_result_flags']={'test':None,'official':None,'completion':None,'precincts_reported':None,'precincts_total':None,'remaining_ballots':None,'round':None}
 facts['advertised_vote_refresh_seconds']=None
 allnative.append(facts)
 if r['priority']:priorityfacts.append(facts)
 for k in set(r['clerk_authority_keys']+current_candidates):edge.append({'native_key':r['native_key'],'authority_key':k,'relationship':'direct/component clerk label or explicit current voting-place association; no count allocation'})
(ROOT/'native-unit-inventory.json').write_text(json.dumps(allnative,indent=2)+'\n')
(ROOT/'priority-field-audit.json').write_text(json.dumps(priorityfacts,indent=2)+'\n')
# Full current rosters survive even when no historical native row maps to them.
contact_groups=defaultdict(list)
for c in clerks:
 key=(c['clerk_name'],c['clerk_address1'],c['clerk_phone'])
 if c['clerk_name']:contact_groups[key].append(c['authority_key'])
for c in clerks:
 c['in_HTML_roster_normalized']=c['municipality'].upper() in htnames;c['baseline_native_keys']=[e['native_key'] for e in edge if e['authority_key']==c['authority_key']]
 c['same_published_contact_keys']=contact_groups[(c['clerk_name'],c['clerk_address1'],c['clerk_phone'])] if c['clerk_name'] else []
 c['contact_group_warning']='Same published contact; not a claim of legal consolidation or same vote reporting unit.'
(ROOT/'current-authority-inventory.json').write_text(json.dumps(clerks,indent=2)+'\n');(ROOT/'authority-edges.json').write_text(json.dumps(edge,indent=2)+'\n')
cols=['record_type','native_key','rank','priority','native_name','historical_county_code','authority_names','clerk_names','clerk_phones','clerk_source_lines','state_source_url','municipal_publisher_urls','municipal_final_urls','tested_request_ids','tested_statuses','download_request_ids','reuse_source_ids','current_voting_place_source_rows','current_voting_place_labels','mapping_status','inspection_outcome','november_2026_contest_id','source_timezone','observed_count_update_cadence','remaining_ballots','notes']
with (ROOT.parent/'official-results-sources.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
 for x in allnative:
  cs=[bykey[k] for k in x['clerk_authority_keys']];rr=x['test_responses']
  w.writerow(dict(record_type='native historical research unit',native_key=x['native_key'],rank=x['rank'],priority=int(x['priority']),native_name=x['native_name'],historical_county_code=x['county_code'],authority_names=' | '.join(c['municipality'] for c in cs) if cs else ('Maine SOS Elections Division' if x['rank']==22 else ''),clerk_names=' | '.join(c['clerk_name'] for c in cs),clerk_phones=' | '.join(c['clerk_phone'] for c in cs),clerk_source_lines='|'.join(str(c['source_line']) for c in cs),state_source_url='https://www3.maine.gov/sos/elections-voting/election-results-data',municipal_publisher_urls=' | '.join(v['url'] for v in x['discovery_routes']),municipal_final_urls=' | '.join(dict.fromkeys(t.get('final_url') or '' for t in rr)),tested_request_ids='|'.join(x['tested_request_ids']),tested_statuses='|'.join(str(t['status']) for t in rr),download_request_ids='|'.join(d['request_id'] for d in x['downloads'] if d.get('request_id')),reuse_source_ids='|'.join(d['reuse_source_id'] for d in x['downloads'] if d.get('reuse_source_id')),current_voting_place_source_rows='|'.join(str(v['source_row']) for v in x['current_membership_mentions']),current_voting_place_labels=' | '.join(dict.fromkeys(v['municipality'] for v in x['current_membership_mentions'])),mapping_status=x['mapping_status'],inspection_outcome=x['inspection_outcome'],notes=x.get('rejection_reason') or x['relationship_warning']))
 w.writerow({'record_type':'statewide source, overlaps all native rows','native_key':'ME:SOS:STATEWIDE','native_name':'Maine Secretary of State Elections Division','authority_names':'Maine SOS','state_source_url':'https://www3.maine.gov/sos/elections-voting/election-results-data','tested_request_ids':'80980b86f6df4740a540|329b5f92851a4fdca8d1|cc5fbb49c205820d20e1','inspection_outcome':'current official index, candidate roster, historical full workbooks and RCV schema; no November result feed established','notes':'Never add statewide, county, municipal, ward/method and RCV vintages together.'})
# Exhaustive request audit (including failures, rejected/unrelated downloads and menu assets).
counts=Counter();types=Counter()
for m in requests.values():counts[str(m.get('status'))]+=1;types[bodytype(m)]+=1
summary={'baseline_native_units':len(allnative),'priority_units':len(priorityfacts),'nonpriority_units':len(allnative)-len(priorityfacts),'exact_priority_sha256':digest((BASE/'priority-keys.txt').read_bytes()),'priority_first163_votes':sum(r['senate_votes'] for r in priorityfacts[:163]),'priority_votes':sum(r['senate_votes'] for r in priorityfacts),'statewide_candidate_votes':sum(r['senate_votes'] for r in allnative),'current_clerk_CSV_labels':len(clerks),'current_named_clerk_labels':sum(bool(c['clerk_name']) for c in clerks),'current_distinct_published_contact_groups':len(contact_groups),'HTML_directory_pages':directory['pages_tested'],'HTML_directory_labels':directory['html_unique_names'],'current_voting_place_rows':len(voting),'current_voting_place_labels':len(set(v['municipality'] for v in voting)),'priority_with_some_successful_official_response':sum(any(t['status']==200 and 'PHP source' not in t['response_kind'] for t in x['test_responses']) for x in priorityfacts),'priority_with_document_refs':sum(bool(x['downloads']) for x in priorityfacts),'priority_with_successful_document_entities':sum(any(d.get('status',d.get('http_status'))==200 and d.get('response_kind') in ('PDF','image','OOXML/archive') for d in x['downloads']) for x in priorityfacts),'priority_outcomes':dict(Counter(x['inspection_outcome'] for x in priorityfacts)),'request_records':len(requests),'HTTP_statuses':dict(counts),'entity_types':dict(types),'no_November_live_result_feed_established':True,'actual_vote_arrival_snapshots':0,'actual_clocked_client_vote_refresh':None,'unallocated_current_township_labels':[x['native_name'] for x in allnative if not x['clerk_authority_keys'] and x['rank']!=22],'regular_close_local':'2026-11-03T20:00:00-05:00','regular_close_UTC':datetime.datetime(2026,11,3,20,tzinfo=ZoneInfo('America/New_York')).astimezone(datetime.timezone.utc).isoformat(),'source_date_warning':'Fetches are UTC2026-10-18, local CDT2026-10-17; source as-of dates and file clocks retained independently.'}
(ROOT/'inspection-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
# A complete 164-record review, not a list of only successes.
md=['# Maine exact 164-priority official-route audit','','Generated offline from retained responses. All dates/elections stay source-scoped. Missing flags, method totals and result IDs remain unknown. The 348-unit remainder is in native-unit-inventory.json and ../official-results-sources.csv.','','| Rank | Native label | Published clerk association | Actual route tests | Download tests / source fields | Gap |','| ---: | --- | --- | --- | --- | --- |']
for x in priorityfacts:
 cs=[bykey[k] for k in x['clerk_authority_keys']];cn='; '.join(c['municipality']+' / '+(c['clerk_name'] or 'name missing') for c in cs) or 'Maine SOS Elections Division'
 rr='; '.join(f"[{t['request_id']}](requests/{t['request_id']}.json):{t['status']}" for t in x['test_responses'])
 ds='; '.join((f"[{d['request_id']}](requests/{d['request_id']}.json) {d.get('status')} {d.get('response_kind')} {d.get('text_scope')}" if d.get('request_id') else 'reused turnout '+d['reuse_source_id']) for d in x['downloads']) or 'No result download established in bounded linked inspection'
 gap=x.get('rejection_reason') or ('Historical combined components remain unallocated' if x['historical_combined_components_unallocated'] else 'Current Senate feed/flags/method totals/cadence not established')
 md.append('| '+ ' | '.join(str(z).replace('|','/') for z in [x['rank'],x['native_name'],cn,rr,ds,gap])+' |')
(ROOT/'priority-review.md').write_text('\n'.join(md)+'\n')
print(json.dumps(summary,indent=2))
