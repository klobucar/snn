#!/usr/bin/env python3
"""Offline primary-result audit and source inventory. Writes only this worker's paths.
Run from any directory. Python 3 stdlib + Poppler pdftotext required.
The dependency lock is created once; subsequent runs reject changed dependencies.
"""
import collections,csv,datetime,gzip,hashlib,io,json,pathlib,re,subprocess,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent
STATE=ROOT.parent.parent
DATA=STATE/'data'
METHODS=['Election Day','Absentee','Early Voting','Question','Remote']
PRIORITY=['6','9','3','8','23','29','25','30','24','34','11','35','16','7','36','2','26','15','28','4','21','27','33','10','1','12','5','17']
NAMES24=['Harris/Walz','Kennedy/Shanahan','Oliver/Maat','Sonski/Onak','Stein/Ware','Terry/Broden','Trump/Vance','West/Abdullah']
NAMES22=['Chesbro, Patricia R.','Kelley, Buzz A.','Murkowski, Lisa','Tshibaka, Kelly C.','Write-in']
COLS24=['harris_walz','kennedy_shanahan','oliver_maat','sonski_onak','stein_ware','terry_broden','trump_vance','west_abdullah']
COLS22=['chesbro','kelley','murkowski','tshibaka','write_in']
EXPECT24=[140026,5670,3040,702,2342,812,184458,1127]
EXPECT22=[27145,7557,113495,111480,2028]
def sha(b):return hashlib.sha256(b).hexdigest()
def load(f):return json.loads(f.read_text())
def body(key):return gzip.decompress((ROOT/(key+'.body.gz')).read_bytes())
def integer(s):return int(s.replace(',',''))
def rows(f):return list(csv.DictReader(io.StringIO(f.read_text())))
def writecsv(name,rs):
 assert rs
 with (ROOT/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def rawfile(name):
 f=DATA/'turnout'/name
 return f.read_bytes() if f.exists() else gzip.decompress(f.with_name(f.name+'.gz').read_bytes())
def pdftext(f):return subprocess.run(['pdftotext','-layout',str(f),'-'],capture_output=True,check=True).stdout.decode()
def hd(label):
 if label.startswith('HD99'):return '99'
 m=re.match(r'(?:District (\d+)|0*(\d+)-)',label)
 assert m,label
 return str(int(m[1] or m[2]))
def unitkind(label):return 'federal_overseas_administrative' if label.startswith('HD99') else 'district_administrative' if label.startswith('District') else 'physical_precinct'
def region(h):
 h=int(h)
 return (1,'Juneau','electionsr1@alaska.gov','907-465-3021') if h<=6 else (5,'Wasilla / Kenai satellite','electionsr5@alaska.gov','907-373-8952') if h in [7,8] or 25<=h<=30 else (2,'Anchorage','electionsr2@alaska.gov','907-522-8683') if 9<=h<=24 else (3,'Fairbanks','electionsr3@alaska.gov','907-451-2835') if 31<=h<=36 else (4,'Nome','electionsr4@alaska.gov','907-443-5285') if h<=40 else ('','Division / Absentee Office','akabsentee@alaska.gov','907-270-2700')
def parsecsv(raw,contest):
 rr=[r for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))) if r['Contest_Id']==contest]
 by=collections.defaultdict(list)
 for r in rr:by[r['Pct_seq_nbr']].append(r)
 names=list(dict.fromkeys(r['candidate_name'] for r in rr))
 gaps=[]
 for seq,rs in by.items():
  assert len(rs)==len(names)
  assert len({r['candidate_id'] for r in rs})==len(names)
  assert [r['candidate_name'] for r in rs]==names
  repeated=['Precinct_name','Pct_Id','total_ballots','Reg_voters','total_under_votes','total_over_votes']+[m+'_'+s for m in METHODS for s in ['ballots','under_votes','over_votes']]
  assert all(len({r[f] for r in rs})==1 for f in repeated)
  assert all(int(r['total_votes'])>=0 for r in rs)
  votes=sum(int(r['total_votes']) for r in rs); under=int(rs[0]['total_under_votes']);over=int(rs[0]['total_over_votes']);ballots=int(rs[0]['total_ballots'])
  if votes+under+over!=ballots:
   assert contest=='6',('Historical balance failed',seq)
   gaps.append(dict(seq=seq,label=rs[0]['Precinct_name'],ballots=ballots,votes=votes,under=under,over=over,unexplained_ballots=ballots-votes-under-over))
  for r in rs:
   for suffix in ['votes','ballots','under_votes','over_votes']:
    assert sum(int(r[m+'_'+suffix]) for m in METHODS)==int(r['total_'+suffix])
 if contest=='6':
  # Observed primary export limitation; retain exact gaps instead of inventing undervotes.
  assert len(gaps)==47 and sum(g['unexplained_ballots'] for g in gaps)==88
  (ROOT/'primary2026-ballot-balance-gaps.json').write_text(json.dumps(gaps,indent=2)+'\n')
 return by,names

