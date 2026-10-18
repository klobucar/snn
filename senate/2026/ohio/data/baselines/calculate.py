#!/usr/bin/env python3
"""Offline Ohio historical county extraction and deterministic sensitivity calculator.

Run from any directory. Python standard library only; no network and no Git.
Raw official workbooks in ../turnout/raw are shared read-only, pinned by manifest.
"""
import argparse, collections, csv, gzip, hashlib, io, json, math, pathlib, re
from xlsx_read import Book

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT.parent
SPECS = {
 '2024_senate': (2024,'2024-11-05','../turnout/raw/2024-summary-archive.xlsx','AA AB AC AD AE AF AG','U.S. Congress','G H I J K L M','official_certified_archived'),
 '2024_president': (2024,'2024-11-05','../turnout/raw/2024-summary-archive.xlsx','G H I J K L M N O P Q R S T','President and Vice President','G H I J K L M N O P Q R S T','official_certified_archived'),
 '2022_senate': (2022,'2022-11-08','../turnout/raw/2022-statewide-races-summary.xlsx','AB AC AD AE AF AG AH','U.S. Congress','G H I J K L M','official_certified_archived'),
 '2018_senate_original': (2018,'2018-11-06','raw/2018-statewidecounty.xlsx','Y Z AA','U.S. Congress','G H I','original_certification_superseded_miami'),
 '2018_senate_amended': (2018,'2018-11-06','raw/2018-statewidecounty-miami-recovered.xlsx','Y Z AA','U.S. Congress','G H I','official_miami_amendment_2019-01-22'),
}
PRECINCTS={2024:'../turnout/raw/2024-statewide-races-precint-level.xlsx',2022:'../turnout/raw/2022-statewide-races-by-precinct.xlsx'}

def write_csv(path,rows):
 rows=list(rows)
 assert rows,path
 s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 b=s.getvalue().encode()
 path.write_bytes(gzip.compress(b,mtime=0) if path.suffix=='.gz' else b)

def norm(s): return ' '.join(s.split())
def party(label):
 m=re.search(r'\((D|R|L|WI)\)',label)
 return m.group(1) if m else 'not_displayed'
def number(v):
 assert v!='','Missing numeric source cell'
 i=int(v);assert str(i)==v and i>=0,v
 return i
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def fips_table():
 s=gzip.decompress((ROOT/'raw/census-counties-2020.txt.gz').read_bytes()).decode()
 return {r['COUNTYNAME'].removesuffix(' County'):r for r in csv.DictReader(s.splitlines(),delimiter='|') if r['STATEFP']=='39'}

