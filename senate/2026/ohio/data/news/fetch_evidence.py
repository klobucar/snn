#!/usr/bin/env python3
"""Bounded public research captures, with exact source metadata and compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,requests,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
URLS={
 'toledo13-results':'https://www.13abc.com/politics/election-results/',
 'wlwt-embed':'https://ehub.htvapps.com/wlwt/wp-json/election-hub/v1/iframe-embed/1826',
 'wosu-npr-embed':'https://apps.npr.org/primary-election-results-2026/states/OH.html?embedded=true',
 'wlwt-widget':'https://ehub.htvapps.com/wlwt/wp-json/election-hub/v1/widget/1826',
 'sos-schedule':'https://www.ohiosos.gov/elections/voting-schedule-text-only',
 'sos-directives':'https://www.ohiosos.gov/elections/elections-administration/directives',
 'wcpo-top-xml':'https://mediaassets.wcpo.com/NWT/electionresults/Top_Races.xml',
 'wcpo-results':'https://www.wcpo.com/election-results',
 'wcpo-national-2024':'https://www.wcpo.com/live-election-results-president-map',
 'cleveland19-results':'https://www.cleveland19.com/politics/election-results/',
 'wosu-primary-2026':'https://www.wosu.org/politics-government/2026-05-05/2026-ohio-primary-election-results',
 'wlwt-primary-2026':'https://www.wlwt.com/article/election-results-ohio-house-senate-governor-primary-races/71204035',
 'blade-politics':'https://www.toledoblade.com/local/politics',
 'sos-live':'https://liveresults.ohiosos.gov/',
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
