#!/usr/bin/env python3
"""Bounded public research captures, with exact source metadata and compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,requests,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
URLS={'bdn-senate-embed': 'https://mikeshepherdme.github.io/bdn-election-embeds/embed-senate-dem-primary.html', 'bdn-town-embed': 'https://mikeshepherdme.github.io/bdn-election-embeds/embed-town-lookup.html', 'wgme-results': 'https://wgme.com/news/local/maine-2026-primary-election-results', 'wabi-results': 'https://www.wabi.tv/politics/election-results/', 'wmtw-embed': 'https://ehub.htvapps.com/wmtw/wp-json/election-hub/v1/iframe-embed/1754', 'bdn-senate-data': 'https://mikeshepherdme.github.io/bdn-election-embeds/public/data/race/us-senate-democratic-primary.json', 'bdn-towns-data': 'https://mikeshepherdme.github.io/bdn-election-embeds/public/towns.json', 'sos-september-process': 'https://www3.maine.gov/sos/news/general-election-two-months-away-secretary-states-office-provides-update-maine-election-1', 'sos-absentee-2026': 'https://www3.maine.gov/sos/news/maine-voters-can-request-absentee-ballots-nov-3-election-starting-today-ballots-will-be-mailed', 'bdn-results': 'https://www.bangordailynews.com/maine-election-results/', 'bdn-towns': 'https://www.bangordailynews.com/search-maine-election-results-by-town/', 'bdn-counting': 'https://www.bangordailynews.com/2026/06/09/politics/maine-primary-ranked-choice-voting-counting-joam40zk0w/', 'wgme-primary-article': 'https://wgme.com/news/local/maine-senator-susan-collins-wins-uncontested-republican-senate-primary-election-day-graham-platner-governor-janet-mills', 'wmtw-cumberland-primary': 'https://www.wmtw.com/article/cumberland-county-maine-2026-primary-election-results/71528559', 'mainepublic-home': 'https://www.mainepublic.org/', 'sos-rcv': 'https://www.maine.gov/sos/elections-voting/upcoming/ranked-choice-voting-tabs', 'sos-upcoming': 'https://www.maine.gov/sos/elections-voting/upcoming-elections', 'nyt-elections': 'https://www.nytimes.com/section/politics/elections', 'wagm-results': 'https://www.wagmtv.com/politics/election-results/', 'monitor-rcv-count': 'https://themainemonitor.org/inside-final-day-ranked-choice-voting-count/', 'rcv-statute-current': 'https://legislature.maine.gov/statutes/21-A/title21-Asec723-A.html', 'wagm-state-panel': 'https://www.wagmtv.com/maine-election-results/', 'wagm-ap-one': 'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/110246/32468.html', 'wagm-ap-two': 'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/110246/32509.html'}
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
