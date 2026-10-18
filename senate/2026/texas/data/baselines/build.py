#!/usr/bin/env python3
"""Offline independent primary extraction and deterministic conditional targets.
No residual allocation, rescaling, candidate imputation, or native-unit deduplication.
"""
import csv,gzip,hashlib,io,json,re,subprocess,collections,datetime,math
from pathlib import Path
P=Path(__file__).resolve().parent; DATA=P.parent; STATE=DATA.parent; PEER=DATA/'turnout'
ALIASES={'COLLINGSWOR':'COLLINGSWORTH','THROCKMORT':'THROCKMORTON'}
CONTESTS={
 '2024-senate':dict(date='2024-11-05',seat='Class I; other seat',start='U. S. SENATOR',end='U. S. REPRESENTATIVE',names=['TED CRUZ (I)','COLIN ALLRED','TED BROWN','TRACY ANDRUS','ANALISA ROCHE'],parties=['REP','DEM','LIB','WRI','WRI'],source='sos2024-county-archive-20250422200023',root=PEER,state_source='sos-2024-canvass-archive'),
 '2024-president':dict(date='2024-11-05',seat='',start='PRESIDENT/VICE-PRESIDENT',end='U. S. SENATOR',names=['DONALD J. TRUMP/JD VANCE','KAMALA D. HARRIS/TIM WALZ','CHASE OLIVER/MIKE TER MAAT','JILL STEIN/RUDOLPH WARE','SHIVA AYYADURAI/CRYSTAL ELLIS','JESSIE CUELLAR/WESLEY LASLEY','CLAUDIA DE LA CRUZ/KARINA GARCIA','CHERUNDA FOX/HARLAN MCVAY','PETER SONSKI/LAUREN ONAK','CORNEL WEST/MELINA ABDULLAH'],parties=['REP','DEM','LIB','GRE']+['WRI']*6,source='sos2024-county-archive-20250422200023',root=PEER,state_source='sos-2024-canvass-archive'),
 '2022-governor':dict(date='2022-11-08',seat='Midterm; no Senate election',start='GOVERNOR',end='LIEUTENANT GOVERNOR',names=['GREG ABBOTT (I)',"BETO O'ROURKE",'MARK TIPPETTS','DELILAH BARRIOS','JACQUELINE ABERNATHY','MARK V GOLOBY'],parties=['REP','DEM','LIB','GRE','WRI','WRI'],source='sos2022-county-20241003',root=P,state_source='sos2022-state-20230627'),
 '2020-senate':dict(date='2020-11-03',seat='Class II; same 2026 seat',start='U. S. SENATOR',end='U. S. REPRESENTATIVE',names=['JOHN CORNYN (I)','MARY "MJ" HEGAR','KERRY DOUGLAS MCKENNON','DAVID B. COLLINS','RICARDO TURULLOLS-BONILLA'],parties=['REP','DEM','LIB','GRE','WRI'],source='sos2020-county-20241003',root=P,state_source='sos2020-state-20241211')}
