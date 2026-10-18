#!/usr/bin/env python3
"""Bounded public acquisition and lossless HTML view extraction; no polling job.

Run from repository root, PYTHONDONTWRITEBYTECODE=1 python3 .../research.py seeds
or follow. Every response is retained, including failures; replay is offline by default.
"""
import argparse, concurrent.futures, datetime, gzip, hashlib, html, json, re, sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse
import requests

ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent.parent
LEDGER=ROOT/'acquisition-ledger.json'
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def ledger(): return json.loads(LEDGER.read_text()) if LEDGER.exists() else []
def raw(r): return b''.join(gzip.decompress((ROOT/p).read_bytes()) for p in r['parts'])
class View(HTMLParser):
 def __init__(self,base):
  super().__init__(convert_charrefs=True);self.base=base;self.links=[];self.text=[];self.a=None;self.skip=0;self.resources=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='base' and a.get('href'): self.base=urljoin(self.base,a['href'])
  if tag in ('script','style'): self.skip+=1
  if tag=='a':
   self.a={'position':len(self.links)+1,'line':self.getpos()[0],'column':self.getpos()[1],'href_literal':a.get('href',''),'url':urljoin(self.base,a.get('href','')),'text':'','attributes':attrs};self.links.append(self.a)
  if tag in ('script','iframe','embed','object'):
   self.resources.append({'position':len(self.resources)+1,'line':self.getpos()[0],'tag':tag,'attributes':attrs,'url':urljoin(self.base,a.get('src',a.get('data','')))})
  if tag in ('p','div','br','h1','h2','h3','tr','li'): self.text.append('\n')
 def handle_endtag(self,tag):
  if tag=='a': self.a=None
  if tag in ('script','style') and self.skip: self.skip-=1
 def handle_data(self,s):
  if not self.skip: self.text.append(s)
  if self.a is not None:self.a['text']+=s
 def result(self):
  return {'links':self.links,'resources':self.resources,'text':re.sub(r'[ \t\r\f\v]+',' ',''.join(self.text))}
def view(b,url):
 p=View(url);p.feed(b.decode('utf-8',errors='replace'));return p.result()
def fetch(task):
 id,url,parent,label=task
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 rec={'id':id,'url':url,'parent_url':parent,'link_label':label,'retrieval_utc':now,'request_headers':{'User-Agent':'Iowa-election-source-research/1.0 (bounded public evidence research)'},'parts':[]}
 try:
  r=requests.get(url,headers=rec['request_headers'],timeout=(15,45),allow_redirects=True)
  b=r.content
  rec.update(status=r.status_code,final_url=r.url,headers=dict(r.headers),redirects=[{'url':h.url,'status':h.status_code,'headers':dict(h.headers)} for h in r.history],original_sha256=sha(b),original_bytes=len(b),response_encoding=r.encoding)
  # Exact ordered decoded entity chunks. Full entity is never truncated.
  for i in range(0,max(1,len(b)),30000000):
   p=Path('originals')/(id+(f'.part{i//30000000:03}' if len(b)>30000000 else '')+'.gz')
   z=gzip.compress(b[i:i+30000000],mtime=0);assert len(z)<40000000
   (ROOT/p).write_bytes(z);rec['parts'].append(str(p))
  rec['stored_objects']=[{'path':p,'bytes':(ROOT/p).stat().st_size,'sha256':sha((ROOT/p).read_bytes())} for p in rec['parts']]
  if 'html' in r.headers.get('Content-Type','').lower() or b.lstrip().startswith((b'<!DOCTYPE html',b'<html')):
   v=view(b,r.url);dump(ROOT/'extracts'/(id+'.json'),v)
   rec['view_path']='extracts/'+id+'.json'
 except Exception as e:rec.update(status=None,error=type(e).__name__+': '+str(e))
 return rec
def acquire(tasks):
 old=ledger();ids={r['id'] for r in old};tasks=[t for t in tasks if t[0] not in ids]
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
  for r in ex.map(fetch,tasks):
   old.append(r);dump(LEDGER,old);print(r['id'],r.get('status'),r.get('original_bytes'),flush=True)
 return old
