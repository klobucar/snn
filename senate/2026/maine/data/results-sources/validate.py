#!/usr/bin/env python3
"""Network-free standard-library audits of retained public research and explicit gaps."""
import csv,datetime,gzip,hashlib,json,re,sys,urllib.parse
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent;STATE=ROOT.parent.parent
sys.path.insert(0,str(ROOT.parent/'turnout'))
from xlsx_read import read
checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def j(path):return json.loads(Path(path).read_text())
def check(name,condition):
 if not condition:raise AssertionError(name)
 checks.append(name)
def source(id):
 m=j(ROOT/'requests'/f'{id}.json');return m,gzip.decompress((ROOT/m['body_path']).read_bytes())
def urlkey(u):
 p=urllib.parse.urlparse(urllib.parse.unquote(u));return (p.netloc.removeprefix('www.'),p.path,p.query)
manifest=j(ROOT/'asset-manifest.json');assets=manifest['assets'];seen=set()
for a in assets:
 p=(ROOT/a['path']).resolve();allowed=p.is_relative_to(ROOT) or p in [(ROOT.parent/'official-results-sources.csv').resolve(),(STATE/'official-results.md').resolve()]
 check('owned asset path: '+a['path'],allowed)
 check('asset unique: '+a['path'],a['path'] not in seen);seen.add(a['path'])
 check('asset size: '+a['path'],p.is_file() and p.stat().st_size==a['bytes'] and a['bytes']<40_000_000)
 check('asset SHA256: '+a['path'],sha(p.read_bytes())==a['sha256'])
check('no Python cache artifacts',not list(ROOT.rglob('__pycache__')))
for p,c in j(ROOT/'baseline-pin.json').items():check('read-only input unchanged: '+p,sha((STATE/p).read_bytes())==c['sha256'])
contract=j(STATE/'data/turnout/priority-set.json');inv=j(ROOT/'native-unit-inventory.json');pri=j(ROOT/'priority-field-audit.json');keys=(STATE/'data/turnout/priority-keys.txt').read_bytes()
expected='086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'
check('exact ordered164 key hash',sha(keys)==expected and keys.endswith(b'\n') and len(keys.splitlines())==164)
check('full native512 and remainder348',len(inv)==512 and len(pri)==164 and len([x for x in inv if not x['priority']])==348)
check('full key uniqueness/equality',len({x['native_key'] for x in inv})==512 and {x['native_key'] for x in inv}=={x['native_key'] for x in contract['all_unit_coverage']})
check('exact priority order',[x['native_key'] for x in pri]==keys.decode().splitlines()==[x['native_key'] for x in contract['priority']])
check('all ranks preserved',[x['rank'] for x in inv]==list(range(1,513)))
check('priority/remainder disjoint',not ({x['native_key'] for x in pri}&{x['native_key'] for x in inv if not x['priority']}))
check('ranking and exact80 crossing',sum(x['senate_votes'] for x in pri[:15])==215627 and sum(x['senate_votes'] for x in pri[:163])==656778 and sum(x['senate_votes'] for x in pri)==658029 and 5*656778<4*821072<=5*658029 and pri[-1]['native_name']=='Pownal' and pri[-1]['senate_votes']==1251)
main=list(csv.DictReader((STATE/'data/county-turnout.csv').open()));check('main turnout pinned hash',sha((STATE/'data/county-turnout.csv').read_bytes())=='0d0852ce0029561dec0d764f52272b07c88c329e4f8eb5d4a946ed41f33569be')
cols=['cherry_independent_2024','costello_democratic_2024','king_independent_2024','kouzounas_republican_2024','blank_senate_2024','ballots_cast_2024']
check('historical512 candidate controls',[sum(int(x[k]) for x in main) for k in cols]==[20193,88875,427570,284434,21375,842447])
check('historical512 row ballot controls',all(sum(int(x[k]) for k in cols[:5])==int(x['ballots_cast_2024']) for x in main))