def sha(b):return hashlib.sha256(b).hexdigest()
def jwrite(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def gziptext(path):
 return io.TextIOWrapper(gzip.GzipFile(filename='',mode='wb',fileobj=open(path,'wb'),mtime=0),encoding='utf-8',newline='')
def write(path,rows,fields=None):
 rows=list(rows);fields=fields or list(rows[0])
 with (gziptext(path) if str(path).endswith('.gz') else open(path,'w',newline='',encoding='utf-8')) as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def readcsv(path):
 with open(path,newline='') as f:return list(csv.DictReader(f))
def raw(root,key):
 path=root/'raw'/(key+'.body.gz')
 if path.exists():return gzip.decompress(path.read_bytes())
 meta=json.loads((root/'raw'/(key+'.meta.json')).read_text());chunks=[]
 for part in meta['stored_parts']:
  b=(root/part['path']).read_bytes();assert len(b)==part['bytes']<40000000 and sha(b)==part['sha256'];chunks.append(b)
 b=b''.join(chunks);assert sha(b)==meta['stored_sha256'];original=gzip.decompress(b);assert sha(original)==meta['original_sha256'];return original
def pdftext(root,key):
 b=raw(root,key);assert b.startswith(b'%PDF'),key
 return subprocess.run(['pdftotext','-layout','-','-'],input=b,stdout=subprocess.PIPE,check=True).stdout.decode()
PAT=re.compile(r'\s*([A-Z][A-Z .\x27-]*?)\s{2,}([\d,]+(?:\s+[\d,]+)+)\s*')
def extract(text,cfg):
 # Section bounds are literal official contest names, never a numeric race ID guess.
 text=text.split(cfg['start'],1)[1].split(cfg['end'],1)[0];rows=[];tails=[]
 for line_no,line in enumerate(text.splitlines(),1):
  m=PAT.fullmatch(line)
  if m:rows.append(dict(native_county=m[1].strip(),values=[int(v.replace(',','')) for v in m[2].split()],section_line=line_no,literal=line))
  elif cfg['start']=='PRESIDENT/VICE-PRESIDENT' and re.fullmatch(r'\s*\d[\d,]*\s+\d[\d,]*\s+\d[\d,]*\s*',line):tails.append(dict(values=[int(v.replace(',','')) for v in line.split()],section_line=line_no,literal=line))
 if tails:
  assert len(rows)==len(tails)==255,(len(rows),len(tails))
  for r,t in zip(rows,tails):r['values']+=t['values'];r['tail_section_line']=t['section_line'];r['tail_literal']=t['literal']
 assert len(rows)==255 and rows[-1]['native_county']=='TOTAL VOTES'
 assert len({r['native_county'] for r in rows[:-1]})==254
 n=len(cfg['names']);assert all(len(r['values'])==n+1 for r in rows)
 for r in rows:assert sum(r['values'][:-1])==r['values'][-1],r
 assert [sum(r['values'][i] for r in rows[:-1]) for i in range(n+1)]==rows[-1]['values']
 return rows

def state_extract(text,cfg):
 section=text.split(cfg['start'],1)[1].split(cfg['end'],1)[0];out=[]
 for line in section.splitlines():
  m=re.fullmatch(r'\s*(.+?)\s{2,}(REP|DEM|LIB|GRE|WRI)\s+([\d,]+)\s+.*',line)
  if m:out.append((m[1].strip(),m[2],int(m[3].replace(',',''))))
 total=re.search(r'Total Votes\s+([\d,]+)',section);assert total and len(out)==len(cfg['names']),(cfg['start'],out)
 return out,int(total[1].replace(',',''))

def solve_uniform(ss,ts,g):
 T=sum(ts)
 if T<=0:return dict(status='no-positive-pool',unbounded=None,bounded=None)
 M=sum(t*(2*s-1) for s,t in zip(ss,ts));u=(g*T-M)/(2*T)
 def margin(d):return sum(t*(2*min(1,max(0,s+d))-1) for s,t in zip(ss,ts))
 lo,hi=-1.,1.
 for _ in range(100):
  mid=(lo+hi)/2
  if margin(mid)<g*T:lo=mid
  else:hi=mid
 b=(lo+hi)/2
 return dict(status='already-winning' if M>g*T else 'at-target' if M==g*T else 'improvement-required',unbounded=u,bounded=b,clipped=sum(not(0<=s+u<=1) for s in ss),M=M,T=T)

def conditional(t,T,other,g):
 if t<=0:return None,'no-positive-pool'
 q=(t+g*T-other)/(2*t)
 return q,'impossible' if q>1 else 'already-secured' if q<0 else 'feasible'

def main():
 med=list(csv.DictReader(io.StringIO(raw(PEER,'medsl-senate-county').decode('utf-8-sig'))));med=[r for r in med if r['state_po']=='TX']
 fips={r['county_name']:r['county_fips'] for r in med};assert len(fips)==254;canonical={v:k for k,v in fips.items()}
 extracts={};by={};candidates=[];controls=[];vintages=[]
 for contest,cfg in CONTESTS.items():
  text=pdftext(cfg['root'],cfg['source']);rows=extract(text,cfg);extracts[contest]=rows
  footer=sorted(set(re.findall(r'\d\d/\d\d/\d{4} \d{1,2}[.:]\d\d [AP]M',text)))
  st,total=state_extract(pdftext(cfg['root'],cfg['state_source']),cfg);assert [v for n,p,v in st]+[total]==rows[-1]['values']
  by[contest]={}
  for i,r in enumerate(rows[:-1],1):
   native=r['native_county'];full=ALIASES.get(native,native);key=fips[full];by[contest][key]=r
   for j,(name,party) in enumerate(zip(cfg['names'],cfg['parties'])):
    candidates.append(dict(contest=contest,election_date=cfg['date'],seat_relation=cfg['seat'],county_fips=key,county_name=full,native_county_name=native,native_county_code='',native_candidate_name=name,native_party=party,write_in=int(party=='WRI'),votes=r['values'][j],county_contest_total=r['values'][-1],native_county_order=i,candidate_order=j+1,source_id=cfg['source'],source_footer_literal='; '.join(footer),geo_status='county FIPS mapped to pinned MEDSL; explicit two truncation aliases',source_section_line=r.get('tail_section_line') if contest=='2024-president' and j>=8 else r['section_line']))
  for j,((native,party,v),name) in enumerate(zip(st,cfg['names'])):
   controls.append(dict(contest=contest,native_candidate_name=name,state_publication_candidate_literal=native,native_party=party,votes=v,county_sum=sum(r['values'][j] for r in rows[:-1]),difference=sum(r['values'][j] for r in rows[:-1])-v,state_contest_total=total,state_source_id=cfg['state_source'],county_source_id=cfg['source']))
  # Primary native county codes absent; FIPS mapping is derived, never presented as native.
  for source,root in ([(f'sos2024-county-archive-{v}',PEER) for v in ['20241215150002','20241215142552']] if contest.startswith('2024') else [('sos2020-county-20201216',P)] if contest=='2020-senate' else []):
   old=extract(pdftext(root,source),cfg)
   diffs=[dict(native_county=a['native_county'],old=a['values'],selected=b['values']) for a,b in zip(old,rows) if a['values']!=b['values'] or a['native_county']!=b['native_county']]
   vintages.append(dict(contest=contest,compared_source=source,selected_source=cfg['source'],row_count=len(old)-1,differences=diffs))
 jwrite(P/'primary-extraction.json',extracts);write(P/'county-candidates.csv',candidates);write(P/'state-candidate-controls.csv',controls);jwrite(P/'vintage-comparison.json',vintages)
 base=[];ranked=sorted(by['2024-senate'],key=lambda k:(-by['2024-senate'][k]['values'][-1],k));total=sum(by['2024-senate'][k]['values'][-1] for k in ranked);cum=0;priority=[]
 for rank,k in enumerate(ranked,1):
  prev=cum;cum+=by['2024-senate'][k]['values'][-1];in80=int(5*prev<4*total)
  if in80:priority.append('TX:'+k)
  for contest,cfg in CONTESTS.items():
   r=by[contest][k];v=r['values'];D=v[1];R=v[0];pair=D+R;T=v[-1];other=T-pair;statePair=sum(z['values'][0]+z['values'][1] for z in by[contest].values());stateAll=sum(z['values'][-1] for z in by[contest].values());s=D/pair if pair else None
   base.append(dict(contest=contest,election_date=cfg['date'],seat_relation=cfg['seat'],county_fips=k,county_name=canonical[k],native_county_name=r['native_county'],native_county_code='',dispatch_key='TX:'+k,d=D,r=R,other=other,candidate_votes=T,pair_votes=pair,pair_participation=pair/T if T else '',d_pair_share=s if s is not None else '',d_minus_r_pair_margin=(D-R)/pair if pair else '',d_minus_r_all_candidate_margin=(D-R)/T if T else '',pair_weight=pair/statePair if statePair else '',candidate_vote_weight=T/stateAll if stateAll else '',historical_winner='D' if D>R else 'R' if R>D else 'tie',closeness_band='undefined' if not pair else '<=5pp' if abs(D-R)*100<=5*pair else '>5-10pp' if abs(D-R)*100<=10*pair else '>10pp',senate2024_volume_rank=rank,senate2024_cumulative_votes=cum,senate2024_top15=int(rank<=15),senate2024_priority80=in80,ballots_cast='',registered_voters='',undervotes='',overvotes='',method_split_status='not published in county canvass',source_id=cfg['source'],status='primary archived official county canvass; independently reconciled to primary statewide',geography_vintage=cfg['date']+' county labels; mapped FIPS; no 2026 precinct approval'))
 write(DATA/'county-baselines.csv',base)
 jwrite(P/'priority-set.json',dict(denominator=total,rank_basis='all five valid 2024 Senate candidate votes',top15_votes=sum(by['2024-senate'][k]['values'][-1] for k in ranked[:15]),minimum80_count=len(priority),minimum80_votes=sum(by['2024-senate'][k.split(':')[1]]['values'][-1] for k in priority),preceding_set_votes=sum(by['2024-senate'][k.split(':')[1]]['values'][-1] for k in priority[:-1]),priority_keys=priority,full_order=['TX:'+k for k in ranked]))
 # Historical low/base/high volumes; 2024 Senate county preferences held fixed.
 # All-candidate county volumes converted to pair votes using county2024 pair participation.
 ss=[by['2024-senate'][k]['values'][1]/sum(by['2024-senate'][k]['values'][:2]) for k in ranked]
 mixes=[('low-2022-governor-volume','2022-governor'),('base-2024-senate-volume','2024-senate'),('high-2024-president-volume','2024-president'),('2020-senate-volume','2020-senate')]
 states=[];scenarios=[]
 mixes=[(m,v,'2024-senate') for m,v in mixes]+[(c+'-own-preference-and-volume',c,c) for c in ['2020-senate','2022-governor','2024-president']]
 for mix,vol,preference in mixes:
  ss=[by[preference][k]['values'][1]/sum(by[preference][k]['values'][:2]) for k in ranked]
  volume=[by[vol][k]['values'][-1] for k in ranked];participation=[sum(by[preference][k]['values'][:2])/by[preference][k]['values'][-1] for k in ranked];ts=[v*p for v,p in zip(volume,participation)]
  for target,g in [('tie',0.),('A+1-pair-margin',.01),('A+1-all-candidate-margin',.01*sum(volume)/sum(ts))]:
   sol=solve_uniform(ss,ts,g);T=sol['T'];baseM=sol['M'];delta=sol['bounded'];nets=[];unets=[]
   for i,k in enumerate(ranked):
    s=ss[i];t=ts[i];q=min(1,max(0,s+delta));u=s+sol['unbounded'];baselineNet=t*(2*s-1);otherNet=baseM-baselineNet;conditionalQ,status=conditional(t,T,otherNet,g);net=t*(2*q-1);nets.append(net);unets.append(t*(2*u-1))
    scenarios.append(dict(scenario=mix,target=target,preference_baseline=preference+' '+CONTESTS[preference]['names'][1]+' versus '+CONTESTS[preference]['names'][0],volume_basis=vol+' all valid candidate votes',pair_participation_basis='county '+preference+' named DEM+REP / all valid candidates',county_fips=k,county_name=canonical[k],d=by[preference][k]['values'][1],r=by[preference][k]['values'][0],baseline_pair_share=s,expected_all_candidate_votes=volume[i],pair_participation=participation[i],expected_pair_votes=t,pair_weight=t/T,baseline_net=baselineNet,one_pp_share_net_gain=.02*t,target_margin_on_pair=g,target_margin_on_all_candidates=g*T/sum(volume),unbounded_shift_share_pp=100*sol['unbounded'],unbounded_target_share=u,bounded_shift_share_pp=100*delta,bounded_target_share=q,bounded_target_net=net,net_gain=net-baselineNet,clipped=int(q!=s+delta),selected_only_required_share=conditionalQ,selected_only_status=status,others_fixed=preference+' pair shares and this scenario volumes'))
   states.append(dict(scenario=mix,target=target,preference_baseline=preference,volume_basis=vol,all_candidate_votes=sum(volume),pair_votes=T,pair_participation=T/sum(volume),baseline_net=baseM,baseline_pair_margin=baseM/T,baseline_all_candidate_margin=baseM/sum(volume),target_pair_margin=g,target_all_candidate_margin=g*T/sum(volume),target_net=g*T,unbounded_shift_share_pp=100*sol['unbounded'],bounded_shift_share_pp=100*delta,unbounded_clipped_count=sol['clipped'],bounded_achieved_net=sum(nets),unbounded_achieved_net=sum(unets),status=sol['status']))
 write(P/'county-target-scenarios.csv',scenarios);write(P/'state-target-scenarios.csv',states)
 print('Built',len(base),'county contest rows;',len(candidates),'candidate cells;',len(scenarios),'scenario county rows;',len(priority),'priority counties')
if __name__=='__main__':main()