def extract():
 census=fips_table();assert len(census)==88
 baselines=[];votes=[];candidates=[];checks=[];headers=[]
 for key,(year,date,path,columns,side,sidecols,status) in SPECS.items():
  b=Book(ROOT/path);master=dict(b.rows('Master'));sr=dict(b.rows(side));cols=columns.split();sc=sidecols.split()
  assert len(cols)==len(sc)
  header=master[2];counties=[(i,r) for i,r in master.items() if r.get('A') in census]
  assert len(counties)==88 and len({r['A'] for _,r in counties})==88
  side_rows={r['A']:r for _,r in sr.items() if r.get('A') in census}
  headers.append({'comparison':key,'source_path':path,'master_header':master[1]['A'],'native_contest_label':master[1][cols[0]],'candidate_columns':cols,'native_numeric_election_id':None,'native_numeric_contest_id':None,'identifier_note':'Workbook has no numeric election/contest/candidate/county IDs. Native county name and sheet/column/row coordinates retained; local comparison key is a derivative, not a native ID.'})
  for col,sidecol in zip(cols,sc):
   assert header[col]==sr[2][sidecol],(key,col,'side-label')
   label=header[col];p=party(label);name=norm(re.sub(r'\s*\((D|R|L|WI)\)\*?','',label))
   total=number(master[3][col]);calc=sum(number(r[col]) for _,r in counties)
   assert calc==total,(key,label,calc,total)
   candidates.append({'comparison':key,'election_date':date,'native_contest_label':master[1][cols[0]].strip(),'source_candidate_label':label,'candidate_name_normalized':name,'party_source':p,'write_in':int(p=='WI'),'statewide_votes':total,'native_candidate_key':f'Master!{col}2','source_path':path,'source_status':status})
   checks.append({'check':'county_sum_vs_published_statewide','comparison':key,'county':'STATE','candidate':label,'observed':calc,'expected':total,'difference':calc-total})
   for row,r in counties:
    n=number(r[col]);assert n==number(side_rows[r['A']][sidecol]),(key,r['A'],col,'side sheet')
    c=census[r['A']]
    votes.append({'comparison':key,'election_date':date,'county':r['A'],'county_fips':c['STATEFP']+c['COUNTYFP'],'native_county_name':r['A'],'source_candidate_label':label,'candidate_name_normalized':name,'party_source':p,'votes':n,'source_cell':f'Master!{col}{row}','source_path':path,'source_status':status})
  state_d=sum(c['statewide_votes'] for c in candidates if c['comparison']==key and c['party_source']=='D')
  state_r=sum(c['statewide_votes'] for c in candidates if c['comparison']==key and c['party_source']=='R')
  state_all=sum(number(master[3][col]) for col in cols)
  for row,r in counties:
   c=census[r['A']];d=sum(number(r[col]) for col in cols if party(header[col])=='D');rr=sum(number(r[col]) for col in cols if party(header[col])=='R');allvotes=sum(number(r[col]) for col in cols);o=allvotes-d-rr;two=d+rr;m=(d-rr)/two;ballots=number(r['E'])
   baselines.append({'comparison':key,'election_date':date,'county':r['A'],'county_fips':c['STATEFP']+c['COUNTYFP'],'census_countyns_2020':c['COUNTYNS'],'native_county_name':r['A'],'native_numeric_county_id':'not_published','source_county_row':row,'d_votes':d,'r_votes':rr,'other_votes':o,'all_candidate_votes':allvotes,'two_party_votes':two,'ballots_counted_or_total_voters':ballots,'ballot_field_native':header['E'],'registered_voters':number(r['D']),'ballots_minus_contest_votes_unclassified':ballots-allvotes,'d_share_two_party':d/two,'d_minus_r_margin_two_party':m,'d_share_all_candidates':d/allvotes,'d_minus_r_margin_all_candidates':(d-rr)/allvotes,'other_share_all_candidates':o/allvotes,'historical_winner':'D' if d>rr else 'R' if rr>d else 'tie','absolute_margin_band':'mixed_le5pp' if abs(m)<=.05 else 'lean_gt5_to10pp' if abs(m)<=.10 else 'gt10pp','net_d_minus_r_votes':d-rr,'statewide_major_party_weight':two/(state_d+state_r),'statewide_contest_weight':allvotes/state_all,'statewide_margin_contribution':(d-rr)/(state_d+state_r),'net_gain_per_1pp_d_share':.02*two,'region_native':r['B'],'media_market_native':r['C'],'source_path':path,'source_status':status})
   assert 0<=allvotes<=ballots and 0<two<=allvotes
 write_csv(DATA/'county-baselines.csv',baselines);write_csv(ROOT/'candidate-votes.csv',votes);write_csv(ROOT/'candidate-universe.csv',candidates);write_csv(ROOT/'primary-state-checks.csv',checks)
 (ROOT/'source-schema.json').write_text(json.dumps(headers,indent=2)+'\n')
 return baselines,votes,candidates

