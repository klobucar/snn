#!/usr/bin/env python3
"""Bounded public research captures, with exact source metadata and compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,requests,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
URLS={'kcci-senate-primary': 'https://www.kcci.com/article/iowa-primary-election-results-us-senate-2026/71453516', 'kwqc-results': 'https://www.kwqc.com/politics/election-results/', 'ipr-npr-embed': 'https://apps.npr.org/primary-election-results-2026/states/IA.html?embedded=true', 'kcci-ap-embed': 'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/104899/29218.html', 'sos-general-2026': 'https://sos.iowa.gov/news-resources/secretary-pate-encourages-iowans-make-plan-vote-2026-general-election', 'cass-results': 'https://www.casscountyia.gov/county-government/elections/', 'ipr-primary': 'https://www.iowapublicradio.org/political-news/2026-06-02/2026-iowa-primary-election-results', 'kcrg-results': 'https://www.kcrg.com/politics/election-results/', 'ktiv-results': 'https://www.ktiv.com/politics/election-results/', 'kcci-home': 'https://www.kcci.com/', 'kwqc-home': 'https://www.kwqc.com/', 'nyt-elections': 'https://www.nytimes.com/section/politics/elections', 'kcrg-state-panel': 'https://www.kcrg.com/iowa-election-results/', 'kcci-primary-final': 'https://www.kcci.com/article/iowa-primary-election-results-us-senate-2026-turek-wahls-hinson-carlin/71475902', 'kcrg-ap-national': 'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/110246/32468.html', 'kcrg-ap-state': 'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/110246/32444.html', 'npr-senate-primary': 'https://apps.npr.org/primary-election-results-2026/data/IA_S_6_2_2026.json', 'npr-senate-primary-counties': 'https://apps.npr.org/primary-election-results-2026/data/IA_S_6_2_2026_counties.json', 'sos-results-index': 'https://sos.iowa.gov/iowans/election-results-statistics', 'sos-2024-canvass': 'https://sos.iowa.gov/elections/pdf/2024/general/canvsummary.pdf', 'sos-2024-precinct-app': 'https://electionresults.iowa.gov/IA/122322/web.345435/', 'sos-2022-canvass': 'https://sos.iowa.gov/elections/pdf/2022/general/canvsummary.pdf', 'sos-2022-precinct-index': 'https://sos.iowa.gov/precinct-results-county-2022-general-0', 'sos-2020-canvass': 'https://sos.iowa.gov/elections/pdf/2020/general/canvsummary.pdf', 'sos-2020-precinct-index': 'https://sos.iowa.gov/precinct-results-county-2020-general'}
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
