from research import *
p=ROOT/'requests';rs=json.loads((ROOT/'municipal-route-discovery.json').read_text());jobs={}
for r in rs:
 if not r['priority']:continue
 for id in r['route_request_ids']:
  m=json.loads((p/f'{id}.json').read_text())
  if m.get('status')!=200:continue
  s=gzip.decompress((ROOT/m['body_path']).read_bytes()).decode(errors='replace')
  for u in re.findall(r'["\'](/Pages/MenuMain/HiddenMainSubMenus\?[^"\']+)["\']',s):
   url=urllib.parse.urljoin(m.get('final_url',m['request_url']),html.unescape(u));jobs.setdefault(url,[]).append({'rank':r['rank'],'parent_request_id':id})
print('actual public CMS menu routes',len(jobs),flush=True)
def go(u):
 id=digest(u.encode())[:20];f=p/f'{id}.json';m=json.loads(f.read_text()) if f.exists() else fetch(u)
 if m.get('status') is None and 'SSLCertVerification' in m.get('error',''):
  from curl_repair import curl_fetch
  f=p/f'{id}-curl.json';m=json.loads(f.read_text()) if f.exists() else curl_fetch(u)
 return {'url':u,'request_id':m['id'],'status':m.get('status'),'parents':jobs[u]}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:out=list(ex.map(go,jobs))
(ROOT/'menu-tests.json').write_text(json.dumps(out,indent=2)+'\n');print('menu results',[(x['status'],x['request_id']) for x in out],flush=True)