def precinct_inventory(baselines,candidates):
 census=fips_table();inventory=[];checks=[]
 for year,path in PRECINCTS.items():
  book=Book(ROOT/path);sums=collections.Counter();units=collections.Counter();seen=set();labels={}
  for row,r in book.rows('Master'):
   if row==1:note=r['A'];continue
   if row==2:labels=r;continue
   if r.get('A') not in census:continue
   county=r['A'];c=census[county];code=r['C'];key=(year,county,code)
   assert key not in seen,('duplicate native unit',key)
   assert re.fullmatch('[A-Z]{3}',code),key
   seen.add(key);units[county]+=1
   inventory.append({'election_year':year,'county':county,'county_fips':c['STATEFP']+c['COUNTYFP'],'native_county_name':county,'native_precinct_code':code,'native_precinct_name':r['B'],'source_row':row,'registered_voters':number(r['F']),'ballots_counted':number(r['G']),'source_path':path,'vintage':f'{year} general official canvass','write_in_counts':'not_available_at_precinct_level','cross_year_join_status':'not_attempted_no_validated_crosswalk'})
   relevant={norm(x['source_candidate_label']) for x in candidates if x['comparison'] in [f'{year}_senate',f'{year}_president']}
   for col,label in labels.items():
    if norm(label) in relevant:
     sums[county,norm(label)]+=number(r[col])
  assert len(units)==88
  for c in candidates:
   if c['comparison'] not in [f'{year}_senate',f'{year}_president']:continue
   rows=[r for r in CANDIDATE_VOTES if r['comparison']==c['comparison'] and r['source_candidate_label']==c['source_candidate_label']]
   for r in rows:
    found=sums[r['county'],norm(c['source_candidate_label'])];expected=0 if c['write_in'] else r['votes']
    assert found==expected,(year,r['county'],c['source_candidate_label'],found,expected)
    checks.append({'comparison':c['comparison'],'county':r['county'],'candidate':c['source_candidate_label'],'precinct_sum':found,'county_summary':r['votes'],'summary_minus_precinct':r['votes']-found,'explanation':'explicitly omitted write-ins' if c['write_in'] else 'same-election exact reconciliation'})
  for base in baselines:
   if base['comparison']==f'{year}_senate':base['native_precinct_count']=units[base['county']]
 write_csv(ROOT/'native-reporting-units.csv.gz',inventory);write_csv(ROOT/'precinct-county-checks.csv',checks)
 return inventory,checks

def scenario(shares,turnout,margin=0,held=None):
 """All shares fractional; margin=0.01 is D+1 TWO-PARTY margin.

 held: mapping county→fixed D share; omitted counties retain baseline shares.
 A uniform shift moves R votes to D at fixed two-party T; no clipping.
 """
 total=math.fsum(turnout.values());assert total>0
 m0=math.fsum(turnout[c]*(2*shares[c]-1) for c in shares)
 shift=(margin*total-m0)/(2*total)
 target={c:shares[c]+shift for c in shares}
 return total,m0,shift,target

def selected_share(shares,turnout,selected,margin=0,held=None):
 held=held or {};total=math.fsum(turnout.values());t=turnout[selected]
 assert t>0
 rest=math.fsum(turnout[c]*(2*held.get(c,shares[c])-1) for c in shares if c!=selected)
 q=(margin*total-rest+t)/(2*t)
 status='already_secured' if q<0 else 'impossible' if q>1 else 'feasible'
 return q,status,rest

