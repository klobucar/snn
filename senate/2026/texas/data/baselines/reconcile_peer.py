#!/usr/bin/env python3
"""Read-only comparison of independently parsed primary cells, fields, ranking and priority."""
from build import *
def main():
 own=readcsv(P/'county-candidates.csv');base=readcsv(DATA/'county-baselines.csv');peer=readcsv(PEER/'county-candidates-2024.csv')+readcsv(PEER/'county-candidates-comparators.csv');pt=readcsv(DATA/'county-turnout.csv');diff=[];counts=collections.Counter()
 cv={'senate':'2024-senate','president':'2024-president','senate_2020':'2020-senate','governor_2022':'2022-governor'}
 om={(r['contest'],r['county_fips'],r['native_candidate_name']):r for r in own};pm={(cv[r['contest']],r['county_fips'],r['source_candidate_name']):r for r in peer};assert len(om)==len(own) and len(pm)==len(peer)
 for key in sorted(set(om)|set(pm)):
  a=om.get(key);b=pm.get(key)
  if a is None or b is None:diff.append(dict(key=key,field='missing',own=a,peer=b));continue
  for x,y in [('votes','votes'),('native_county_name','source_county_name'),('native_county_code','source_county_code'),('native_party','source_party'),('write_in','write_in'),('county_contest_total','source_county_total'),('election_date','election_date')]:
   counts['candidate_'+x]+=1
   if a[x]!=b[y]:diff.append(dict(key=key,field=x,own=a[x],peer=b[y]))
 bm={(r['contest'],r['county_fips']):r for r in base}
 for r in pt:
  k=r['county_fips'];a=bm[('2024-senate',k)]
  fields={'source_county_name':'native_county_name','source_county_code':'native_county_code','dispatch_key':'dispatch_key','rank':'senate2024_volume_rank','top15':'senate2024_top15','priority80':'senate2024_priority80','cumulative_senate_2024':'senate2024_cumulative_votes'}
  for x,y in fields.items():
   counts['county_'+x]+=1
   if r[x]!=a[y]:diff.append(dict(key=k,field=x,own=a[y],peer=r[x]))
  for pc,oc in [('senate_2024','2024-senate'),('president_2024','2024-president'),('senate_2020','2020-senate'),('governor_2022','2022-governor')]:
   a=bm[(oc,k)]
   for x,y in [('total','candidate_votes'),('d','d'),('r','r'),('other','other')]:
    counts['county_'+pc+'_'+x]+=1
    if r[pc+'_'+x]!=a[y]:diff.append(dict(key=k,field=pc+'_'+x,own=a[y],peer=r[pc+'_'+x]))
  for pf,bf in [('share_state_senate_2024','candidate_vote_weight'),('cumulative_share_state_senate_2024',None)]:
   expected=float(bm[('2024-senate',k)][bf]) if bf else int(r['cumulative_senate_2024'])/sum(int(z['senate_2024_total']) for z in pt)
   counts[pf]+=1
   if abs(float(r[pf])-expected)>1e-14:diff.append(dict(key=k,field=pf,own=expected,peer=r[pf]))
  c={z['native_candidate_name']:z for z in own if z['contest']=='2024-senate' and z['county_fips']==k}
  for pf,name in [('senate_2024_brown','TED BROWN'),('senate_2024_andrus_writein','TRACY ANDRUS'),('senate_2024_roche_writein','ANALISA ROCHE')]:
   counts[pf]+=1
   if r[pf]!=c[name]['votes']:diff.append(dict(key=k,field=pf,own=c[name]['votes'],peer=r[pf]))
 ctrl=readcsv(P/'county-ballot-registration-controls.csv');controlmap={(r['county_fips'],r['native_measure']):r for r in ctrl}
 for r in pt:
  k=r['county_fips']
  measuremap={'ballots_cast_2024':'Total Ballots Cast' if k=='48201' else 'Ballots Cast','registered_voters_2024':'Registered Voters','senate_2024_undervotes':'Undervotes','senate_2024_overvotes':'Overvotes'}
  for field,measure in measuremap.items():
   cell=controlmap.get((k,measure));expected=cell['value'] if cell else '';counts['optional_'+field]+=1
   if r[field]!=expected:diff.append(dict(key=k,field=field,own=expected,peer=r[field]))
  for field in ['ballots_cast_2022','registered_voters_2022','ballots_cast_2020','registered_voters_2020','registration_date_2024']:
   counts['optional_'+field]+=1
   if r[field]!='':diff.append(dict(key=k,field=field,own='',peer=r[field]))
  for field,measure in [('ballots_source_id_2024',measuremap['ballots_cast_2024']),('registration_source_id_2024','Registered Voters')]:
   cell=controlmap.get((k,measure));expected=cell['source_id'] if cell else '';counts['optional_'+field]+=1
   if r[field]!=expected:diff.append(dict(key=k,field=field,own=expected,peer=r[field]))
 op=json.loads((P/'priority-set.json').read_text());pp=json.loads((PEER/'priority-set.json').read_text())
 for key in ['full_order','priority_keys','minimum80_count','minimum80_votes','preceding_set_votes','top15_votes']:
  counts[key]+=1
  if op[key]!=pp[key]:diff.append(dict(key=key,field='priority',own=op[key],peer=pp[key]))
 if ['TX:'+r['county_fips'] for r in pt]!=op['full_order']:diff.append(dict(key='county CSV full order',field='order'))
 # Independent pinned MEDSL county/candidate comparison beyond statewide equality.
 med=list(csv.DictReader(io.StringIO(raw(PEER,'medsl-senate-county').decode('utf-8-sig'))));med=[r for r in med if r['state_po']=='TX']
 for r in med:
  key=('2024-senate',r['county_fips'],'TED CRUZ (I)' if r['candidate']=='TED CRUZ' else r['candidate']);a=om[key];counts['MEDSL_candidate_cell']+=1
  if a['votes']!=r['votes'] or a['county_contest_total']!=r['totalvotes']:diff.append(dict(key=key,field='MEDSL',own=a,peer=r))
 files=[P/'county-candidates.csv',DATA/'county-baselines.csv',PEER/'county-candidates-2024.csv',PEER/'county-candidates-comparators.csv',DATA/'county-turnout.csv',PEER/'priority-set.json',P/'county-ballot-registration-controls.csv']
 result=dict(status='pass' if not diff else 'fail',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),primary_candidate_cells=len(om),counties=len(pt),field_comparison_counts=dict(counts),mismatches=diff,hashes={str(f.relative_to(STATE)):sha(f.read_bytes()) for f in files},scope='independent primary extraction; all shared county candidate values/native labels/FIPS, full2024 volume order and exact80priority; no precinct equivalence')
 jwrite(P/'peer-reconciliation.json',result);print(result['status'],len(om),'candidate cells',sum(counts.values()),'field checks',len(diff),'mismatches');assert not diff,diff[:3]
if __name__=='__main__':main()