# Independent long-table comparators and retained source defects, without rewriting them.
for filename,nrows,nlabels,votes,ballots in [('president-2024-source-rows.csv',513,513,831375,842447),('governor-2022-source-rows.csv',510,509,676819,680909)]:
 long=list(csv.DictReader((STATE/'data/turnout'/filename).open()));group=defaultdict(list)
 for x in long:group[x['source_row_key']].append(x)
 check('complete raw row coverage '+filename,len(group)==nrows and len({x['native_key'] for x in long})==nlabels)
 one=[v[0] for v in group.values()]
 check('comparator candidate/ballot totals '+filename,sum(int(x['candidate_votes']) for x in one)==votes and sum(int(x['ballots']) for x in one)==ballots)
 if filename.startswith('governor'):
  t3=[x for x in one if x['source_row']=='190'];cran=[x for x in one if x['unit_name'].strip()=='Cranberry Isles']
  check('T3 ND printed PEN and HAN section preserved',len(t3)==1 and t3[0]['county_code']=='PEN' and t3[0]['county_section_code']=='HAN' and int(t3[0]['candidate_votes'])==4 and int(t3[0]['ballots'])==4)
  check('two Cranberry Isles source rows remain',len(cran)==2 and sum(int(x['candidate_votes']) for x in cran)==115 and sum(int(x['ballots']) for x in cran)==117)

u=pri[21];check('STATE UOCAVA identity/admin/no invented clerk',u['native_name']=='STATE UOCAVA' and u['rank']==22 and u['senate_votes']==6434 and not u['county_code'] and not u['clerk_authority_keys'])
check('all164 inspected with actual routes',all(x['tested_request_ids'] for x in pri))
check('unsupported current feed/remaining/cadence fields null',all(x['current_Senate_feed_or_candidate_ids'] is None and x['outstanding_votes'] is None and x['observed_count_update_cadence'] is None and all(v is None for v in x['verified_current_result_flags'].values()) for x in inv))
check('T22 MD current host remains unknown',next(x for x in inv if x['native_name']=='T22 MD Twp')['current_serving_authority_candidates']==[])
for exact_name in ('Portland','Berwick','Yarmouth','Windham','Paris','Turner','York','Warren','Union'):
 unit=next(x for x in inv if x['native_name']==exact_name)
 check('full-name authority association '+exact_name,all(r['municipality'].split('(')[0].strip().upper()==exact_name.upper() for r in unit['current_membership_mentions']))
portland=next(x for x in inv if x['native_name']=='Portland')
check('Portland retains exactly own12 current rows',[r['source_row'] for r in portland['current_membership_mentions']]==list(range(384,396)))
argyle=next(x for x in inv if x['native_name']=='Argyle Twp')
check('explicit Argyle multi-host associations survive',len(argyle['current_serving_authority_candidates'])>=3)
check('all eight priority combined labels retained',len([x for x in pri if '/' in x['native_name']])==8 and all(x['historical_combined_components_unallocated'] for x in pri if '/' in x['native_name']))
# All published current rosters, without equating row counts to legal authority count.
clerks=j(ROOT/'current-authority-inventory.json');voting=j(ROOT/'current-voting-places.json')['rows'];dire=j(ROOT/'directory-audit.json')
check('all560 clerk labels including missing names',len(clerks)==560 and len({c['municipality'] for c in clerks})==560 and sum(bool(c['clerk_name']) for c in clerks)==546)
check('all34 directory pages/counts/unique names',sorted(x['page'] for x in dire['pages'])==list(range(34)) and dire['html_rows']==505 and dire['html_unique_names']==505 and not dire['duplicate_html_names'])
check('HTML/CSV normalized coverage505 versus55 extras',sum(c['in_HTML_roster_normalized'] for c in clerks)==505)
check('all539 current polling rows preserved',len(voting)==539 and len({r['source_row'] for r in voting})==539 and len({r['municipality'] for r in voting})==499)
va=j(ROOT/'current-voting-identity-audit.json');check('current duplicate WP retained',va['unique_county_municipality_WP_tuples']==538 and [r['source_row'] for r in va['duplicate_tuples'][0]['rows']]==[418,437])
# Original response metadata and raw content bounds, failures included.
requests={};statuses=Counter()
for f in (ROOT/'requests').glob('*.json'):
 if f.name.endswith('.links.json'):continue
 m=j(f);id=m['id'];requests[id]=m;b=gzip.decompress((ROOT/m['body_path']).read_bytes());statuses[str(m.get('status'))]+=1
 check('original entity hash: '+id,sha(b)==m['entity_sha256'] and len(b)==m['entity_bytes_retained'] and len(b)<=39_000_000)
 check('saved entity hash: '+id,sha((ROOT/m['body_path']).read_bytes())==m['saved_sha256'])
 check('UTC retrieval: '+id,datetime.datetime.fromisoformat(m['retrieved_utc']).utcoffset()==datetime.timedelta(0))
 check('public URL schemes: '+id,all(urllib.parse.urlparse(m[k]).scheme in ('http','https') for k in ('publisher_url','request_url')))
 check('no supplied authentication headers: '+id,not any(k.lower() in ('authorization','cookie','x-api-key') for k in m.get('requested_headers',{})))
 mtype={k.lower():v for k,v in m.get('headers',[])}.get('content-type','')
 if m.get('status')==206:check('range sample not a complete statewide product',id=='95aaabddac38c657afea' and len(b)==65536 and {k.lower():v for k,v in m['headers']}['content-range']=='bytes 0-65535/16143837')
