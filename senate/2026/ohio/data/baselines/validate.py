#!/usr/bin/env python3
"""Independent offline audit: direct XML DOM, House publication totals, saved hashes,
all county/unit coverage, weights, threshold, scenario arithmetic, bound cases.
Does not import the extraction implementation for any source comparisons.
"""
import argparse,collections,csv,datetime,gzip,hashlib,io,json,math,pathlib,re,zipfile,xml.etree.ElementTree as E
from decimal import Decimal as D
ROOT=pathlib.Path(__file__).resolve().parent
DATA=ROOT.parent
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def rows(path):
 b=path.read_bytes();s=gzip.decompress(b).decode() if path.suffix=='.gz' else b.decode()
 return list(csv.DictReader(io.StringIO(s)))
def source_master(path):
 # Independent DOM implementation and direct known Master sheet2; no xlsx_read.
 with zipfile.ZipFile(path) as z:
  ss=[''.join(t.itertext()) for t in E.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',N)]
  xml=E.fromstring(z.read('xl/worksheets/sheet2.xml'))
  cells={c.attrib['r']:ss[int(c.findtext('s:v',default='',namespaces=N))] if c.attrib.get('t')=='s' else c.findtext('s:v',default='',namespaces=N) for c in xml.findall('.//s:c',N)}
 return cells

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--require-turnout',action='store_true');args=ap.parse_args();counts=collections.Counter();notes=[]
 def check(ok,name,detail=''):
  assert ok,(name,detail)
  counts[name]+=1
 def close(a,b,tol=1e-6):return abs(float(a)-float(b))<=tol
 # Raw/header hashes, not just self-consistency of derivatives.
 for e in json.loads((ROOT/'shared-input-manifest.json').read_text()):
  p=ROOT/e['local_path'];check(hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'],'shared_primary_hash',str(p));check(e['status']==200,'shared_primary_http_200',str(p))
 for p in (ROOT/'raw').glob('*.meta.json'):
  e=json.loads(p.read_text());raw=ROOT/e['stored_path'] if e.get('stored_path') else p.with_name(p.name.removesuffix('.meta.json'))
  if e.get('sha256_stored'):check(hashlib.sha256(raw.read_bytes()).hexdigest()==e['sha256_stored'],'owned_response_hash',str(p))
  if e.get('sha256_decoded'):
   b=gzip.decompress(raw.read_bytes()) if raw.suffix=='.gz' else raw.read_bytes()
   check(hashlib.sha256(b).hexdigest()==e['sha256_decoded'],'owned_decoded_response_hash',str(p))
 for p in ROOT.rglob('*'):
  if p.is_file():check(p.stat().st_size<40*1024*1024,'individual_asset_under_40MiB',str(p))
 baseline=rows(DATA/'county-baselines.csv');candidate=rows(ROOT/'candidate-universe.csv');votes=rows(ROOT/'candidate-votes.csv');schema=json.loads((ROOT/'source-schema.json').read_text());raws={}
 for s in schema:
  path=s['source_path'];raws.setdefault(path,source_master(ROOT/path))
 for r in votes:
  coord=r['source_cell'].split('!')[1]
  check(int(raws[r['source_path']][coord])==int(r['votes']),'independent_raw_candidate_county_cell',r)
  col=re.sub('[0-9]','',coord);check(raws[r['source_path']][col+'2']==r['source_candidate_label'],'independent_raw_candidate_label',r['comparison'])
 for r in candidate:
  col=re.sub('[0-9]','',r['native_candidate_key'].split('!')[1]);check(int(raws[r['source_path']][col+'3'])==int(r['statewide_votes']),'independent_raw_state_total',r['candidate_name_normalized'])
 census=list(csv.DictReader(gzip.decompress((ROOT/'raw/census-counties-2020.txt.gz').read_bytes()).decode().splitlines(),delimiter='|'));fips={r['COUNTYNAME'].removesuffix(' County'):r['STATEFP']+r['COUNTYFP'] for r in census if r['STATEFP']=='39'}
 check(len(baseline)==440,'all_baseline_row_count');check(len(votes)==2992,'all_candidate_county_row_count');check(len(candidate)==34,'all_candidate_vintage_count')
 by={k:{r['county']:r for r in baseline if r['comparison']==k} for k in {r['comparison'] for r in baseline}}
 for k,rs in by.items():
  check(set(rs)==set(fips),'all88_county_coverage',k);check(len(rs)==88,'all88_county_uniqueness',k)
  check(close(sum(float(r['statewide_major_party_weight']) for r in rs.values()),1,1e-14),'major_weights_sum_one',k)
  check(close(sum(float(r['statewide_contest_weight']) for r in rs.values()),1,1e-14),'contest_weights_sum_one',k)
  for r in rs.values():
   check(r['county_fips']==fips[r['county']],'census_fips_match',r['county'])
   check(int(r['d_votes'])+int(r['r_votes'])+int(r['other_votes'])==int(r['all_candidate_votes']),'d_r_other_balance',r['county'])
   check(int(r['d_votes'])+int(r['r_votes'])==int(r['two_party_votes']),'two_party_balance',r['county'])
   check(0<=int(r['all_candidate_votes'])<=int(r['ballots_counted_or_total_voters']),'contest_vs_ballots_bounds',r['county'])
   check(close(float(r['d_share_two_party']),int(r['d_votes'])/int(r['two_party_votes']),1e-14),'independent_share',r['county'])
 # Independently parse each Senate candidate line from the primary House PDF text.
 housechecks=[]
 for y,key in [(2024,'2024_senate'),(2022,'2022_senate'),(2018,'2018_senate_original')]:
  s=(ROOT/f'house-{y}.txt').read_text();sec=s.split('OHIO',1)[1].split('FOR UNITED STATES REPRESENTATIVE',1)[0]
  for c in [r for r in candidate if r['comparison']==key]:
   name=c['candidate_name_normalized'];alias='James B. Renacci' if name=='Jim Renacci' else name
   lines=[l for l in sec.splitlines() if re.search(re.escape(alias)+',',l)]
   check(len(lines)==1,'house_candidate_identity',alias)
   n=int(re.findall(r'[0-9][0-9,]*',lines[0])[-1].replace(',',''));found=sum(int(r['votes']) for r in votes if r['comparison']==key and r['candidate_name_normalized']==name)
   check(found==n,'independent_house_candidate_total',alias)
   housechecks.append({'comparison':key,'candidate':name,'house_alias':alias,'county_sum':found,'house_published':n,'difference':found-n,'status':'exact'})
 # Presidential House publication reports party group totals, not all ticket names.
 sec=(ROOT/'house-2024.txt').read_text().split('OHIO',1)[1].split('FOR UNITED STATES SENATOR',1)[0]
 party_groups={'Republican':('R',),'Democratic':('D',),'Libertarian':('L',),'No Party':('not_displayed',),'Write-in':('WI',)}
 for label,ps in party_groups.items():
  line=[l for l in sec.splitlines() if re.match(r'\s*'+re.escape(label)+r'\s*\.',l)][0];n=int(re.findall(r'[0-9][0-9,]*',line)[-1].replace(',',''));found=sum(int(c['statewide_votes']) for c in candidate if c['comparison']=='2024_president' and c['party_source'] in ps)
  check(found==n,'independent_house_presidential_party_total',label);housechecks.append({'comparison':'2024_president','candidate':label,'house_alias':label,'county_sum':found,'house_published':n,'difference':found-n,'status':'exact_party_group'})
 # Amended Miami differs from the earlier House publication, not an unexplained error.
 for f in ['d_votes','r_votes','other_votes','all_candidate_votes','ballots_counted_or_total_voters','registered_voters']:
  old=by['2018_senate_original'];new=by['2018_senate_amended'];diff={c:int(new[c][f])-int(old[c][f]) for c in old if new[c][f]!=old[c][f]}
  check(set(diff)<= {'Miami'},'2018_revision_only_miami',f)
 write_csv(ROOT/'house-reconciliation.csv',housechecks)
 units=rows(ROOT/'native-reporting-units.csv.gz');seen=set();unit_sums=collections.Counter();yearcount=collections.Counter()
 for r in units:
  k=(r['election_year'],r['county_fips'],r['native_precinct_code']);check(k not in seen,'native_unit_unique_composite',k);seen.add(k);yearcount[r['election_year']]+=1
  for f in ['registered_voters','ballots_counted']:unit_sums[r['election_year'],r['county'],f]+=int(r[f])
 check(dict(yearcount)=={'2024':8878,'2022':8933},'native_unit_vintage_counts')
 for y in ['2024','2022']:
  for c,r in by[y+'_senate'].items():
   for f,bf in [('registered_voters','registered_voters'),('ballots_counted','ballots_counted_or_total_voters')]:check(unit_sums[y,c,f]==int(r[bf]),'native_unit_county_denominator_reconciliation',(y,c,f))
 for r in rows(ROOT/'precinct-county-checks.csv'):
  check(int(r['summary_minus_precinct'])==int(r['county_summary'])-int(r['precinct_sum']),'precinct_summary_difference_arithmetic')
  check(int(r['summary_minus_precinct'])==0 or r['explanation']=='explicitly omitted write-ins','precinct_omissions_explained')
 states=rows(ROOT/'state-scenarios.csv');targets=rows(ROOT/'county-target-scenarios.csv');conditional=rows(ROOT/'selected-county-targets.csv')
 for s in states:
  rs=[r for r in targets if r['scenario']==s['scenario'] and r['target_two_party_margin']==s['target_two_party_margin']]
  check({r['county'] for r in rs}==set(fips),'scenario_all88_coverage',s['scenario'])
  t=sum(D(r['scenario_major_party_votes']) for r in rs);net=sum(D(r['scenario_major_party_votes'])*(2*D(r['target_d_share_two_party'])-1) for r in rs);m=D(s['target_two_party_margin'])
  check(close(net,m*t),'independent_target_net_sum',s['scenario']);check(close(sum(D(r['statewide_weight']) for r in rs),1,1e-14),'scenario_weight_sum_one')
  base=sum(D(r['scenario_major_party_votes'])*(2*D(r['baseline_d_share_two_party'])-1) for r in rs);shift=(m*t-base)/(2*t)
  check(close(shift,s['uniform_d_share_shift'],1e-14),'independent_uniform_shift')
  for r in rs:
   pref=by[s['preference_comparison']][r['county']];mix=by[s['turnout_mix_comparison']]
   expected_t=D(s['scenario_major_party_votes'])*D(mix[r['county']]['two_party_votes'])/sum(D(x['two_party_votes']) for x in mix.values())
   check(close(expected_t,r['scenario_major_party_votes']),'independent_scenario_county_turnout_weight')
   check(close(D(pref['d_votes'])/D(pref['two_party_votes']),r['baseline_d_share_two_party'],1e-14),'independent_scenario_preference_from_counts')
   check(close(D(r['scenario_major_party_votes'])*(2*D(r['target_d_share_two_party'])-1),r['target_net_votes']),'independent_county_net_contribution')
   check(close(D(r['scenario_major_party_votes'])*D('.02'),r['net_gain_per_1pp_d_share']),'independent_1pp_share_net_effect')
   check(close(D(r['target_d_share_two_party'])-D(r['baseline_d_share_two_party']),shift,1e-14),'county_uniform_shift')
   check(0<=float(r['target_d_share_two_party'])<=1,'historical_uniform_target_bounds')
  for r in [r for r in conditional if r['scenario']==s['scenario'] and r['target_two_party_margin']==s['target_two_party_margin']]:
   q=D(r['selected_required_d_share']);tc=D(r['selected_major_party_votes']);rest=D(r['all_other_counties_net_votes'])
   check(close(rest+tc*(2*q-1),m*t),'independent_selected_target_arithmetic')
   # Check reachable margin interval at the two physical endpoints.
   lo,hi=rest-tc,rest+tc
   expected='already_secured' if m*t<lo else 'impossible' if m*t>hi else 'feasible'
   check(r['status']==expected,'selected_status_physical_endpoints')
 same_mix=[s for s in states if s['preference_comparison']=='2024_senate' and s['turnout_mix_comparison']=='2024_senate' and s['target_two_party_margin']=='0']
 check(len(same_mix)==3,'three_observed_volume_anchors')
 check(max(float(s['uniform_d_share_shift']) for s in same_mix)-min(float(s['uniform_d_share_shift']) for s in same_mix)<1e-14,'uniform_volume_scale_invariance')
 # Direct formula on actual counts, with D+1 requiring half a D-share point more.
 for key in by:
  d=sum(int(r['d_votes']) for r in by[key].values());r=sum(int(x['r_votes']) for x in by[key].values());tie=(r-d)/(2*(d+r))
  check(close((tie+.005)-tie,.005,1e-15),'share_vs_margin_half_point')
 for r in rows(ROOT/'third-candidate-denominators.csv'):
  d,rr,o=(sum(int(x[f]) for x in by[r['comparison']].values()) for f in ['d_votes','r_votes','other_votes'])
  shift=D(r['uniform_d_share_shift']);net=D(r['required_d_minus_r_net_votes'])
  check(close(d-rr+2*D(d+rr)*shift,net),'third_candidate_transfer_arithmetic')
  check(close(net/D(d+rr),r['target_two_party_margin']),'third_candidate_two_party_denominator')
  check(close(net/D(d+rr+o),r['target_all_candidate_margin']),'third_candidate_all_vote_denominator')
 # Exercise the user-adjustable function, including saturation cases and zero T.
 import calculate
 for shares,T,selected,m,held,expected_status in [({'A':.5,'B':.5},{'A':1,'B':10},'A',0,{'B':1},'already_secured'),({'A':.5,'B':.5},{'A':1,'B':10},'A',0,{'B':0},'impossible'),({'A':.6,'B':.4},{'A':100,'B':100},'A',.01,{},'feasible')]:
  q,status,rest=calculate.selected_share(shares,T,selected,m,held);check(status==expected_status,'calculator_bound_case',expected_status)
  check(close(rest+T[selected]*(2*q-1),m*sum(T.values())),'calculator_held_override_arithmetic')
 try:calculate.selected_share({'A':.5},{'A':0},'A');raise RuntimeError('zero denominator accepted')
 except AssertionError:counts['calculator_zero_denominator_rejected']+=1
 p=json.loads((ROOT/'priority-set.json').read_text());rank=sorted(by['2024_senate'].values(),key=lambda r:-int(r['all_candidate_votes']));t=sum(int(r['all_candidate_votes']) for r in rank)
 check(sum(int(r['all_candidate_votes']) for r in rank[:31])<.8*t<=sum(int(r['all_candidate_votes']) for r in rank[:32]),'min80_threshold');check([r['county'] for r in rank[:32]]==p['counties'],'priority_order_independent');check(t==5704620,'certified_contest_denominator')
 turnout=DATA/'county-turnout.csv';turnout_status='pending_stable_worker_output'
 if turnout.exists():
  tr=rows(turnout)
  notes.append({'turnout_csv_headers':list(tr[0])})
  # Populate only after turnout worker confirms stable schema; do not infer denominators.
  contract=ROOT/'turnout-schema-contract.json'
  if contract.exists():
   cfg=json.loads(contract.read_text());tr=[r for r in tr if all(r[k]==v for k,v in cfg.get('filters',{}).items())];check(len(tr)==88,'turnout_all88_row_count');out=[]
   check({r[cfg['county']] for r in tr}==set(fips),'turnout_all88_county_coverage')
   for r in tr:
    c=r[cfg['county']]
    for a,definition in cfg['fields'].items():
     comp,bf=definition;b=by[comp][c];x,y=r[a],b[bf];check(str(x)==str(y),'independent_turnout_county_cell',(c,a,x,y));out.append({'county':c,'turnout_column':a,'baseline_column':comp+':'+bf,'turnout_value':x,'baseline_value':y,'difference':int(x)-int(y) if str(x).isdigit() and str(y).isdigit() else 0})
    for a,(comp,bf) in cfg['ranks'].items():
     expected=next(i for i,x in enumerate(sorted(by[comp].values(),key=lambda x:-int(x[bf])),1) if x['county']==c)
     check(int(r[a])==expected,'independent_turnout_rank',(c,a));out.append({'county':c,'turnout_column':a,'baseline_column':comp+':rank('+bf+')','turnout_value':r[a],'baseline_value':expected,'difference':int(r[a])-expected})
    rankindex=next(i for i,x in enumerate(rank,1) if x['county']==c)
    for a,limit in [('in_top15',15),('in_minimum80',32)]:
     expected=int(rankindex<=limit);check(int(r[a])==expected,'independent_turnout_priority_flag',(c,a));out.append({'county':c,'turnout_column':a,'baseline_column':'computed_rank_threshold','turnout_value':r[a],'baseline_value':expected,'difference':int(r[a])-expected})
    cv=[x for x in votes if x['county']==c]
    for y in ['2024','2022']:
     expected=sum(int(x['votes']) for x in cv if x['comparison']==y+'_senate' and x['party_source']=='WI');a='senate_'+y+'_writein_votes';check(int(r[a])==expected,'independent_turnout_writein',(c,a));out.append({'county':c,'turnout_column':a,'baseline_column':y+'_senate:writein_sum','turnout_value':r[a],'baseline_value':expected,'difference':int(r[a])-expected})
    cum=sum(int(x['all_candidate_votes']) for x in rank[:rankindex]);check(int(r['senate_2024_cumulative_votes'])==cum,'independent_turnout_cumulative_count',c)
    check(close(float(r['senate_2024_state_share_percent']),100*int(by['2024_senate'][c]['all_candidate_votes'])/t,1e-8),'independent_turnout_share_percent',c)
    check(close(float(r['senate_2024_cumulative_share_percent']),100*cum/t,1e-8),'independent_turnout_cumulative_percent',c)
    check(r['senate_2024_state_share_fraction']==str(by['2024_senate'][c]['all_candidate_votes'])+'/'+str(t),'independent_turnout_exact_fraction',c)
   write_csv(ROOT/'turnout-worker-reconciliation.csv',out);turnout_status='exact_all88_confirmed_schema'
   other=rows(DATA/'turnout/county-candidate-votes.csv');our={(x['election_date'],x['comparison'].split('_')[1],x['county_fips'],x['source_candidate_label']):x for x in votes if x['comparison'] in ['2024_senate','2024_president','2022_senate']};compared=[]
   for r in other:
    # Final contract supplies source-native labels and columns; preserve full labels.
    key=(r['election_date'],r['contest_key'],r['county_fips'],r['candidate_native_label'])
    check(key in our,'worker_candidate_key_exists',key);u=our[key]
    check(int(r['votes'])==int(u['votes']),'worker_candidate_cell_exact',key)
    check(r['candidate_native_column']==re.sub('[0-9]','',u['source_cell'].split('!')[1]),'worker_candidate_native_column_exact',key)
    check(r['write_in'].lower()==str(u['party_source']=='WI').lower(),'worker_candidate_writein_status_exact',key)
    compared.append({'election_date':r['election_date'],'contest':r['contest_key'],'county_fips':r['county_fips'],'candidate':r['candidate_native_label'],'turnout_votes':r['votes'],'baseline_votes':u['votes'],'difference':int(r['votes'])-int(u['votes'])})
   check(len(other)==len(our)==2464,'worker_full_candidate_coverage');check(len({(r['election_date'],r['contest_key'],r['county_fips'],r['candidate_native_label']) for r in other})==len(other),'worker_candidate_unique_keys')
   write_csv(ROOT/'turnout-worker-candidate-reconciliation.csv',compared)
   other_priority=json.loads((DATA/'turnout/priority-set.json').read_text())
   check(other_priority['ordered_county_keys_all88']==[r['county_fips'] for r in rank],'worker_all88_order_exact')
   check(other_priority['ordered_priority_county_keys']==[r['county_fips'] for r in rank[:32]],'worker_priority32_order_exact')
   for k,expected in [('statewide_votes',5704620),('top15_votes',3525320),('minimum80_count',32),('minimum80_votes',4581738),('previous_votes',4542798)]:check(other_priority[k]==expected,'worker_priority_primary_totals',k)
   unitchecks=[]
   for r in other_priority['county_records']:
    for year,info in r['reporting_units'].items():
     ours={(x['native_precinct_code'],x['native_precinct_name'],int(x['source_row'])) for x in units if x['election_year']==year and x['county_fips']==r['county_fips']}
     theirs={(x['precinct_code_native'],x['precinct_name_native'],x['source_row']) for x in info['units']}
     check(ours==theirs,'worker_native_units_exact',(year,r['county_fips']))
     digest=hashlib.sha256(json.dumps(sorted(ours),separators=(',',':')).encode()).hexdigest()
     unitchecks.append({'election_year':year,'county_fips':r['county_fips'],'county':r['county_native_id'],'unit_count':len(ours),'symmetric_difference_count':len(ours^theirs),'sha256_sorted_code_name_row_tuples':digest})
   write_csv(ROOT/'turnout-worker-unit-reconciliation.csv',unitchecks)
   summary={'status':'EXACT_NO_DIFFERENCES','validated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'county_count':88,'county_field_comparisons_saved':len(out),'candidate_cells_compared':len(compared),'candidate_key_label_column_and_writein_status':'all exact','native_unit_count':sum(r['unit_count'] for r in unitchecks),'priority_count':32,'priority_order_and_all88_rank_order':'exact','statewide_totals':{},'stable_files':[]}
   for key,column in [('2024_senate','senate_2024_votes'),('2024_president','president_2024_votes'),('2022_senate','senate_2022_votes')]:
    ours=sum(int(r['all_candidate_votes']) for r in by[key].values());theirs=sum(int(r[column]) for r in tr)
    summary['statewide_totals'][key]={'baseline_sum':ours,'turnout_sum':theirs,'difference':theirs-ours}
   for path in [DATA/'county-turnout.csv',DATA/'turnout/county-candidate-votes.csv',DATA/'turnout/priority-set.json',DATA/'county-baselines.csv',ROOT/'candidate-votes.csv']:
    summary['stable_files'].append({'path':str(path.relative_to(DATA)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
   (ROOT/'turnout-worker-reconciliation.json').write_text(json.dumps(summary,indent=2)+'\n')
 if args.require_turnout:check(turnout_status=='exact_all88_confirmed_schema','turnout_worker_final_reconciliation_required')
 result={'run_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS' if turnout_status=='exact_all88_confirmed_schema' else 'PASS_core_PENDING_turnout_schema','checks_passed':sum(counts.values()),'check_counts':dict(counts),'native_unit_counts':dict(yearcount),'turnout_reconciliation_status':turnout_status,'notes':notes,'scope':'historical evidence and deterministic scenarios only; no probability calibration, 2026 precinct approval or live collector validation'}
 (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

def write_csv(p,rs):
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
if __name__=='__main__':main()
