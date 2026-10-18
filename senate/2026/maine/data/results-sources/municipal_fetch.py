from research import *
from reconcile import norm
p=ROOT/'requests';ls=json.loads((p/'f7dbdb34f5df9316e4d5.links.json').read_text())['links'];routes={}
for l in ls:
 t=re.sub(r'\s+',' ',l['text']).strip();m=re.match(r'(.+?) (election|town|Facebook|contact info|tribe) website$',t)
 if m:routes.setdefault(norm(m[1]),[]).append({'url':l['url'],'discovery_label':t,'discovery_request_id':'f7dbdb34f5df9316e4d5','route_type':m[2]})
units=json.loads((ROOT/'authority-reconciliation.json').read_text());jobs=[];index=[]
for u in units:
 n=u['native_name'].strip().split('/')[0];r=routes.get(norm(n),[])
 # official tribal label differs from municipality; do not substitute other tribal jurisdiction.
 if n=='Penobscot Indian Island':r=routes.get(norm('Penobscot Nation'),[])
 if n=='Indian Twp':r=routes.get(norm('Indian Township Reservation'),[])
 if n=='Pleasant Point':r=routes.get(norm('Pleasant Point Reservation'),[])
 usable=[x for x in r if x['route_type'] not in ('contact info','Facebook')]
 for x in usable:
  if x['url'] not in jobs:jobs.append(x['url'])
 index.append({'native_key':u['native_key'],'rank':u['rank'],'priority':u['priority'],'name':u['native_name'],'discovery_routes':r,'route_request_ids':[]})
(ROOT/'municipal-route-discovery.json').write_text(json.dumps(index,indent=2)+'\n')
print('discovery',len(routes),'native usable',sum(bool(x['discovery_routes']) for x in index),'jobs',len(jobs),flush=True)
def go(u):
 u=urllib.parse.quote(u,safe=':/?&=%#');id=digest(u.encode())[:20];f=p/f'{id}.json'
 m=json.loads(f.read_text()) if f.exists() else fetch(u)
 return {'publisher_url':u,'request_id':m['id'],'status':m.get('status'),'bytes':m['entity_bytes_retained'],'final_url':m.get('final_url'),'complete':m['complete']}
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
 out=[]
 for i,r in enumerate(ex.map(go,jobs)):
  out.append(r)
  if (i+1)%40==0:print('fetched',i+1,flush=True)
(ROOT/'municipal-fetches.json').write_text(json.dumps(out,indent=2)+'\n')
for x in index:
 for r in out:
  if any(urllib.parse.quote(d['url'],safe=':/?&=%#')==r['publisher_url'] for d in x['discovery_routes']):x['route_request_ids'].append(r['request_id'])
(ROOT/'municipal-route-discovery.json').write_text(json.dumps(index,indent=2)+'\n')
print('done',len(out),{str(s):sum(r['status']==s for r in out) for s in set(r['status'] for r in out)},flush=True)