def scenarios(baselines):
 by={k:{r['county']:r for r in baselines if r['comparison']==k} for k in SPECS}
 high=sum(r['two_party_votes'] for r in by['2024_senate'].values());low=sum(r['two_party_votes'] for r in by['2022_senate'].values());base=sum(r['two_party_votes'] for r in by['2018_senate_amended'].values())
 definitions=[]
 for key in ['2024_senate','2024_president','2022_senate','2018_senate_amended']:
  definitions.append((key+'_own_observed',key,key,sum(r['two_party_votes'] for r in by[key].values()),'observed preference and volume; historical election'))
 for label,volume in [('low_2022',low),('base_2018_amended',base)]:
  definitions.append(('2024_senate_fixed_mix_'+label,'2024_senate','2024_senate',volume,'uniform statewide volume only; 2024 county weights and shares held fixed'))
 for mix in ['2022_senate','2018_senate_amended']:
  definitions.append(('2024_senate_mix_'+mix+'_fixed_high_volume','2024_senate',mix,high,'county composition only; statewide major-party volume fixed at 2024'))
 # Same experiment crossed fully: geographic composition versus uniform volume.
 for mix in ['2022_senate','2018_senate_amended']:
  for label,volume in [('low_2022',low),('base_2018_amended',base)]:
   definitions.append(('2024_senate_mix_'+mix+'_'+label,'2024_senate',mix,volume,'historical county weights crossed with observed statewide volume; scenario only'))
 states=[];countyrows=[];conditional=[]
 for ident,pref,mix,volume,assumption in definitions:
  shares={c:r['d_share_two_party'] for c,r in by[pref].items()};mix_total=sum(r['two_party_votes'] for r in by[mix].values());turnout={c:volume*r['two_party_votes']/mix_total for c,r in by[mix].items()}
  for m in [0,.01]:
   total,m0,shift,targets=scenario(shares,turnout,m)
   net=math.fsum(turnout[c]*(2*targets[c]-1) for c in targets)
   assert math.isclose(net,m*total,abs_tol=1e-7)
   feasible=all(0<=q<=1 for q in targets.values())
   states.append({'scenario':ident,'preference_comparison':pref,'turnout_mix_comparison':mix,'target_two_party_margin':m,'scenario_major_party_votes':total,'baseline_d_minus_r_net_votes':m0,'baseline_two_party_margin':m0/total,'uniform_d_share_shift':shift,'uniform_d_share_shift_pp':100*shift,'uniform_margin_shift_pp':200*shift,'required_net_change':m*total-m0,'target_net_votes':net,'all_county_targets_feasible':int(feasible),'already_winning_without_improvement':int(m0>m*total),'assumption':assumption})
   for c,r in by[pref].items():
    q=targets[c];t=turnout[c]
    countyrows.append({'scenario':ident,'target_two_party_margin':m,'county':c,'county_fips':r['county_fips'],'preference_comparison':pref,'turnout_mix_comparison':mix,'baseline_d_votes':r['d_votes'],'baseline_r_votes':r['r_votes'],'baseline_other_votes':r['other_votes'],'baseline_d_share_two_party':shares[c],'scenario_major_party_votes':t,'statewide_weight':t/total,'baseline_net_contribution':t*(2*shares[c]-1),'uniform_d_share_shift':shift,'target_d_share_two_party':q,'target_d_minus_r_margin':2*q-1,'target_net_votes':t*(2*q-1),'net_gain_per_1pp_d_share':.02*t,'feasibility':'feasible' if 0<=q<=1 else 'infeasible_unbounded_uniform_shift','other_share_assumption':'no conversion from ballots; major-party votes explicit; others outside denominator'})
    req,status,rest=selected_share(shares,turnout,c,m)
    conditional.append({'scenario':ident,'target_two_party_margin':m,'selected_county':c,'county_fips':r['county_fips'],'selected_major_party_votes':t,'statewide_major_party_votes':total,'all_other_counties_d_share':'each at preference_comparison observed two-party share','all_other_counties_net_votes':rest,'selected_required_d_share':req,'selected_share_shift_from_baseline':req-shares[c],'selected_required_margin':2*req-1,'status':status,'unbounded_target_net_votes':t*(2*req-1)})
 write_csv(ROOT/'state-scenarios.csv',states);write_csv(ROOT/'county-target-scenarios.csv',countyrows);write_csv(ROOT/'selected-county-targets.csv',conditional)
 (ROOT/'scenario-definitions.json').write_text(json.dumps({'not_a_2026_projection':True,'historical_major_party_volume_anchors':{'low_2022_senate':low,'base_2018_senate_amended':base,'high_2024_senate':high},'definitions':definitions},indent=2)+'\n')
 return states,countyrows,conditional

def priority(baselines):
 rows=sorted([r for r in baselines if r['comparison']=='2024_senate'],key=lambda r:(-r['all_candidate_votes'],r['county']));total=sum(r['all_candidate_votes'] for r in rows);acc=0;cut=None;rank=[]
 for i,r in enumerate(rows,1):
  acc+=r['all_candidate_votes']
  if cut is None and acc/total>=.8:cut=i
  rank.append({'rank':i,'county':r['county'],'county_fips':r['county_fips'],'all_candidate_votes':r['all_candidate_votes'],'cumulative_votes':acc,'cumulative_share':acc/total})
 for r in rank:r['priority_top15_union_min80']=int(r['rank']<=max(15,cut))
 write_csv(ROOT/'priority-reconciliation.csv',rank)
 p={'basis':'2024 Senate all seven certified candidates','county_count':88,'minimum_80_count':cut,'priority_count':max(15,cut),'statewide_votes':total,'first_31_votes':rank[30]['cumulative_votes'],'priority_votes':rank[max(15,cut)-1]['cumulative_votes'],'priority_share':rank[max(15,cut)-1]['cumulative_share'],'top15_votes':rank[14]['cumulative_votes'],'counties':[r['county'] for r in rank[:max(15,cut)]]}
 (ROOT/'priority-set.json').write_text(json.dumps(p,indent=2)+'\n');return p

