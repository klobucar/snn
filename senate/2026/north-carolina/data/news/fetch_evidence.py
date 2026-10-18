#!/usr/bin/env python3
"""Bounded source snapshots; offline inspection uses retained compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,re,requests
ROOT=Path(__file__).resolve().parent
URLS={
 'wral-results-2024':'https://www.wral.com/2024-november-general-election-results/21683978/',
 'wral-results-linked':'https://www.wral.com/news/2024-general-election-results',
 'wral-counting-2024':'https://www.wral.com/archive/21707382/',
 'wbtv-results':'https://www.wbtv.com/politics/election-results/',
 'wbtv-nc-interactive':'https://www.wbtv.com/north-carolina-election-results/',
 'witn-results':'https://www.witn.com/politics/election-results/',
 'witn-nc-interactive':'https://www.witn.com/north-carolina-election-results/',
 'wect-results':'https://www.wect.com/politics/election-results/',
 'wway-results':'https://www.wwaytv3.com/election-results/',
 'wway-2026-embed':'https://www.wwaytv3.com/content/uploads/elections/2026Election.html',
 'wway-2024-table':'https://www.wwaytv3.com/content/uploads/weather-images/wx/Election2024.html',
 'wlos-home':'https://wlos.com/',
 'wxii-home':'https://www.wxii12.com/',
 'wunc-live-2024':'https://www.wunc.org/live-updates/2024-election-day-north-carolina-voting-results-live',
 'wunc-npr-sourcing':'https://www.wunc.org/2024-11-05/heres-how-npr-will-report-the-2024-election-results',
 'nyt-elections':'https://www.nytimes.com/section/politics/elections',
 'wlos-config':'https://sbgcg.com/Ticker/Stations/WLOS/get_elections_url.php',
 'wlos-embed':'https://sbgcg.com/Ticker/Stations/WLOS/elections.html',
 'wbtv-ap-nc':'https://interactives.apelections.org/election-results/customers/layouts/organization-layouts/published/110246/32532.html',
 'wral-ap':'https://interactives.ap.org/election-results/customers/layouts/organization-layouts/published/41164/15089.html',
 'wlos-results':'https://wlos.com/news/election-results',
 'wral-2024-data':'https://assets.wral.com/26bf8e22-4825-4253-b748-81d26c75b930',
 'ncsbe-timeline':'https://www.ncsbe.gov/results-data/election-results/election-night-reporting-timeline',
 'ncsbe-results':'https://www.ncsbe.gov/results-data/election-results',
 'ncsbe-absentee':'https://www.ncsbe.gov/results-data/absentee-and-provisional-data',
 'ncsbe-dashboard-about':'https://www.ncsbe.gov/results-data/election-results/about-election-results-dashboard',
 'ncsbe-2026-guide':'https://s3.amazonaws.com/dl.ncsbe.gov/Candidate%20Filing/2025-26_Statewide_Candidate_Guide.pdf',
 'ncsbe-audits':'https://www.ncsbe.gov/about-elections/election-security/post-election-procedures-and-audits'}
def fetch(item):
 key,url=item; row={'id':key,'url':url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=requests.get(url,timeout=35); ext='.pdf.gz' if 'pdf' in r.headers.get('Content-Type','') else '.html.gz'; path=ROOT/(key+ext); path.write_bytes(gzip.compress(r.content,mtime=0))
  row.update(status=r.status_code,final_url=r.url,raw_sha256=hashlib.sha256(r.content).hexdigest(),asset=path.name,stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=len(r.content),headers=dict(r.headers))
 except requests.RequestException as e: row['error']=str(e)
 return row
if __name__=='__main__':
 rows=list(ThreadPoolExecutor(max_workers=4).map(fetch,URLS.items()))
 config=next(r for r in rows if r['id']=='wlos-config')
 if config.get('status')==200:
  destination=json.loads(gzip.decompress((ROOT/config['asset']).read_bytes()))['url']
  rows.append(fetch(('wlos-playlist',destination)))
 (ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
 for row in rows: print(row['id'],row.get('status',row.get('error')))
