#!/usr/bin/env python3
"""Bounded public research captures, with exact source metadata and compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,requests,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
URLS={
 'akpublic-general-2026':'https://alaskapublic.org/news/politics/elections/2026-10-05/what-to-know-about-alaskas-general-election',
 'ktoo-general-2026':'https://www.ktoo.org/2026/10/12/what-to-know-about-alaskas-general-election/',
 'knom-nome-primary':'https://knom.org/2026/08/18/nome-unofficial-primary-election-results-are-here/',
 'kyuk-home':'https://www.kyuk.org/',
 'division-calendar':'https://www.elections.alaska.gov/calendar/',
 'beacon-results':'https://alaskabeacon.com/live-election-results/',
 'akpublic-elections':'https://alaskapublic.org/elections',
 'akpublic-rcv-2024':'https://alaskapublic.org/news/2024-11-20/ranked-choice-tabulation-is-set-for-5-p-m-today-watch-it-live-here',
 'ans-results':'https://www.alaskasnewssource.com/politics/election-results/',
 'ktoo-home':'https://www.ktoo.org/',
 'division-information':'https://www.elections.alaska.gov/election-information/',
 'division-results':'https://www.elections.alaska.gov/election-results/',
 'nyt-elections':'https://www.nytimes.com/section/politics/elections'}
def fetch(item):
 key,url=item;row={'id':key,'url':url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=requests.get(url,timeout=35);path=ROOT/(key+'.html.gz');path.write_bytes(gzip.compress(r.content,mtime=0))
  row.update(status=r.status_code,final_url=r.url,raw_sha256=hashlib.sha256(r.content).hexdigest(),asset=path.name,stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=len(r.content),headers=dict(r.headers))
 except requests.exceptions.SSLError as e:
  row['requests_error']=str(e)
  with tempfile.TemporaryDirectory() as t:
   body=Path(t)/'body';hdr=Path(t)/'headers'
   c=subprocess.run(['curl','--silent','--show-error','--location','--max-time','35','--dump-header',str(hdr),'--output',str(body),'--write-out','%{http_code}\\n%{url_effective}',url],capture_output=True,text=True)
   row['transport']='system curl with default certificate verification'
   if c.returncode==0:
    code,final=c.stdout.split('\\n',1) if '\\n' in c.stdout else c.stdout.split('\n',1)
    raw=body.read_bytes();path=ROOT/(key+'.html.gz');path.write_bytes(gzip.compress(raw,mtime=0))
    row.update(status=int(code),final_url=final,raw_sha256=hashlib.sha256(raw).hexdigest(),asset=path.name,stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=len(raw),raw_headers=hdr.read_text())
   else:row['error']=c.stderr
 except requests.RequestException as e:row['error']=str(e)
 return row
if __name__=='__main__':
 rows=list(ThreadPoolExecutor(max_workers=4).map(fetch,URLS.items()));(ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
 for r in rows:print(r['id'],r.get('status',r.get('error')))
