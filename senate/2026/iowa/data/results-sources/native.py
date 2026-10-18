#!/usr/bin/env python3
"""Independent offline audit of selected original historical XML and frozen contract.

Reads peers only. Conserves every exact constituent object, identity and position;
does not build a spatial, cross-vintage or current-election crosswalk.
"""
import collections,csv,gzip,hashlib,io,json,zipfile
import xml.etree.ElementTree as E
from pathlib import Path
import research as r
T=r.STATE/'data/turnout'
def csvrows(p):
 with p.open() as f:return list(csv.DictReader(f))
def source_raw(s):
 b=(T/s['path']).read_bytes();assert r.sha(b)==s['stored_sha256'],s['id']
 out=gzip.decompress(b);assert r.sha(out)==s['original_sha256'],s['id'];return out
def main():
 p=T/'priority-set.json';assert r.sha(p.read_bytes())=='579b22b8d4f35f12d085ef8402a1bcab14e135a1577daf3ddc4f7d3f66460822'
 priority=json.loads(p.read_text());counties=priority['all_counties'];assert len(counties)==99
 assert r.sha(('\n'.join('IA:'+x for x in priority['priority_county_fips'])+'\n').encode())=='e015514b8718b35e9599389cddde2451e5cd598115ef4d6468016a7858271f95'
 constituents=[];counts=collections.Counter()
 for ci,c in enumerate(counties):
  for year,scopes in c['native_constituents'].items():
   if not isinstance(scopes,dict):continue
   for scope,objects in scopes.items():
    if not isinstance(objects,list):continue
    for oi,o in enumerate(objects):
     assert isinstance(o,dict),(scope,o)
     constituents.append({'county':c['county'],'county_fips':c['county_fips'],'year':year,'scope':scope,'contract_json_pointer':f'/all_counties/{ci}/native_constituents/{year}/{scope}/{oi}','literal_object':o})
     counts[year+'|'+scope]+=1
 assert len(constituents)==13558,len(constituents)
 (r.ROOT/'native-constituent-inventory.jsonl.gz').write_bytes(gzip.compress(b''.join((json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n').encode() for o in constituents),mtime=0))
 sources=json.loads((T/'source-manifest.json').read_text());by={s['id']:s for s in sources};roster=json.loads((T/'clarity-county-roster.json').read_text())
 expected={(x['source_id'],x['source_xml_path']):x for x in csvrows(T/'clarity-2024-native-candidate-method.csv')};assert len(expected)==26448
 checks=[];schema=collections.defaultdict(set);positions=[];state=collections.Counter();duplicates=[];seen=set();controls=0
 for c in roster:
  f=c['county_fips'];s=by['sos-2024-county-xml-'+f];assert s['status']==200
  z=zipfile.ZipFile(io.BytesIO(source_raw(s)));assert z.namelist()==['detail.xml'];b=z.read('detail.xml');root=E.fromstring(b)
  assert root.findtext('ElectionDate')=='11/5/2024' and root.findtext('Region')==c['county']
  contest=next(n for n in root.findall('Contest') if n.get('text')=='President and Vice President');choices=contest.findall('Choice');assert len(choices)==8
  canonical=[n.get('name') for n in choices[0].find('VoteType')];native=0;county_total=0;parties=[]
  for ni,n in enumerate(root.iter()):
   schema[n.tag].add(tuple(n.attrib.keys()))
  for ch in choices:
   vals=[];parties.append({'choice_key':ch.get('key'),'label':ch.get('text'),'party_literal':ch.get('party')})
   for v in ch.findall('VoteType'):
    pp=v.findall('Precinct');assert [n.get('name') for n in pp]==canonical
    total=sum(int(n.get('votes')) for n in pp);assert total==int(v.get('votes'));vals.append(total);controls+=1
    for i,n in enumerate(pp,1):
     path=f"Contest[@key='{contest.get('key')}']/Choice[@key='{ch.get('key')}']/VoteType[@name='{v.get('name')}']/Precinct[{i}]"
     key=(s['id'],path);assert key not in seen;seen.add(key);x=expected[key]
     assert (x['native_unit_label'],x['native_candidate_label'],x['party_header'],x['native_method'],int(x['votes']))==(n.get('name'),ch.get('text'),ch.get('party') or '',v.get('name'),int(n.get('votes'))),(key,x,dict(n.attrib),dict(ch.attrib))
     positions.append({'source_id':s['id'],'source_member':'detail.xml','path':path,'attributes':dict(n.attrib),'native_choice_attributes':dict(ch.attrib),'native_contest_attributes':dict(contest.attrib)})
     native+=1
   assert sum(vals)==int(ch.get('totalVotes'));controls+=1;county_total+=int(ch.get('totalVotes'));state[(ch.get('text'),'Total')]+=int(ch.get('totalVotes'))
  contract=next(x for x in counties if x['county_fips']==f);assert county_total==contract['pres2024_candidate_generic_writein_votes']
  tv=root.find('VoterTurnout');tp=tv.findall('Precincts/Precinct');st=json.loads(source_raw(by['sos-2024-county-status-'+f]));assert st['P']==canonical
  for scope,labels in [('candidate',canonical),('root_turnout',[n.get('name') for n in tp]),('status',st['P'])]:
   for label,n in collections.Counter(labels).items():
    if n>1:duplicates.append({'county_fips':f,'scope':scope,'literal_label':label,'occurrences':n})
  checks.append({'county':c['county'],'county_fips':f,'native_election_id':c['election_id'],'native_version':c['pinned_version'],'native_contest_key':contest.get('key'),'xml_clock':root.findtext('Timestamp'),'roster_clock':c['source_clock'],'xml_member_sha256':r.sha(b),'xml_member_bytes':len(b),'candidate_units':len(canonical),'root_turnout_units':len(tp),'status_units':len(st['P']),'candidate_method_cells':native,'candidate_generic_votes':county_total,'root_turnout_attributes':dict(tv.attrib),'root_turnout_ballot_sum':sum(int(n.get('ballotsCast')) for n in tp),'root_turnout_registration_sum':sum(int(n.get('totalVoters')) for n in tp),'status_ballot_sum':sum(int(x) for x in st['B']),'status_codes':dict(collections.Counter(map(str,st['S']))),'turnout_missing_candidate_labels':[x for x in canonical if x not in [n.get('name') for n in tp]],'choices':parties,'source_id':s['id']})
 assert len(seen)==26448 and controls==2376
 assert sum(x['candidate_generic_votes'] for x in checks)==1663506
 assert sum(x['candidate_units'] for x in checks)==1653 and sum(x['root_turnout_units'] for x in checks)==1651 and sum(x['status_units'] for x in checks)==1653
 s=by['sos-2024-state-reports-detailxml-zip'];z=zipfile.ZipFile(io.BytesIO(source_raw(s)));sr=E.fromstring(z.read('detail.xml'));ct=next(n for n in sr.findall('Contest') if n.get('text')=='President and Vice President')
 for ch in ct.findall('Choice'):assert state[(ch.get('text'),'Total')]==int(ch.get('totalVotes'))
 r.dump(r.ROOT/'native-county-checks.json',checks)
 r.dump(r.ROOT/'native-xml-schema.json',{'scope':'Every element tag/attribute-set in all99 original2024 county full XML; identities/positions below limited to selected presidential contest','tags':{k:[list(s) for s in sorted(v)] for k,v in schema.items()},'absent_fields':['No numeric precinct ID in selected Precinct elements','No Senate2026 contest in historical files','No exact remaining Senate votes','No certified current geographic crosswalk'],'selected_control_cells':controls})
 (r.ROOT/'native-selected-position-inventory.jsonl.gz').write_bytes(gzip.compress(b''.join((json.dumps(o,ensure_ascii=False,separators=(',',':'))+'\n').encode() for o in positions),mtime=0))
 # Pin every reused original and selected full derivatives, with original metadata references.
 deps=[]
 files=[T/'source-manifest.json',T/'SCHEMA.md',T/'priority-set.json',T/'asset-manifest.json',T.parent/'county-turnout.csv',T.parent/'coordinator-baseline-reconciliation.json',T.parent/'coordinator-native-contract-checks.json',T.parent/'coordinator-primary-preflight.json',T.parent/'coordinator-priority-keys.txt',T.parent/'baselines/asset-manifest.json']
 for f in ['native-units.csv','statistics-units.csv','clarity-2024-native-units.csv','clarity-2024-status-units.csv','clarity-2024-native-candidate-method.csv','clarity-2024-county-candidate-method.csv','clarity-2024-registration-ballots.csv','clarity-county-roster.json','canvass-candidate-method.csv','native-unit-candidate-method.csv','native-registration-ballots.csv','native-candidate-sheet-context.csv','statistics-rows.csv.gz','clarity-2024-party-label-differences.csv','clarity-2024-context-reconciliation.csv','state-controls.json']:files.append(T/f)
 for s in sources:
  if s.get('path'):
   f=(T/s['path']).resolve()
   if f not in [x.resolve() for x in files]:files.append(f)
 for f in files:
  b=f.read_bytes();deps.append({'path':str(Path(__import__('os').path.relpath(f,r.ROOT))),'bytes':len(b),'sha256':r.sha(b)})
 r.dump(r.ROOT/'dependencies.json',{'scope':'Exact read-only peer paths; originals retain URL/status/headers/UTC/redirect limitations in pinned source-manifest. No duplicate large downloads.','files':deps,'source_records':sources})
 r.dump(r.ROOT/'native-validation.json',{'status':'pass_with_retained_source_discrepancies','counties':99,'priority':41,'contract_constituent_objects':len(constituents),'constituent_context_counts':dict(counts),'full_selected_candidate_cells_checked':len(seen),'county_candidate_method_controls_checked':controls,'candidate_generic_state_sum':1663506,'candidate_units':1653,'turnout_units':1651,'status_units':1653,'literal_duplicates':duplicates,'spatial_crosswalks_approved':0,'discrepancies_retained':['Lucas rootturnout5 candidate/status7; labels and trailing spaces preserved','93county rootregistration unit/control differences retained','2024canvass ED/Absentee992119/681892 vs turnout992112/681899 total1674011, DesMoines+7/-7','2020statistics registration age bins2203256 vs printed2203254','14county party-label differences SPA/SPU/PSI/NoP versus stateSOC; never rewritten']})
 print('PASS native',len(constituents),'objects',len(seen),'candidate cells',controls,'controls',len(deps),'dependency pins')
if __name__=='__main__':main()