# Source-directed download provenance: only actual retained parent hrefs qualify.
link_count=0
for x in j(ROOT/'priority-inspections.json'):
 for d in x['downloads']:
  if d.get('request_id'):check('download source reference '+d['request_id'],d['request_id'] in requests)
  if d.get('parent_request_id'):
   par=d['parent_request_id'];links=j(ROOT/'requests'/f'{par}.links.json')['links']
   check('actual parent download link '+par,any(urlkey(t['url'].split('#')[0])==urlkey(d['url']) for t in links));link_count+=1
  if d.get('reused_body_path'):
   b=gzip.decompress((ROOT/d['reused_body_path']).read_bytes());check('read-only reused source hash '+d['reuse_source_id'],sha(b)==d['entity_sha256'])
# Current candidate control from original OOXML plus retained inspected PDF text.
m,b=source('faa16009e9a48f60f351');wb=read(ROOT/m['body_path']);cr=next(iter(wb.values()));us=[r for r in cr if r['cells'].get('A'+str(r['row']))=='US'];check('current November printed candidates exactly2',len(us)==2 and us[0]['cells']['F2']=='Collins' and us[1]['cells']['F3']=='Jackson')
ca=j(ROOT/'candidates-2026.json');check('current eight named candidates and no invented exclusions certainty',len(ca['printed_candidates'])==2 and len(ca['declared_write_ins'])==6 and ca['negative_exclusions_certification_claim'] is False and ca['candidate_ids'] is None)
check('Platner withdrawal not a late excluded candidate',ca['withdrawals'][0]['late_excluded_candidate_under_723A'] is False)
# Complete original selected RCV workbooks, source blank fields and duplicates retained.
m,b=source('ea9168a83a2208b62e32');rs=next(iter(read(ROOT/m['body_path']).values()));data=[]
for row in rs:
 n=row['row'];c={re.sub(r'\d+','',k):v for k,v in row['cells'].items()}
 if c.get('D') and all(c.get(k,'').isdigit() for k in 'FGHIJK'):data.append((n,c))
