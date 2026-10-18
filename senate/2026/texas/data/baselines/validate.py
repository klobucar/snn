#!/usr/bin/env python3
"""Offline integrity and arithmetic audit against retained primary evidence.
--verify-assets performs all checks read-only, including the finalized asset manifest.
"""
from build import *
from live_remainder import solve
from targets import calculate
import argparse,os

def near(a,b,tol=1e-7):
 assert abs(a-b)<=tol,(a,b,abs(a-b))
def main(verify_assets=False):
 checks={};sources=json.loads((P/'source-ledger.json').read_text())['sources']
 for s in sources:
  path=P/s['body_path'] if s.get('body_path') else None
  if path:body=path.read_bytes()
  else:
   chunks=[]
   for part in s['stored_parts']:
    bb=(P/part['path']).read_bytes();assert len(bb)==part['bytes']<40000000 and sha(bb)==part['sha256'];chunks.append(bb)
   body=b''.join(chunks)
  assert len(body)==s['stored_bytes'] and sha(body)==s['stored_sha256'],s['source_id']
  original=(P/s['original_body_path']).read_bytes() if 'original_body_path' in s else gzip.decompress(body) if path is None or path.suffix=='.gz' else body
  assert len(original)==s['original_bytes'] and sha(original)==s['original_sha256'],s['source_id']
  assert s.get('requested_url') and s.get('retrieved_at_utc') and 'response_headers' in s,s['source_id']
 checks['hash_checked_original_responses_and_references']=len(sources)
 ca=readcsv(P/'county-candidates.csv');bs=readcsv(DATA/'county-baselines.csv');controls=readcsv(P/'state-candidate-controls.csv');sc=readcsv(P/'county-target-scenarios.csv');st=readcsv(P/'state-target-scenarios.csv');p=json.loads((P/'priority-set.json').read_text())
 assert len(bs)==1016 and len(ca)==6604 and len(controls)==26
 assert len({(r['contest'],r['county_fips']) for r in bs})==len(bs)
 assert len({(r['contest'],r['county_fips'],r['native_candidate_name']) for r in ca})==len(ca)
 bm={(r['contest'],r['county_fips']):r for r in bs};cm=collections.defaultdict(list)
 for r in ca:cm[(r['contest'],r['county_fips'])].append(r)
 for contest,cfg in CONTESTS.items():
  # Re-read original primary PDF bytes; independently published statewide controls are never generated constants.
  state,total=state_extract(pdftext(cfg['root'],cfg['state_source']),cfg);county=extract(pdftext(cfg['root'],cfg['source']),cfg);expected={r['native_county']:r for r in county[:-1]}
  rr=[r for r in bs if r['contest']==contest];assert len(rr)==254 and len({r['county_fips'] for r in rr})==254
  near(sum(float(r['pair_weight']) for r in rr),1,1e-12);near(sum(float(r['candidate_vote_weight']) for r in rr),1,1e-12)
  for j,(literal,party,v) in enumerate(state):
   cells=[r for r in ca if r['contest']==contest and int(r['candidate_order'])==j+1];assert sum(int(r['votes']) for r in cells)==v
   control=next(x for x in controls if x['contest']==contest and x['native_candidate_name']==cfg['names'][j]);assert int(control['votes'])==v and int(control['difference'])==0 and control['state_publication_candidate_literal']==literal
  assert sum(int(r['candidate_votes']) for r in rr)==total
  for r in rr:
   cells=sorted(cm[(contest,r['county_fips'])],key=lambda x:int(x['candidate_order']));vals=[int(x['votes']) for x in cells];literal=expected[r['native_county_name']]
   assert vals==literal['values'][:-1] and int(r['candidate_votes'])==literal['values'][-1]
   assert int(r['d'])==vals[1] and int(r['r'])==vals[0] and int(r['other'])==sum(vals[2:])
   assert int(r['pair_votes'])==sum(vals[:2]);T=int(r['pair_votes']);V=sum(vals)
   assert T>0 and V>0;near(float(r['d_pair_share']),vals[1]/T,1e-14);near(float(r['pair_participation']),T/V,1e-14)
   assert all(r[k]=='' for k in ['ballots_cast','registered_voters','undervotes','overvotes','native_county_code'])
 checks['primary_candidate_county_cells']=len(ca);checks['primary_county_contest_rows']=len(bs);checks['independent_state_controls']=len(controls)
 # Independent external primary presentations: Clerk Senate and legislative governor.
 for year,textpath in [(2024,STATE.parent/'ohio/data/baselines/house-2024.txt'),(2020,STATE.parent/'michigan/data/baselines/house-statistics2020.txt')]:
  text=textpath.read_text();section=text.split('TEXAS',1)[1].split('FOR UNITED STATES SENATOR',1)[1].split('FOR UNITED STATES REPRESENTATIVE',1)[0];nums=[int(x.replace(',','')) for x in re.findall(r'([\d,]+)\s*$',section,re.M)];assert sorted(nums)==sorted(int(r['votes']) for r in controls if r['contest']==f'{year}-senate'),nums
 journal=raw(P,'journal-2022-governor').decode();txt=re.sub('<[^>]+>',' ',journal);txt=re.sub(r'\s+',' ',txt);section=txt.split('There were votes cast for governor, as follows:',1)[1].split('There were votes cast for lieutenant governor',1)[0];nums=[int(x.replace(',','')) for x in re.findall(r'\b\d[\d,]+\b',section)];v=[int(r['votes']) for r in controls if r['contest']=='2022-governor'];assert nums==v[:4]+[sum(v[4:])],(nums,v)
 checks['independent_primary_publications']='Clerk2020+2024 Senate; legislative2022 governor party candidates+combined namedwriteins'
 order=sorted([r for r in bs if r['contest']=='2024-senate'],key=lambda r:(-int(r['candidate_votes']),r['county_fips']));den=sum(int(r['candidate_votes']) for r in order);cum=0;keys=[];cross=None
 for i,r in enumerate(order,1):
  cum+=int(r['candidate_votes']);keys.append('TX:'+r['county_fips']);assert int(r['senate2024_volume_rank'])==i and int(r['senate2024_cumulative_votes'])==cum
  if cross is None and 5*cum>=4*den:cross=i
 assert keys==p['full_order'];assert keys[:cross]==p['priority_keys'];assert p['minimum80_count']==cross;assert sum(int(r['candidate_votes']) for r in order[:cross])==p['minimum80_votes'];assert 5*p['preceding_set_votes']<4*den<=5*p['minimum80_votes'];assert p['preceding_set_votes']+int(order[cross-1]['candidate_votes'])==p['minimum80_votes']
 checks['priority']={'denominator':den,'counties':cross,'votes':p['minimum80_votes'],'exact_integer_threshold':(4*den+4)//5,'full_order_checked':len(keys)}
 assert len(sc)==5334 and len(st)==21 and len({(r['scenario'],r['target'],r['county_fips']) for r in sc})==len(sc)
 for r in st:
  rr=[x for x in sc if x['scenario']==r['scenario'] and x['target']==r['target']];assert len(rr)==254;T=sum(float(x['expected_pair_votes']) for x in rr);V=sum(float(x['expected_all_candidate_votes']) for x in rr);near(T,float(r['pair_votes']));near(V,float(r['all_candidate_votes']));near(sum(float(x['pair_weight']) for x in rr),1,1e-12)
  achieved=0;unbounded=0
  for x in rr:
   t=float(x['expected_pair_votes']);s=float(x['baseline_pair_share']);part=float(x['pair_participation']);near(t,float(x['expected_all_candidate_votes'])*part)
   preference=r['preference_baseline'];br=bm[(preference,x['county_fips'])];near(s,float(br['d_pair_share']),1e-14);near(part,float(br['pair_participation']),1e-14)
   volume=next(y for y in bs if y['contest']==r['volume_basis'] and y['county_fips']==x['county_fips']);near(float(x['expected_all_candidate_votes']),int(volume['candidate_votes']))
   q=float(x['bounded_target_share']);u=float(x['unbounded_target_share']);assert 0<=q<=1;net=t*(2*q-1);near(net,float(x['bounded_target_net']));near(.02*t,float(x['one_pp_share_net_gain']));near(float(x['net_gain']),net-float(x['baseline_net']));achieved+=net;unbounded+=t*(2*u-1)
   cq=float(x['selected_only_required_share']);other=float(r['baseline_net'])-float(x['baseline_net']);near(other+t*(2*cq-1),float(r['target_net']));status='impossible' if cq>1 else 'already-secured' if cq<0 else 'feasible';assert x['selected_only_status']==status
  near(achieved,float(r['target_net']),1e-6);near(unbounded,float(r['target_net']),1e-6);near(float(r['target_pair_margin'])*T,float(r['target_net']));near(float(r['target_all_candidate_margin'])*V,float(r['target_net']))
  if r['target']=='A+1-pair-margin':
   tie=next(x for x in st if x['scenario']==r['scenario'] and x['target']=='tie');near(float(r['unbounded_shift_share_pp'])-float(tie['unbounded_shift_share_pp']),.5,1e-12)
 checks['scenario_county_rows']=len(sc);checks['state_targets']=len(st)
 # Stress behavior cannot pass merely by mirroring generated actual-scenario constants.
 sol=solve_uniform([.99,.01],[1.,1.],.5);assert sol['clipped']==1 and sol['bounded']>sol['unbounded'];near(sum(2*min(1,max(0,s+sol['bounded']))-1 for s in [.99,.01]),1,1e-12)
 assert solve_uniform([.6],[10.],0)['status']=='already-winning';assert solve_uniform([],[],0)['status']=='no-positive-pool';assert conditional(0,10,0,0)==(None,'no-positive-pool');assert conditional(1,10,-9,0)[1]=='impossible';assert conditional(1,10,9,0)[1]=='already-secured'
 ex=json.loads((P/'live-examples.json').read_text());statuses=collections.Counter()
 for c in ex['cases']:
  result=solve(**c['input']);assert result==c['result'];statuses[result['status']]+=1
  if 'counted_unchanged' in result:assert result['counted_unchanged']==c['input']['counted']
  if result['status']=='feasible':
   q=result['required_share'];net=result['counted_net']+result['other_units_net']+result['solved_pool']*(2*q-1);near(net,result['target_net'],1e-7);near(net/result['final_denominator'],result['target_margin'],1e-12)
 assert all(statuses[x]>0 for x in ['feasible','unknown-remaining-input','invalid-remaining-input','no-positive-pool','already-secured','impossible','no-positive-final-denominator'])
 assert solve({'A':1,'B':2,'other':0},[{'unit':'x','pair_votes':2,'other_votes':None}],.01,'all-candidate')['status']=='unknown-remaining-input'
 checks['live_edge_cases']=dict(statuses);checks['clipping_zero_pool_already_winning_stress']='pass'
 # Reconstruct native inventory directly from every original source row; don't compare only generated constants.
 with gzip.open(P/'native-units.csv.gz','rt') as f:units=list(csv.DictReader(f))
 um={(u['source_id'],u['native_county_name'],u['native_unit_id']):u for u in units};assert len(um)==len(units)==31702
 from native_evidence import OFFICES,MEASURES,NORM
 files=[(f.name.split('.')[0],f,'2024') for f in sorted((PEER/'raw').glob('oe2024-*.body.gz'))]+[(f'oe-tx{y}',PEER/'raw'/f'oe-tx{y}.body.gz',y) for y in ['2020','2022']];nativecounts={}
 for year in ['2024','2020','2022']:
  counts=collections.Counter();selected={}
  for source,path,y in files:
   if y!=year:continue
   with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
    for rn,r in enumerate(csv.DictReader(f),2):
     if r.get('county')=='county' and r.get('office')=='office':continue
     counts[(source,r.get('county',''),r.get('precinct',''))]+=1
     if NORM(r.get('office','')) in OFFICES[year]|MEASURES:selected[(source,rn)]=r
  for k,n in counts.items():assert k in um and int(um[k]['source_rows'])==n
  got=set()
  with gzip.open(P/f'native-cells-{year}.jsonl.gz','rt') as f:
   for line in f:
    r=json.loads(line);key=(r['source_id'],r['source_row']);assert key not in got and selected[key]==r['source_fields'];got.add(key)
  assert got==set(selected);nativecounts[year]=dict(units=len(counts),selected_rows=len(got))
 checks['native_original_retention']=nativecounts
 with gzip.open(P/'tlc-vtd-cells.csv.gz','rt') as f:vtd=list(csv.DictReader(f))
 groups=collections.defaultdict(list)
 for r in vtd:groups[r['source_id']].append(r)
 assert len(groups)==5
 for name,rr in groups.items():assert len(rr)==9712 and len({(r['CNTYVTD'],r['VTDKEY']) for r in rr})==9712 and len({r['county_fips'] for r in rr})==254
 checks['tlc_derived_rows_preserved']=len(vtd)
 audit=json.loads((P/'primary-unit-audit.json').read_text());assert not audit['vendor_peer_differences'];assert all(not r['peer_label_absent'] for r in audit['pdf_checks']);checks['primary_unit_audit']=dict(vendor_shared_rows=audit['vendor_peer_rows_compared'],pdf_unit_labels=sum(r['independently_observed_labels'] for r in audit['pdf_checks']),scope=audit['scope'])
 with gzip.open(P/'harris-primary-senate-unit-controls.csv.gz','rt') as f:hu=list(csv.DictReader(f))
 assert len(hu)==len({r['native_unit_id'] for r in hu})==1584
 hmap={'TED CRUZ':'TED CRUZ (I)','COLIN ALLRED':'COLIN ALLRED','TED BROWN':'TED BROWN','Analisa Roche (W)':'ANALISA ROCHE','Tracy Andrus (W)':'TRACY ANDRUS'}
 for rawname,canonical in hmap.items():assert sum(int(r[rawname]) for r in hu)==int(next(r['votes'] for r in ca if r['contest']=='2024-senate' and r['county_fips']=='48201' and r['native_candidate_name']==canonical))
 for r in hu:
  assert sum(int(r[n]) for n in hmap)==int(r['Cast Votes'])
  assert int(r['Cast Votes'])+int(r['Undervotes'])+int(r['Overvotes'])==int(r['Total Ballots Cast'])
  assert sum(int(r[n]) for n in ['Ballot by Mail Ballots Cast','Early Voting Ballots Cast','Election Day Ballots Cast','EV Provisional Ballots Cast','ED Provisional Ballots Cast'])==int(r['Total Ballots Cast'])
 checks['primary_harris_all_unit_candidate_ballot_method_controls']=len(hu)
 peer=json.loads((P/'peer-reconciliation.json').read_text());assert peer['status']=='pass' and not peer['mismatches'];checks['peer_candidate_county_checks']=sum(peer['field_comparison_counts'].values())
 # Local Markdown relative links must resolve; HTTP URLs were retained as source provenance.
 mdpaths=[STATE/'county-partisanship.md',P/'SCHEMA.md'];links=0
 for path in mdpaths:
  for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
   if re.match(r'\w+://',target) or target.startswith('#'):continue
   target=target.split('#')[0];assert (path.parent/target).exists(),(path,target);links+=1
 checks['local_relative_links']=links
 owned=[STATE/'county-partisanship.md',DATA/'county-baselines.csv']+[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts];assert all(f.stat().st_size<40000000 for f in owned)
 checks['largest_owned_asset_bytes']=max(f.stat().st_size for f in owned)
 # Narrative numerical examples must match actual retained settings and live fixtures.
 report=(STATE/'county-partisanship.md').read_text()
 assert f"{calculate('base-2024-senate-volume','48113')['required_selected_pair_share']*100:.6f}%" in report
 for case in ex['cases'][8:11]:
  pct=case['result']['required_share']*100;assert (f'{pct:.4f}%' in report or f'{pct:.6f}%' in report),pct
 checks['report_settings_and_live_examples']='pass'
 if verify_assets:
  manifest=json.loads((P/'asset-manifest.json').read_text());expected={os.path.relpath(f,STATE) for f in owned if f.name!='asset-manifest.json'};assert {r['path'] for r in manifest['assets']}==expected
  for a in manifest['assets']:
   f=STATE/a['path'];assert f.stat().st_size==a['bytes']<40000000 and sha(f.read_bytes())==a['sha256'],a['path']
  print('PASS; asset manifest',len(manifest['assets']),'files; allsource/county/unit/scenario checks');return
 result=dict(status='pass',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,limitations=['Historical scenario arithmetic, not2026 forecast or probabilities.','All254 primary county baselines reconcile; incomplete native precinct originals, duplicatekeys/methodnonadditivity and sourcecounty conflicts remain unaccepted.','Genericwritein vendor/TLC universes are not silently replaced by named validwriteins.','No cross-year/2026 geography approval, candidate roster mapping or feedcadence established.']);jwrite(P/'validation.json',result);print('PASS',json.dumps(checks))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--verify-assets',action='store_true');args=a.parse_args();main(args.verify_assets)