def main():
 # Lock every reused source and derivative that contributes to this audit; never edit it.
 deps=[DATA/'coordinator-baseline-reconciliation.json',DATA/'county-baselines.csv',DATA/'county-turnout.csv']
 deps += [DATA/'turnout'/n for n in ['priority-set.json','reporting-units-2024.csv','reporting-units-2022.csv','precinct2024.csv.gz','precinct2022.txt.gz','summary2024.pdf','summary2022.pdf','senate-rcv2022-parsed.json','candidate-reconciliation.csv','district-reconciliation.csv']]
 deps += [DATA/'baselines'/n for n in ['cvr-ballot-coverage-gaps.csv','cvr-coverage-gaps.csv','rcv-statewide-round-checks.csv','certificate2022.extracted.txt']]
 for year in [2024,2022]:
  for h in [*range(1,41),99]:
   deps += [DATA/'turnout'/f'hd{h}-{year}.pdf', DATA/'turnout'/f'hd{h}-{year}.pdf.retrieval.json',DATA/'turnout'/f'hd{h}-{year}.pdf.headers']
 lock={str(f.relative_to(STATE)):sha(f.read_bytes()) for f in deps}
 lockpath=ROOT/'dependency-hashes.json'
 if lockpath.exists():assert lock==load(lockpath),'A read-only dependency changed: inspect and explicitly refresh the lock after review.'
 else:lockpath.write_text(json.dumps(lock,indent=2)+'\n')
 metas=[]
 for f in sorted(ROOT.glob('*.meta.json')):
  m=load(f);assert sha((ROOT/m['asset']).read_bytes())==m['stored_sha256'];assert sha(body(m['id']))==m['raw_sha256'];assert len(body(m['id']))==m['bytes'];assert sha((ROOT/m['headers']).read_bytes())==m['headers_sha256'];assert m['bytes']<=20*1024*1024
  assert m['curl_metadata'].get('ssl_verify_result') in (0,None),m['id']
  metas.append(m)
 (ROOT/'evidence-manifest.json').write_text(json.dumps(metas,indent=2)+'\n')
 # Every 2024 and 2022 source unit is reconciled to its retained native key, without a cross-year join.
 u24=rows(DATA/'turnout/reporting-units-2024.csv');u22=rows(DATA/'turnout/reporting-units-2022.csv')
 b24,n24=parsecsv(rawfile('precinct2024.csv'),'4');assert n24==NAMES24 and len(b24)==523
 allchecks=[];coverage=[]
 for us,names,cols,expected,year in [(u24,NAMES24,COLS24,EXPECT24,2024),(u22,NAMES22,COLS22,EXPECT22,2022)]:
  assert len(us)==len({u['source_unit_key'] for u in us})=={2024:523,2022:522}[year]
  assert {u['native_house_district'] for u in us}==set(map(str,[*range(1,41),99]))
  assert all(u['county_fips']=='' and u['state_fips']=='02' for u in us)
  if year==2024:
   for u in us:
    rs=b24[u['native_pct_seq_nbr']];assert u['source_label']==rs[0]['Precinct_name'] and u['native_pct_id']==rs[0]['Pct_Id']
    assert [int(u[c]) for c in cols]==[int(r['total_votes']) for r in rs]
   assert sum(not u['native_pct_id'] for u in us)==80
  else:
   t=list(csv.reader(io.StringIO(rawfile('precinct2022.txt').decode('utf-16')),delimiter='\t'))
   for u in us:
    r=t[int(u['source_record_start'])-1];assert r[0]==u['source_label'];assert [int(u[c]) for c in cols]==[integer(v) for v in r[1:]]
  summary=pdftext(DATA/'turnout'/f'summary{year}.pdf');a=summary.index('U.S. President / Vice President' if year==2024 else 'U.S. Senator');s=summary[a:summary.index('U.S. Representative')]
  for name,col,exp in zip(names,cols,expected):
   match=re.search('^'+re.escape(name)+r'\s+(?:[A-Z]+\s+)?([\d,]+)\s+\d+\.\d+%\s*$',s,re.M);assert match
   total=sum(int(u[col]) for u in us);assert total==integer(match[1])==exp
   allchecks.append(dict(election=str(year),candidate=name,all_units=total,official_summary=integer(match[1]),difference=0))
  for h in map(str,[*range(1,41),99]):
   f=DATA/'turnout'/f'hd{h}-{year}.pdf';text=pdftext(f);assert 'OFFICIAL RESULTS' in text
   provenance=load(f.with_name(f.name+'.retrieval.json'))
   assert sha(f.read_bytes())==provenance['sha256'] and sha(f.with_name(f.name+'.headers').read_bytes())==provenance['headers_sha256']
   a=text.index('U.S. President / Vice President' if year==2024 else 'U.S. Senator');s=text[a:text.index('U.S. Representative')]
   lines=[x for x in s.splitlines() if 'State of Alaska - Total' in x];assert len(lines)==2
   nums=[[integer(z) for z in x.replace('State of Alaska - Total','').split() if re.fullmatch(r'[\d,]+',z)] for x in lines]
   vs=nums[0][2:]+nums[1][:-1];group=[u for u in us if u['native_house_district']==h]
   assert vs==[sum(int(u[col]) for u in group) for col in cols]
   assert sum(vs)==nums[1][-1] and sum(int(u['ballots_cast']) for u in group)==nums[0][0]
   assert sum(int(u['registered_voters']) for u in group)==nums[0][1]
  for u in us:coverage.append(dict(election_id=u['election_id'],source_unit_key=u['source_unit_key'],source_label=u['source_label'],native_house_district=u['native_house_district'],native_pct_id=u['native_pct_id'],native_pct_seq_nbr=u['native_pct_seq_nbr'],unit_type=u['unit_type'],county_fips='',boundary_vintage=u['boundary_vintage'],contest_id=u['contest_id'],count_stage=u['count_stage'],all_candidate_votes=u['all_candidate_votes'],ballots_cast=u['ballots_cast'],priority_research_district=int(u['native_house_district'] in PRIORITY),authority='Alaska Division of Elections',source_ref='data/turnout/reporting-units-'+str(year)+'.csv'))
 pset=load(DATA/'turnout/priority-set.json');assert [r['native_house_district'] for r in pset['districts']]==PRIORITY
 for key,part in [('general2024','/results/24GENR/HD'),('general2022','/results/22GENR/HD'),('primary2026','/enr26/results/HD')]:
  outbound={urllib.parse.urlparse(x['url']).path for x in load(ROOT/(key+'.links.json'))}
  assert {part+str(h)+'.pdf' for h in [*range(1,41),99]} <= outbound
 assert sum(int(u['all_candidate_votes']) for u in u24)==338177
 pkeys={u['source_unit_key'] for u in u24 if u['native_house_district'] in PRIORITY}
 assert pkeys==set(k for d in pset['districts'] for k in d['constituent_unit_keys'])
 assert sum(int(u['all_candidate_votes']) for u in u24 if u['source_unit_key'] in pkeys)==271492
 assert 5*263774<4*338177<=5*271492
 # Genuine current linked setup is the August primary, not a November zero/test report.
 pb,pnames=parsecsv(body('enr-precinct'),'6');assert len(pb)==523 and len(pnames)==16
 app=json.loads(body('enr-units').decode('utf-8-sig'));small=json.loads(body('enr-statewide').decode('utf-8-sig'))
 assert app['name']==small['name']=='Alaska 2026 Primary Election' and app['certified'] is True
 assert small['totals']==app['totals'] and small['districts']==app['districts'] and small['precincts']==[]
 assert len(app['districts'])==40 and len(app['precincts'])==402
 assert len({r['number'] for r in app['precincts']})==402
 pc=app['contestNames'].index('U.S. Senator'); assert pc==0
 def appvotes(c):return {app['candidateNames'][r['n']]:r['t'] for r in c['c']}
 def cfor(cs):return next(c for c in cs if c['n']==pc)
 total=cfor(app['totals']);assert total['t']==166004 and total['b']==166992 and (total['r'],total['p'])==(401,403)
 rawtot={n:sum(int(r['total_votes']) for rs in pb.values() for r in rs if r['candidate_name']==n) for n in pnames}
 # Full ballot names, not surname prefix matching: keep the two Sullivans separate.
 code={n:next(r for rs in pb.values() for r in rs if r['candidate_name']==n)['Party_Code'] for n in pnames}
 display={n:n+(' ('+code[n]+')' if code[n] else '') for n in pnames}
 assert {display[n]:v for n,v in rawtot.items()}==appvotes(total)
 for d in app['districts']:
  rs=[r for rows0 in pb.values() for r in rows0 if hd(r['Precinct_name'])==d['number']]
  assert {display[n]:sum(int(r['total_votes']) for r in rs if r['candidate_name']==n) for n in pnames}==appvotes(cfor(d['contests']))
 for d in app['precincts']:
  rs=next(rs for rs in pb.values() if rs[0]['Pct_Id']==d['number']);assert unitkind(rs[0]['Precinct_name'])=='physical_precinct'
  assert {display[r['candidate_name']]:int(r['total_votes']) for r in rs}==appvotes(cfor(d['contests']))
 summary=(ROOT/'enr-summary.extracted.txt').read_text().split('\f')[0]
 for n in pnames:
  pattern=re.escape(n).replace(r'\ ',r'\s+')
  if n=='Darden, Dustin Thomas House':pattern=r'Darden, Dustin Thomas'
  m=re.search(pattern+r'\s+(?:[A-Z]+\s+)?([\d,]+)\s+\d+\.\d+%',summary);assert m,n;assert integer(m[1])==rawtot[n]
  allchecks.append(dict(election='2026_primary',candidate=n,all_units=rawtot[n],official_summary=integer(m[1]),difference=0))
 for seq,rs in pb.items():
  r=rs[0];coverage.append(dict(election_id='26PRIM',source_unit_key='26PRIM:6:seq:'+seq,source_label=r['Precinct_name'],native_house_district=hd(r['Precinct_name']),native_pct_id=r['Pct_Id'],native_pct_seq_nbr=seq,unit_type=unitkind(r['Precinct_name']),county_fips='',boundary_vintage='2026 August primary snapshot; no November crosswalk',contest_id='6',count_stage='primary pick-one; OFFICIAL RESULTS',all_candidate_votes=sum(int(v['total_votes']) for v in rs),ballots_cast=int(r['total_ballots']),priority_research_district=int(hd(r['Precinct_name']) in PRIORITY),authority='Alaska Division of Elections',source_ref='data/results-sources/enr-precinct.body.gz'))
 # The official map omits HD99 in district view, and method administrative units in precinct view.
 assert sum(cfor(x['contests'])['t'] for x in app['districts'])+sum(int(r['total_votes']) for rs in pb.values() for r in rs if hd(r['Precinct_name'])=='99')==total['t']
 m24=json.loads(body('map2024-units').decode('utf-8-sig'));assert m24['certified'] and len(m24['districts'])==40 and len(m24['precincts'])==402
 p24=m24['contestNames'].index('U.S. President / Vice President');tc24=next(x for x in m24['totals'] if x['n']==p24)
 assert tc24['t']==338177 and tc24['b']==340981 and tc24['r']==tc24['p']==403
 assert sum(next(x for x in d['contests'] if x['n']==p24)['t'] for d in m24['districts'])+401==338177
 for d in m24['precincts']:
  c=next(x for x in d['contests'] if x['n']==p24);rs=next(rs for rs in b24.values() if rs[0]['Pct_Id']==d['number'])
  assert {m24['candidateNames'][v['n']].rsplit(' (',1)[0]:v['t'] for v in c['c']}=={r['candidate_name']:int(r['total_votes']) for r in rs}
 # Every HD row has all constituent units covered, while authority is statewide and region assignment is current only.
 inventory=[];ptable=[]
 for h in map(str,[*range(1,41),99]):
  g=[u for u in u24 if u['native_house_district']==h];g22=[u for u in u22 if u['native_house_district']==h];gp=[r for rs in pb.values() for r in rs[:1] if hd(r['Precinct_name'])==h]
  ri,office,email,phone=region(h);rank=PRIORITY.index(h)+1 if h in PRIORITY else ''
  r=dict(reporting_geography='HD'+h,geography_type='federal_overseas_administrative' if h=='99' else 'native_house_district_reporting_group',native_house_district=h,state_fips='02',county_fips='',priority_rank=rank,baseline_election_id='24GENR',baseline_contest_id='4',baseline_votes_2024=sum(int(x['all_candidate_votes']) for x in g),units_2024=len(g),physical_units_2024=sum(x['unit_type']=='physical_precinct' for x in g),administrative_units_2024=sum(x['unit_type']!='physical_precinct' for x in g),units_2022=len(g22),units_2026_primary=len(gp),authority='Alaska Division of Elections / Director',authority_url='https://www.elections.alaska.gov/ballot-counting-process/counting-system-and-schedule/',current_region=ri,regional_office=office,regional_email=email,regional_phone=phone,regional_authority_url='https://www.elections.alaska.gov/contact-information/',landing_url='https://www.elections.alaska.gov/election-results/',linked_current_app='https://www.elections.alaska.gov/enr26/',observed_app_election_id='26PRIM',november_2026_results_url='',november_status='No linked November results dataset established; current app is certified August primary',historical_2024_url=f'https://www.elections.alaska.gov/results/24GENR/HD{h}.pdf',historical_2022_url=f'https://elections.alaska.gov/results/22GENR/HD{h}.pdf',historical_evidence_2024=f'turnout/hd{h}-2024.pdf',historical_evidence_2022=f'turnout/hd{h}-2022.pdf',unit_coverage_file='results-sources/unit-coverage.csv',status_evidence='results-sources/enr-statewide.meta.json',source_timezone='App updated text and PDF print times have no timezone',cadence='Manual Refresh Results in inspected JS; no timed refresh or publisher SLA established',completion='r/p is reporting precincts; CSV Reporting_flag=0 even for positive certified returns; no vote-completion interpretation',remaining_candidate_votes='',overlap='Replace state/HD/precinct/method alternative views; do not add',manual_fallback='Division official linked election PDF/CSV; regional office for explanation; retain URL/status/UTC and full unit keys')
  inventory.append(r)
  if rank:ptable.append(dict(rank=rank,hd=h,votes=r['baseline_votes_2024'],physical=r['physical_units_2024'],administrative=r['administrative_units_2024'],all_units=r['units_2024'],region=ri))
 writecsv('unit-coverage.csv',coverage);writecsv('candidate-checks.csv',allchecks)
 assert len({u['source_unit_key'] for u in coverage})==1568
 with (DATA/'official-results-sources.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(inventory)
 ptable.sort(key=lambda x:x['rank']);writecsv('priority-inspection.csv',ptable)
 table='| Rank | Native HD | 2024 votes | Physical / administrative units | Total units | Current regional office |\n|---:|---:|---:|---:|---:|---|\n'
 for r in ptable:table+=f"| {r['rank']} | {r['hd']} | {r['votes']:,} | {r['physical']} / {r['administrative']} | {r['all_units']} | {r['region']} |\n"
 (ROOT/'priority-table.md').write_text(table)
 zones=json.loads(body('bts-zone-attributes'));assert len(zones['features'])==9 and not zones.get('exceededTransferLimit',False)
 assert {f['attributes']['zone']:f['attributes']['utc'] for f in zones['features']}['Alaska']=='-09:00'
 for key,expected in [('bts-adak',{'zone':'Hawaii-Aleutian','utc':'-10:00'}),('bts-anchorage',{'zone':'Alaska','utc':'-09:00'})]:
  z=json.loads(body(key));assert len(z['features'])==1 and z['features'][0]['attributes']==expected
 gaps=rows(DATA/'baselines/cvr-ballot-coverage-gaps.csv')
 assert len(gaps)==6 and sum(int(r['missing_ballots']) for r in gaps)==250 and sum(int(r['missing_candidate_votes']) for r in gaps)==237
 rcv=load(DATA/'turnout/senate-rcv2022-parsed.json')
 assert rcv['population']==266797 and rcv['rounds'][-1]['candidates']=={'Chesbro, Patricia R.':0,'Kelley, Buzz A.':0,'Murkowski, Lisa':136330,'Tshibaka, Kelly C.':117534}
 for rnd in rcv['rounds']:assert sum(rnd['candidates'].values())+rnd['Blanks']+rnd['Exhausted']+rnd['Overvotes']==266797
 from zoneinfo import ZoneInfo
 tz={n:datetime.datetime(2026,11,3,20,tzinfo=ZoneInfo(n)).astimezone(datetime.timezone.utc).isoformat() for n in ['America/Anchorage','America/Adak']}
 assert tz=={'America/Anchorage':'2026-11-04T05:00:00+00:00','America/Adak':'2026-11-04T06:00:00+00:00'}
 script=body('map-js').decode('utf-8-sig');assert 'setInterval' not in script and 'setTimeout' not in script and 'onRefreshButtonClick' in script
 # All owned files are below the Git-object bound. Markdown relative links must resolve.
 for f in ROOT.rglob('*'):
  if f.is_file():assert f.stat().st_size<40*1024*1024,f
 links=[]
 report=STATE/'official-results.md'
 if report.exists():
  for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
   if not re.match(r'\w+://',target) and not target.startswith('#'):
    assert (STATE/urllib.parse.unquote(target.split('#')[0])).exists(),target;links.append(target)
 result=dict(status='PASS',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),notifyOnFinish=True,inventory_groups=len(inventory),priority_districts=PRIORITY,priority_votes=271492,statewide_votes=338177,priority_share_percent=271492/338177*100,priority_underlying_2024_units=len(pkeys),baseline_unit_counts={'2024':523,'2022':522},coverage_rows=len(coverage),candidate_summary_checks=len(allchecks),historical_candidate_hd_cells=533,historical_hd_totals=82,current_setup_election='2026 PRIMARY ONLY',primary2026_units=len(pb),primary2026_candidates=len(pnames),primary2026_votes=166004,primary2026_ballots=166992,primary2026_map_hd99_vote_omission=61,primary2026_map_precinct_votes=sum(cfor(x['contests'])['t'] for x in app['precincts']),source_requests=len(metas),dependency_files=len(lock),relative_markdown_links_checked=len(links),cross_year_geography_join=False,november_current_crosswalk=False,november_results_dataset_validated=False,poll_close_utc=tz,remaining_candidate_votes=None)
 result['primary2026_invalid_vote_balance']={'status':'unresolved source gap retained','units':47,'unexplained_ballots':88,'candidate_votes':166004,'reported_undervotes':753,'reported_overvotes':147,'ballots':166992}
 result['historical_rcv_scope_gap']={'localized_ballots':250,'units':6,'fully_absent_units':5,'partial_unit':'37-730 Levelock','cause_and_missing_ranks':'not established'}
 result['archive_hd_links_checked']=123
 (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
