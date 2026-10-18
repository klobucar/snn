#!/usr/bin/env python3
"""Download only observed NCSBE links; retain original bytes and HTTP provenance.
No Git operations. Stdlib-only; only writes under this script's directory.
"""
import concurrent.futures, datetime, hashlib, json, pathlib, urllib.request
from html.parser import HTMLParser
BASE = pathlib.Path(__file__).resolve().parent
INDEX = 'https://www.ncsbe.gov/results-data/election-results/historical-election-results-data'
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.href=None; self.label=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a': self.href=dict(attrs).get('href'); self.label=[]
    def handle_data(self, data):
        if self.href: self.label.append(data)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            self.links.append((' '.join(''.join(self.label).split()),self.href)); self.href=None

def source_context(name,headers):
    years={2014:('2014-11-04','US SENATE','1152'),2020:('2020-11-03','US SENATE','1374'),2022:('2022-11-08','US SENATE','1378'),2024:('2024-11-05','US PRESIDENT','1393')}
    year=next((y for y in years if name.startswith(str(y)+'-') or name=='house-2014-statistics.pdf' and y==2014),None)
    date,contest,group=years.get(year,(None,None,None))
    status='NCSBE certified-results archive PDF' if 'certified' in name else 'NCSBE Election Results ZIP; reconciliation retained separately' if name.endswith('results.zip') else 'House Clerk official federal election statistics' if name.startswith('house-') else 'primary reference page or layout; not a result feed'
    return {'election_date':date,'selected_contest':contest,'selected_contest_group_id':group,'source_status':status,'source_update_time_http_last_modified':headers.get('Last-Modified'),'source_update_time_note':'HTTP file metadata only; no correction chronology inferred','extractor_version':'build_baselines.py v1'}

def fetch(name,url):
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    req=urllib.request.Request(url,headers={'User-Agent':'NC historical election research; Python urllib'})
    with urllib.request.urlopen(req,timeout=120) as r:
        data=r.read(); headers=dict(r.headers); final=r.url; status=r.status
    (BASE/name).write_bytes(data)
    meta={'file':name,'url':url,'final_url':final,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'request_started_at_utc':started,'http_status':status,'response_headers':headers,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    meta.update(source_context(name,headers))
    (BASE/(name+'.meta.json')).write_text(json.dumps(meta,indent=2)+'\n')
    return meta

def main():
    manifest=[fetch('ncsbe-historical-index.html',INDEX)]
    p=Links();p.feed((BASE/'ncsbe-historical-index.html').read_text())
    jobs=[('layout-results.txt',next(u for t,u in p.links if u.endswith('/layout_results_pct.txt')))]
    for year,month,day in [(2024,11,5),(2022,11,8),(2020,11,3),(2014,11,4)]:
        date=f'{year} Nov {day:02d} Election'
        for suffix,ending in [('results.zip','- Results (ZIP)'),('certified-contest.pdf','- Certified Results by Contest (PDF)'),('certified-county.pdf','- Certified Results by County (PDF)')]:
            if year==2014 and suffix!='results.zip': continue
            hits=[(t,u) for t,u in p.links if date in t and t.endswith(ending)]
            assert len(hits)==1,(date,suffix,hits)
            jobs.append((f'{year}-{suffix}',hits[0][1]))
    jobs.extend([('senate-class-II.html','https://www.senate.gov/senators/Class_II.htm'),('senate-class-III.html','https://www.senate.gov/senators/Class_III.htm')])
    jobs.append(('house-2014-statistics.pdf','https://clerk.house.gov/member_info/electionInfo/2014/114-statistics.pdf'))
    jobs.append(('census-national-county2020.txt','https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for meta in pool.map(lambda j:fetch(*j),jobs):
            manifest.append(meta);print(meta['file'],meta['bytes'],meta['sha256'])
    (BASE/'manifest.json').write_text(json.dumps({'collector_version':'1','sources':manifest},indent=2)+'\n')
if __name__=='__main__':main()
