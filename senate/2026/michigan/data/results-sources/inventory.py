#!/usr/bin/env python3
"""Re-fetch public county landings linked by SOS; bounded one-page inspection, no feed guessing."""
import csv,json,hashlib,subprocess,datetime,re,concurrent.futures,gzip
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
ROOT=Path(__file__).resolve().parent
DIRECTORY='https://www.michigan.gov/sos/elections/election-results-and-data/candidate-listings-and-election-results-by-county'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.parts=[];self.a=None
 def handle_starttag(self,t,a):
  if t=='a':self.a=[(dict(a).get('href') or ''),'']
 def handle_data(self,d):
  self.parts.append(d)
  if self.a is not None:self.a[1]+=d
 def handle_endtag(self,t):
  if t=='a' and self.a is not None:self.links.append(self.a);self.a=None

def fetch(url):
 p=subprocess.run(['curl','-L','-A','Mozilla/5.0','--max-time','25','-sS','-w','\n%{http_code}\n%{url_effective}',url],capture_output=True)
 chunks=p.stdout.rsplit(b'\n',2)
 if len(chunks)!=3:return {'url':url,'error':p.stderr.decode(errors='replace')}
 b,status,final=chunks;h=Page();decoded=gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b;h.feed(decoded.decode(errors='replace'))
 return {'url':url,'final_url':final.decode(),'http_status':status.decode(),'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'links':[{'text':re.sub(r'\s+',' ',t).strip(),'url':urljoin(final.decode(),u)} for u,t in h.links if re.search(r'elect|result|2024|2022|clarity|reporting|enhanced',u+' '+t,re.I)],'text':re.sub(r'\s+',' ',' '.join(h.parts))[:80000],'error':p.stderr.decode(errors='replace')}
if __name__=='__main__':
 p=Page();p.feed((ROOT/'directory.html').read_text());start=next(i for i,(u,t) in enumerate(p.links) if t.strip()=='Alcona');items=p.links[start:start+83];assert items[-1][1].strip()=='Wexford'
 (ROOT/'directory-links.json').write_text(json.dumps({'source':DIRECTORY,'research_date':'2026-10-17','links':items},indent=2))
 def one(item):
  u,n=item;n=n.strip();existing=ROOT/(re.sub('[^a-z0-9]+','-',n.lower())+'.json');r=json.loads(existing.read_text()) if existing.exists() else fetch(u);(ROOT/(re.sub('[^a-z0-9]+','-',n.lower())+'.json')).write_text(json.dumps(r,indent=2));return n,u,r
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:rows=list(ex.map(one,items))
 with (ROOT.parent/'official-results-sources.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['county','county_fips','authority_url','landing_url','resolved_url','http_status','verification','research_date','evidence_file','linked_results_urls','feed_status']);w.writeheader()
  for i,(n,u,r) in enumerate(rows):w.writerow(dict(county=n,county_fips={'Saginaw':'26145','St. Clair':'26147','St. Joseph':'26149','Sanilac':'26151','Schoolcraft':'26153','Shiawassee':'26155'}.get(n,f'26{2*i+1:03}'),authority_url=DIRECTORY,landing_url=u,resolved_url=r.get('final_url',''),http_status=r.get('http_status',''),verification='landing retrieved; inspect extracted links' if r.get('http_status')=='200' else 'landing access failed; SOS linkage verified',research_date='2026-10-17',evidence_file='results-sources/'+re.sub('[^a-z0-9]+','-',n.lower())+'.json',linked_results_urls=' | '.join(x['url'] for x in r.get('links',[]) if re.search('result|clarity|reporting|enhanced',x['url']+' '+x['text'],re.I)),feed_status='untested'))
 print('counties',len(rows),'HTTP200',sum(r.get('http_status')=='200' for n,u,r in rows))
