from research import *
from collections import Counter,defaultdict
BASE=ROOT.parent/'turnout'
contract=json.loads((BASE/'priority-set.json').read_text());units=contract['all_unit_coverage']
def body(id):
 m=json.loads((ROOT/'requests'/f'{id}.json').read_text());return gzip.decompress((ROOT/m['body_path']).read_bytes())
def norm(s):
 s=s.strip().upper().replace('SAINT ','ST ').replace('ST. ','ST ').replace('PLANTATION','PLT').replace('TOWNSHIP','TWP')
 return re.sub(r'\s+',' ',s)
raw=list(csv.reader(body('7ce88c366d25718425bc').decode('utf-8-sig').splitlines()));clerks=[]
cols=['municipality','clerk_name','clerk_address1','clerk_address2','clerk_city_state_zip','clerk_phone','clerk_fax','registrar_name','registrar_address1','registrar_address2','registrar_city_state_zip','registrar_phone','registrar_fax','geocode']
for line,row in enumerate(raw[1:],2):
 assert len(row)==14,(line,row)
 clerks.append(dict(zip(cols,row),source_line=line,authority_key=f'ME:SOS:CLERKS:{row[13]}:{urllib.parse.quote(row[0],safe="")}'))
byname={norm(r['municipality']):r for r in clerks}
vraw=json.loads((ROOT/'extracted/925f39cdbc953b852aa1.json').read_text())['Voting Place Report'];voting=[]
for row in vraw[1:]:
 n=row['row'];c={re.sub(r'\d+','',k):v for k,v in row['cells'].items()}
 voting.append(dict(zip(['county_code','municipality','ward_precinct','voting_place','address','voting_town','opening'],[c.get(x,'') for x in 'ABCDEFG']),source_row=n))
maprows=[]
for u in units:
 name=u['native_name'].strip();base=name.split('/')[0];matches=[]
 if norm(name) in byname:matches=[byname[norm(name)]];status='exact normalized municipal label; no boundary equivalence'
 elif norm(base) in byname:matches=[byname[norm(base)]];status='historical combined label; lead authority located; component coverage requires current voting place evidence'
 elif name=='STATE UOCAVA':status='state administered; no town/county/polygon assigned'
 else:status='unresolved native label; no clerk inferred'
 components=name.split('/')[1:]
 # Preserve separate exact component directory records as candidates, never auto-relabel combined aggregate.
 for component in components:
  if norm(component) in byname and byname[norm(component)] not in matches:matches.append(byname[norm(component)])
 v=[r for r in voting if norm(re.split(r'\s*\(',r['municipality'])[0]) in {norm(name),norm(base)}]
 maprows.append({'native_key':u['native_key'],'native_name':u['native_name'],'county_code':u['county_code'],'rank':u['rank'],'priority':u['priority'],'senate_votes':u['senate_votes'],'mapping_status':status,'clerk_authority_keys':[r['authority_key'] for r in matches],'clerk_municipalities':[r['municipality'] for r in matches],'current_voting_place_rows':[r['source_row'] for r in v],'current_voting_place_labels':list(dict.fromkeys(r['municipality'] for r in v)),'historical_combined_components_unallocated':components,'current_boundary_equivalence':'unverified','current_feed_or_contest_id':None})
(ROOT/'current-clerk-roster.json').write_text(json.dumps({'source':'7ce88c366d25718425bc','header_raw':raw[0],'rows':clerks},indent=2)+'\n')
(ROOT/'current-voting-places.json').write_text(json.dumps({'source':'925f39cdbc953b852aa1','rows':voting},indent=2)+'\n')
(ROOT/'authority-reconciliation.json').write_text(json.dumps(maprows,indent=2)+'\n')
print('clerks',len(clerks),'with name',sum(bool(r['clerk_name']) for r in clerks),'unique geo',len(set(r['geocode'] for r in clerks)))
print('voting rows',len(voting),'labels',len(set(r['municipality'] for r in voting)),'opening',Counter(r['opening'] for r in voting))
print('mapping',Counter(r['mapping_status'] for r in maprows))
print('unmatched',[(r['rank'],r['native_name']) for r in maprows if not r['clerk_authority_keys']])
print('combined priority',[(r['rank'],r['native_name'],r['current_voting_place_labels']) for r in maprows if r['priority'] and r['historical_combined_components_unallocated']])
