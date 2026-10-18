from research import *
from collections import Counter
pages=[];rows=[]
for req in json.loads((ROOT/'phase3.json').read_text()):
 if 'find-a-municipal-clerk' not in req['url']:continue
 m=json.loads((ROOT/'requests'/f"{req['id']}.json").read_text());s=gzip.decompress((ROOT/m['body_path']).read_bytes()).decode()
 names=re.findall(r'views-field-title.*?<div class="field-content">(.*?)</div>',s,re.S)
 names=[html.unescape(re.sub('<[^>]+>','',n)).strip() for n in names]
 pages.append({'page':int(urllib.parse.parse_qs(urllib.parse.urlparse(req['url']).query)['page'][0]),'request_id':req['id'],'status':req['status'],'names':names,'count':len(names)})
 for n in names:rows.append(n)
clerk=json.loads((ROOT/'current-clerk-roster.json').read_text())['rows'];csvnames={r['municipality'] for r in clerk};setnames=set(rows)
a={'pagination_advertised_last_page':33,'pages_tested':len(pages),'pages':pages,'html_rows':len(rows),'html_unique_names':len(setnames),'duplicate_html_names':{n:v for n,v in Counter(rows).items() if v>1},'csv_rows':len(clerk),'csv_only_names':sorted(csvnames-setnames),'html_only_names':sorted(setnames-csvnames),'meaning':'Different public SOS rosters, both retained; neither historical native units nor raw count establishes 2026 legal reporting-authority count.'}
(ROOT/'directory-audit.json').write_text(json.dumps(a,indent=2)+'\n')
print({k:v for k,v in a.items() if k!='pages'})