def revisions(baselines):
 old={r['county']:r for r in baselines if r['comparison']=='2018_senate_original'};new={r['county']:r for r in baselines if r['comparison']=='2018_senate_amended'};out=[]
 for c in old:
  for f in ['d_votes','r_votes','other_votes','all_candidate_votes','ballots_counted_or_total_voters','registered_voters']:
   a,b=old[c][f],new[c][f]
   if a!=b:out.append({'county':c,'field':f,'original':a,'miami_amended':b,'change':b-a,'source_explanation':'Archive index says Miami Board certified amended results January 22 2019; original and amended publications both retained.'})
 assert {x['county'] for x in out}=={'Miami'}
 write_csv(ROOT/'2018-revisions.csv',out)

def third_candidate_denominators(baselines):
 out=[]
 for key in ['2024_senate','2022_senate','2024_president','2018_senate_amended']:
  rs=[r for r in baselines if r['comparison']==key];d=sum(r['d_votes'] for r in rs);r=sum(r['r_votes'] for r in rs);o=sum(r['other_votes'] for r in rs);t=d+r;a=t+o
  for name,net in [('tie',0),('d_plus1_two_party',.01*t),('d_plus1_all_candidate',.01*a)]:
   out.append({'comparison':key,'target':name,'fixed_d_plus_r':t,'fixed_other_votes':o,'fixed_all_candidate_votes':a,'required_d_minus_r_net_votes':net,'uniform_d_share_shift':(net-(d-r))/(2*t),'target_two_party_margin':net/t,'target_all_candidate_margin':net/a,'assumption':'Other candidate votes fixed; major-party transfer R to D; not a 2026 candidate prediction.'})
 write_csv(ROOT/'third-candidate-denominators.csv',out)

def cli():
 a=argparse.ArgumentParser();a.add_argument('--selected-county');a.add_argument('--comparison',default='2024_senate',choices=SPECS);a.add_argument('--turnout-mix',default='2024_senate',choices=SPECS);a.add_argument('--total-major-votes',type=float);a.add_argument('--target-margin',type=float,default=0);a.add_argument('--hold-shares-json',type=pathlib.Path,help='JSON county→fractional D share; unlisted counties retain baseline share. Read-only input.');args=a.parse_args()
 global CANDIDATE_VOTES
 if args.selected_county:
  rows=list(csv.DictReader((DATA/'county-baselines.csv').open()));pref={r['county']:float(r['d_share_two_party']) for r in rows if r['comparison']==args.comparison};mix={r['county']:int(r['two_party_votes']) for r in rows if r['comparison']==args.turnout_mix};v=args.total_major_votes if args.total_major_votes is not None else sum(mix.values());assert v>0;turnout={c:v*t/sum(mix.values()) for c,t in mix.items()};held=json.loads(args.hold_shares_json.read_text()) if args.hold_shares_json else {}
  assert args.selected_county in pref and set(held)<=set(pref) and all(0<=s<=1 for s in held.values())
  q,status,rest=selected_share(pref,turnout,args.selected_county,args.target_margin,held)
  print(json.dumps({'selected_county':args.selected_county,'required_d_share':q,'status':status,'other_counties_net':rest,'total_major_party_votes':v,'target_margin':args.target_margin,'held_overrides':held,'unlisted_counties':'at observed baseline shares'},indent=2));return
 baselines,CANDIDATE_VOTES,candidates=extract();inventory,pc=precinct_inventory(baselines,candidates)
 unit_counts=collections.Counter((r['election_year'],r['county']) for r in inventory)
 for r in baselines:
  r['native_precinct_count']=unit_counts[int(r['election_date'][:4]),r['county']] or ''
  r['native_precinct_vintage']=r['election_date'] if r['native_precinct_count'] else 'not_retrieved_2018'
 write_csv(DATA/'county-baselines.csv',baselines)
 states,targets,conditional=scenarios(baselines);p=priority(baselines);revisions(baselines);third_candidate_denominators(baselines)
 print(json.dumps({'baseline_rows':len(baselines),'candidate_county_rows':len(CANDIDATE_VOTES),'candidate_vintages':len(candidates),'native_unit_rows':len(inventory),'precinct_candidate_checks':len(pc),'state_scenarios':len(states),'county_target_rows':len(targets),'conditional_rows':len(conditional),'priority':p},indent=2))

if __name__=='__main__':cli()