check('RCV complete425 rows and all ballot balances',len(data)==425 and all(sum(int(c[k]) for k in 'FGHIJ')==int(c['K']) for n,c in data))
check('RCV initial original candidate/ballot controls',[sum(int(c[k]) for n,c in data) for k in 'FGHIJK']==[24944,22920,8182,22678,4756,83480])
check('RCV blank office fields not dropped',[n for n,c in data if not c.get('A')]==[92,353])
m,b=source('3e8ead0ae70c94422366');cv=next(iter(read(ROOT/m['body_path']).values()))[1:];ids=[r['cells']['A'+str(r['row'])] for r in cv];first=Counter(r['cells']['D'+str(r['row'])] for r in cv)
check('CVR complete345 rows/342 unique with known duplicate IDs',len(cv)==345 and len(set(ids))==342 and {k:v for k,v in Counter(ids).items() if v>1}=={'1335':2,'1342':2,'1347':2})
check('CVR rank mismatch retained',first=={'Baldacci, Joseph M.':95,'Dunlap, Matthew G.':78,'Loud, Paige':80,'Wood, Jordan':76,'undervote':16})
ra=j(ROOT/'rcv-audit.json');check('all actual rounds/exhausted control83480',all(sum(r[k] for k in ['Baldacci','Dunlap','Wood','Loud','exhausted'])==83480 for r in ra['rounds']))
check('local14 controls12 matches/discrepancies retained',len(j(ROOT/'local-controls.json'))==14 and sum(r['all_candidate_controls_match'] for r in j(ROOT/'local-controls.json'))==12 and {r['unit']:r['local_minus_current_SOS'] for r in j(ROOT/'local-controls.json') if not r['all_candidate_controls_match']}=={'Gorham':[0,0,-400,-30],'Falmouth':[0,0,-1,-1]})
v=j(STATE/'data/turnout/source-vintage-diff.json');check('Alfred separate archived/current controls',[v[k]['affected_unit'] for k in ('senate','president')]==['YOR / Alfred','YOR / Alfred'] and all(v[k]['unaffected_ballots']==2076 and v[k]['archived_clerk_exact'] for k in v))
check('Alfred Senate candidate+290 blank-290',sum(v['senate']['current_statewide'][:4])-sum(v['senate']['archived_statewide'][:4])==290 and v['senate']['current_statewide'][4]-v['senate']['archived_statewide'][4]==-290)
check('Alfred president candidate+386 blank-386',sum(v['president']['current_statewide'][:6])-sum(v['president']['archived_statewide'][:6])==386 and v['president']['current_statewide'][6]-v['president']['archived_statewide'][6]==-386)
# CSV universe and local Markdown targets, no network link checking/extra fetches.
rows=list(csv.DictReader((ROOT.parent/'official-results-sources.csv').open()));check('CSV complete512 plus explicit overlapping statewide source',len(rows)==513 and len([r for r in rows if r['record_type']=='native historical research unit'])==512)
mds=[STATE/'official-results.md',ROOT/'README.md',ROOT/'priority-review.md'];link_total=0
for md in mds:
 for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',md.read_text()):
  if re.match(r'\w+://|mailto:|#',link):continue
  dest=(md.parent/urllib.parse.unquote(link.split('#')[0])).resolve();check('local Markdown target '+link,dest.exists() or dest==(ROOT/'validation.json').resolve());link_total+=1
out={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'standard_library_only':True,'network_requests':0,'assertions':len(checks),'asset_count':len(assets),'asset_bytes':sum(x['bytes'] for x in assets),'max_asset_bytes':max(x['bytes'] for x in assets),'request_records':len(requests),'HTTP_statuses':dict(statuses),'native_units':512,'priority':164,'remainder':348,'priority_sha256':expected,'current_clerk_labels':560,'current_HTML_labels':505,'current_voting_place_rows':539,'current_unique_county_municipality_WP':538,'source_parent_links_checked':link_count,'Markdown_targets_checked':link_total,'known_source_issues_retained':['current roster universes differ; T22MD host unknown','current SaintAgatha WP repeats','Gorham/Falmouth local-vs-correctedSOS candidate differences','CVR345rows342unique and first-rank discrepancy','initial versus round1 counts differ','Alfred archived versus corrected SOS; correction chronology unknown','nine priority raw-byte access gaps and three separately labeled web observations','no current November Senate feed/IDs/cadence/outstanding count'],'asset_manifest_sha256':sha((ROOT/'asset-manifest.json').read_bytes())}
old=ROOT/'validation.json'
if old.exists():
 prev=j(old)
 if {k:v for k,v in prev.items() if k!='checked_utc'}=={k:v for k,v in out.items() if k!='checked_utc'}:out['checked_utc']=prev['checked_utc']
old.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