def seeds():
 tasks=[('sos-auditors','https://sos.iowa.gov/auditors',None,'Official county auditor directory'),('sos-candidates','https://sos.iowa.gov/voters/candidates',None,'SOS candidates'),('sos-general','https://sos.iowa.gov/general-election',None,'General election page; tested route'),('sos-current-results','https://electionresults.iowa.gov/IA/','https://sos.iowa.gov/elections-voting','Election Results'),('sos-results-index','https://sos.iowa.gov/iowans/election-results-statistics',None,'Official results and statistics')]
 rows=acquire(tasks);r=next(r for r in rows if r['id']=='sos-auditors');s=raw(r).decode();chunks=re.split(r'<h2[^>]*id="([^"]*CountyAuditor)"[^>]*>',s)
 counties=json.loads((STATE/'data/turnout/priority-set.json').read_text())['all_counties'];by={c['county']:c for c in counties};directory=[];tasks=[]
 for i in range(1,len(chunks),2):
  body=chunks[i+1];name=html.unescape(re.sub('<[^>]+>','',body.split('</h2>')[0])).strip()
  m=re.search(r'<th[^>]*>Website</th>\s*<td>\s*<a[^>]*href="([^"]+)"',body)
  assert name in by,(name,chunks[i])
  c=by[name];url=html.unescape(m[1]) if m else None
  phone=re.search(r'<a href="tel:([^"]+)"',body)
  directory.append({'county':name,'county_fips':c['county_fips'],'rank_2024':c['rank_2024'],'priority':c['in_minimum80'],'anchor':chunks[i],'directory_url':r['final_url']+'#'+chunks[i],'auditor_url':url,'phone':phone[1] if phone else None,'directory_source_id':r['id'],'source_position':i//2+1})
  if url:tasks.append(('county-'+c['county_fips']+'-seed',url,r['final_url']+'#'+chunks[i],'Website'))
 assert len(directory)==99 and len({c['county_fips'] for c in directory})==99
 dump(ROOT/'auditor-directory.json',directory);acquire(tasks)
def score(l):
 t=(l['text']+' '+l['url']).lower();n=0
 if not any(x in t for x in ['elect','ballot','canvass','precinct','polling','voting']):return -999
 if any(x in t for x in ['search/results','calendar.aspx','gift certif','birth certif','death certif','notar','business','str aw','strawpoll','registration form','register to vote','voter-registration','/elected_officials','current-mayor','school-board-members']):return -999
 if any(x in t for x in ['2026 general','general election 2026','november 3, 2026','november_3_2026','general_2026','general-election-2026','2026-general','2026_general']):n+=100
 if 'result' in t:n+=50
 if any(x in t for x in ['elections','election/','election_information','election-information','election_and_voting']):n+=15
 if any(x in t for x in ['sample ballot','candidate list','certif','canvass']):n+=25
 if '2026' in t:n+=20
 if any(x in t for x in ['2025','2024','2023','2022','2021','2020']):n-=25
 if any(x in t for x in ['facebook','twitter','instagram','mailto:','tel:','javascript:','news-resources']):n=-999
 return n
def follow():
 rows=ledger();directory=json.loads((ROOT/'auditor-directory.json').read_text());tasks=[]
 for c in directory:
  if not c['priority']:continue
  own=[r for r in rows if r['id'].startswith('county-'+c['county_fips']+'-')]
  tested={urldefrag(r['url'])[0] for r in own};candidate={}
  for r in own:
   if not r.get('view_path') or r.get('status')!=200:continue
   v=json.loads((ROOT/r['view_path']).read_text())
   for l in v['links']:
    u=urldefrag(l['url'])[0]
    if urlparse(u).scheme not in ('http','https') or u in tested:continue
    n=score(l)
    if n<15:continue
    if u not in candidate or n>candidate[u][0]:candidate[u]=(n,r,l)
  cap=max(0,18-len(own));take=min(4,cap)
  for j,(n,r,l) in enumerate(sorted(candidate.values(),key=lambda a:-a[0])[:take]):tasks.append(('county-'+c['county_fips']+'-linked'+str(len(own)+j),urldefrag(l['url'])[0],r['final_url'],l['text'].strip()))
 acquire(tasks)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['seeds','follow']);a=p.parse_args();globals()[a.mode]()
