#!/usr/bin/env python3
"""Meaningful offline checks of retained original bytes, native controls and coverage."""
import collections,csv,datetime,gzip,hashlib,io,json,re,zipfile
from pathlib import Path
from urllib.parse import unquote,urlparse
import research as r
def j(p):return json.loads(p.read_text())
def fail(test,msg):
 if not test:raise AssertionError(msg)
def main():
 checks={};pfile=r.STATE/'data/turnout/priority-set.json';p=j(pfile)
 fail(pfile.stat().st_size==9106895 and r.sha(pfile.read_bytes())=='579b22b8d4f35f12d085ef8402a1bcab14e135a1577daf3ddc4f7d3f66460822','Final priority metadata changed')
 for path,expected in [('data/turnout/asset-manifest.json','20104d2dce95fd34f3a4fe5ea129193faa38218471e6ee7259689047fcfb11f4'),('data/baselines/asset-manifest.json','d6725bcb601a6e0187494415ce9ea910d4f7417705d9e5cf4a52429532ffd293')]:fail(r.sha((r.STATE/path).read_bytes())==expected,'Final peer asset manifest pin changed:'+path)
 checks['final_peer_pins']='pass'
 rows=list(csv.DictReader((r.STATE/'data/official-results-sources.csv').open()));cs=p['all_counties'];fail(len(rows)==99,'county inventory99');fail([x['county_fips'] for x in rows]==[x['county_fips'] for x in cs],'all99 exact order')
 fail(len({x['county_fips'] for x in rows})==99,'county uniqueness');deep=[x for x in rows if x['investigation_scope']=='deep_priority'];rest=[x for x in rows if x['investigation_scope']=='discovery_only'];fail(len(deep)==41 and len(rest)==58,'41/58 honest scopes')
 keybytes=('\n'.join('IA:'+x['county_fips'] for x in deep)+'\n').encode();fail(r.sha(keybytes)=='e015514b8718b35e9599389cddde2451e5cd598115ef4d6468016a7858271f95','ordered keyhash')
 fail(sum(int(x['baseline_candidate_generic_marks']) for x in rows)==1663506,'all99 denominator');fail(sum(int(x['baseline_candidate_generic_marks']) for x in deep)==1332107,'exact41volume');fail(sum(int(x['baseline_candidate_generic_marks']) for x in rows[:40])==1322507,'first40');fail(sum(int(x['baseline_candidate_generic_marks']) for x in rows[:15])==991869,'top15')
 fail(deep[-1]['county_fips']=='19087' and deep[-1]['baseline_candidate_generic_marks']=='9600','Henry crossing');fail(next(x for x in rows if x['county']=='Page')['county_fips']=='19145','Page real county')
 records=list((r.ROOT/'counties').glob('*.json'));fail(len(records)==41,'41individual files');fail({x.stem for x in records}=={x['county_fips'] for x in deep},'41filesexact')
 for f in records:
  o=j(f);fail(o['investigation_scope']=='deep_priority' and len(o['finding'])>150 and len(o['gap'])>30 and o['tested_routes'],'substantive individual record:'+f.name);fail(not o['november_feed_approved'] and not o['current_crosswalk_approved'],'No unjustified approval')
 checks['county_scope_order_arithmetic']={'status':'pass','all99':99,'deep41':41,'discovery58':58,'denominator':1663506,'priority_marks':1332107,'ordered_keys_sha256':r.sha(keybytes)}
 deps=j(r.ROOT/'dependencies.json');fail(len({x['path'] for x in deps['files']})==len(deps['files']),'dependency path uniqueness')
 for d in deps['files']:
  f=r.ROOT/d['path'];b=f.read_bytes();fail(len(b)==d['bytes'] and r.sha(b)==d['sha256'],'dependency hash:'+d['path']);fail(len(b)<40000000,'dependency strictbound')
 # Original source metadata remains separate, and every available original matches its exact stored reference.
 peer_originals=0
 for s in deps['source_records']:
  if not s.get('path'):continue
  f=r.STATE/'data/turnout'/s['path'];b=f.read_bytes();fail(r.sha(b)==s['stored_sha256'],'peerstoredhash:'+s['id']);out=gzip.decompress(b);fail(r.sha(out)==s['original_sha256'],'peeroriginalhash:'+s['id']);peer_originals+=1
 census=next(x for x in deps['source_records'] if x['id']=='census-county-codes');b=gzip.decompress((r.STATE/'data/turnout'/census['path']).read_bytes());censusrows=list(csv.DictReader(io.StringIO(b.decode()),delimiter='|'));ia=[x for x in censusrows if x['STATEFP']=='19'];fail(len(ia)==99,'Census99')
 canonical={x['COUNTYNAME'].removesuffix(' County'):'19'+x['COUNTYFP'] for x in ia};fail(canonical=={x['county']:x['county_fips'] for x in rows},'independent Census exact full names/FIPS')
 checks['peer_dependencies_census_originals']={'status':'pass','pinned_files':len(deps['files']),'original_entities_checked':peer_originals,'census_counties':99}
 # Complete exact-object conservation, source scope/order/unknowns included.
 obs=[json.loads(x) for x in gzip.decompress((r.ROOT/'native-constituent-inventory.jsonl.gz').read_bytes()).decode().split('\n') if x];expected=[]
 for ci,c in enumerate(cs):
  for year,scopes in c['native_constituents'].items():
   if isinstance(scopes,dict):
    for scope,objects in scopes.items():
     if isinstance(objects,list):
      for oi,o in enumerate(objects):expected.append({'county':c['county'],'county_fips':c['county_fips'],'year':year,'scope':scope,'contract_json_pointer':f'/all_counties/{ci}/native_constituents/{year}/{scope}/{oi}','literal_object':o})
 fail(obs==expected and len(obs)==13558,'all13558 literal objects/order');fail(len({x['contract_json_pointer'] for x in obs})==13558,'unique original positions')
 blankroot=[x for x in obs if x['scope']=='turnout_context_units' and x['year']=='2024']
 # Check by XML context rather than guessing a scope spelling.
 actualroot=[x for x in obs if x['year']=='2024' and 'VoterTurnout/' in str(x['literal_object'].get('source_xml_path',''))]
 fail(len(actualroot)==1651 and all(x['literal_object'].get('source_contest_key')=='' for x in actualroot),'rootturnout1651 blank contest')
 nc=j(r.ROOT/'native-county-checks.json');fail(len(nc)==99,'native99');fail(sum(x['candidate_method_cells'] for x in nc)==26448,'native26448');fail(sum(x['candidate_generic_votes'] for x in nc)==1663506,'native state control')
 lucas=next(x for x in nc if x['county']=='Lucas');fail((lucas['candidate_units'],lucas['root_turnout_units'],lucas['status_units'])==(7,5,7),'Lucas scopes');fail(lucas['root_turnout_ballot_sum']==2733 and lucas['status_ballot_sum']==4676,'Lucas explicit exception')
 cells=[json.loads(x) for x in gzip.decompress((r.ROOT/'native-selected-position-inventory.jsonl.gz').read_bytes()).decode().split('\n') if x];fail(len(cells)==26448 and len({(x['source_id'],x['path']) for x in cells})==26448,'native raw position uniqueness')
 fail(j(r.ROOT/'native-validation.json')['county_candidate_method_controls_checked']==2376,'2376nativecontrols')
 checks['complete_native_conservation']={'status':'pass','exact_objects':13558,'candidate_cells':26448,'county_controls':2376,'candidate_units':1653,'root_turnout_units':1651,'status_units':1653,'approved_crosswalks':0}
 m=r.ledger();fail(len({x['id'] for x in m})==len(m),'source IDs unique');ids={x['id'] for x in m};now=datetime.datetime.now(datetime.timezone.utc);originals=0;partcount=0;failures=[]
 for a in m:
  dt=datetime.datetime.fromisoformat(a['retrieval_utc']);fail(dt.utcoffset()==datetime.timedelta(0) and dt<=now,'UTC retrieval:'+a['id'])
  fail(a.get('url','').startswith(('http://','https://')),'actual requestURL')
  if a.get('status') is None:
   fail(a.get('error') and not a['parts'] and 'original_sha256' not in a,'transporterror metadata');failures.append(a['id']);continue
  fail(isinstance(a['status'],int) and isinstance(a['redirects'],list) and isinstance(a['headers'],dict),'HTTP metadata')
  b=r.raw(a);fail(len(b)==a['original_bytes'] and r.sha(b)==a['original_sha256'],'exact original bytes:'+a['id']);originals+=1
  for x in a['stored_objects']:
   z=(r.ROOT/x['path']).read_bytes();fail(len(z)==x['bytes'] and r.sha(z)==x['sha256'] and len(z)<40000000,'storedgzipbound/hash');partcount+=1
  if 'payload' in a['id'] and a['status']==403:fail(a['original_bytes']==0,'expected retained GMD empty403')
 for c in rows:fail(c['authority_source_id'] in ids and c['key_publication_source_id'] in ids,'county source refs')
 identity=j(r.ROOT/'source-identity-inventory.json');fail({x['source_id'] for x in identity}==ids,'every response has identity classification')
 viewcounts=collections.Counter();seenpositions=set();duplicate_literals=collections.Counter()
 for line in gzip.decompress((r.ROOT/'source-view-position-inventory.jsonl.gz').read_bytes()).decode().split('\n'):
  if not line:continue
  x=json.loads(line);fail(x['source_id'] in ids,'view pointerref');context=x['context'];pos=(x['source_id'],context,x['physical_page'],x['line']) if context.startswith('PDF') else (x['source_id'],context,x['position']);fail(pos not in seenpositions,'raw source position duplicate');seenpositions.add(pos);viewcounts[x['source_id']]+=1
  if context=='HTML_links':duplicate_literals[(x['source_id'],x['href_literal'],x['text'])]+=1
 fail(all(x['source_view_occurrences']==viewcounts[x['source_id']] for x in identity),'full view positions counted')
 checks['own_original_metadata_and_full_positions']={'status':'pass','requests':len(m),'HTTP_original_entities':originals,'gzip_objects':partcount,'transport_failures':failures,'view_positions':len(seenpositions),'preserved_repeated_link_values':sum(n-1 for n in duplicate_literals.values() if n>1)}
 primary=j(r.ROOT/'primary-2026-identity-schema.json');fail(primary['election_id']=='126082' and primary['version']=='377216' and primary['election_date']=='6/2/2026','Reject primary asNovember');fail(primary['status_reported_sum']==1658 and primary['status_participating_sum']==1658,'primary status1658')
 fail(len(primary['county_roster'])==99 and {x['county_fips'] for x in primary['county_roster']}==set(canonical.values()),'primary99roster')
 for a in m:
  if a['id'].startswith('sos-election-list-data'):
   el=json.loads(r.raw(a));fail(len(el)==4 and not any('general' in x['ElectionName'].lower() and '2026' in x['ElectionName'] for x in el),'actual bounded list identity')
 admin=j(r.ROOT/'absentee-2026-native-rows.json');ar=[x for x in admin if x.get('county_fips')];fail(len(ar)==99 and [sum(x[k] or 0 for x in ar) for k in ['requested','issued','received']]==[176012,176014,33418],'absentee99statecontrol');fail(any(x['received'] is None for x in admin),'blanknotzero');fail(any(x['label_literal']=='UD' for x in admin),'literalUD')
 s=j(r.ROOT/'senate-2026-ballot-identities.json');fail([x['name'] for x in s['printed_candidates']]==['Ashley Hinson','Josh Turek','Thomas Laehn'],'currentballot candidates')
 visual={x['source_id']:x for x in j(r.ROOT/'visual-ballot-checks.json')}
 for id in s['ballot_corroboration_source_ids']:
  text=(r.ROOT/'extracts'/(id+'.txt')).read_text()
  if id in visual:
   v=visual[id];a=next(a for a in m if a['id']==id);fail(a['original_sha256']==v['original_sha256'] and r.sha((r.ROOT/v['render_path']).read_bytes())==v['render_sha256'],'visually checked source/render pins');fail(v['observed_election_date']=='November 3, 2026' and {x['label'] for x in v['observed_named_choices']}=={'Ashley Hinson','Josh Turek','Thomas Laehn'} and v['generic_writein'],'visual candidate/ballot context')
  else:
   fail(all(x in text for x in ['Ashley Hinson','Josh Turek','Thomas Laehn']),'actual sample names:'+id);fail('Write' in text or 'write' in text,'actual writein line:'+id)
 checks['current_identity_rules_admin']={'status':'pass_with_explicit_conflicts','primary_counties':99,'primary_cells':1188,'primary_status':'1658/1658','current_named_ballot_candidates':3,'November_live_feed_eids':[],'absentee_controls':[176012,176014,33418],'recount_calendar_conflict_retained':True,'military_FWAB_stale9pm_retained':True}
 # Owned links and individual object bound checks; no dependency/cache trees created.
 md=r.STATE/'official-results.md';local=0
 for target in re.findall(r'\]\(([^)]+)\)',md.read_text()):
  if target.startswith(('http://','https://','mailto:','#')):continue
  f=md.parent/unquote(target.split('#')[0]);fail(f.exists() or f==r.ROOT/'validation.json' or f==r.ROOT/'asset-manifest.json','local report link:'+target);local+=1
 files=sorted([f for f in r.ROOT.rglob('*') if f.is_file() and f.name not in ['asset-manifest.json','validation.json']]+[md,r.STATE/'data/official-results-sources.csv']);assets=[]
 for f in files:
  fail('__pycache__' not in f.parts and 'node_modules' not in f.parts,'no own dependency/cache dirs');b=f.read_bytes();fail(len(b)<40000000,'strict object bound:'+str(f));assets.append({'path':str(f.relative_to(r.STATE)),'bytes':len(b),'sha256':r.sha(b)})
 manifest={'scope':'All owned artifacts except asset-manifest itself and validation.json (excluded to avoid cycles). Peer originals are exact dependencies, not copied assets.','strict_upper_bound_exclusive_bytes':40000000,'assets':assets};r.dump(r.ROOT/'asset-manifest.json',manifest)
 fail((r.ROOT/'asset-manifest.json').stat().st_size<40000000,'manifeststrictbound')
 checks['references_bounds']={'status':'pass','local_report_links':local,'owned_assets':len(assets),'largest_owned_object_bytes':max(x['bytes'] for x in assets),'exclusive_byte_bound':40000000}
 result={'status':'completed_with_retained_source_gaps_and_discrepancies','validated_at_utc':now.isoformat(),'checks':checks,'asset_manifest_sha256':r.sha((r.ROOT/'asset-manifest.json').read_bytes()),'limitations':['No November2026 counted feed/general machine keys, upload schema, demonstrated cadence or exact remaining votes','41priority investigations include explicit current-source blocks;58remainder remain discovery only','No approved geographic/cross-vintage/current reporting crosswalk','Recount guide/holiday deadline conflict remains source-scoped; scoped UOCAVA/FWAB/SafeatHome rules not generalized','Historical±7/registration+2/Lucas/context/party differences conserved without repair']};r.dump(r.ROOT/'validation.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
