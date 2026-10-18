from research import *
p=ROOT/'requests';index=json.loads((ROOT/'municipal-route-discovery.json').read_text());units=[x for x in index if x['priority']]
# Deterministic bounded audit; actual observed links only. Exclusions are navigational,
# not claims of missing results. Every page's full link catalog remains retained.
def score(l,asset=False):
 t=l['text'].lower();u=l['url'].lower();v=0
 if re.search(r'water|lead|radon|budget|agenda|planning|employment|search|minutes|assessment|test results|bid result|recycling',t):return -100
 if re.search(r'election results|voting results|election returns',t):v+=120
 elif 'results' in t:v+=55
 if re.search(r'november.{0,10}(2024|2026)|2024.{0,20}general|2026.{0,20}general',t):v+=90
 if re.search(r'election|voting|voter',t):v+=35
 if re.search(r'clerk',t):v+=10
 if re.search(r'2024|2026',t):v+=12
 if re.search(r'2020|2021|2019|2018|2017',t):v-=25
 if 'sample' in t or 'sample' in u:v-=40
 if re.search(r'\.pdf(?:\?|$)|\.xlsx?(?:\?|$)|\.csv(?:\?|$)',u):v+=5
 if '#' in u and u.split('#')[0]==l.get('parent','').split('#')[0]:return -100
 return v
def getlinks(id):
 f=p/f'{id}.links.json'
 return json.loads(f.read_text())['links'] if f.exists() else []
def isasset(u):return bool(re.search(r'\.(pdf|xlsx?|csv|txt|zip)(?:\?|$)|/DocumentCenter/View/|/DocumentCenter/Download/|/vertical/.*/uploads/',u,re.I))
def navlinks(m):
 rows=[]
 for l in getlinks(m['id']):
  u=l['url'].split('#')[0]
  if not u.startswith(('http://','https://')) or isasset(u):continue
  if any(x in u.lower() for x in ['facebook.com','twitter.com','youtube.com','instagram.com','google.com','maineballot.org']):continue
  l={**l,'url':u,'parent':m.get('final_url',m['request_url'])};sc=score(l)
  if sc>=10:rows.append((sc,l))
 out=[]
 for sc,l in sorted(rows,key=lambda x:-x[0]):
  if not any(x['url']==l['url'] for x in out):out.append(l)
 return out
jobs={};inspection=[]
for unit in units:
 rec={**unit,'pages':[],'selected_navigation':[],'downloads':[]}
 for id in unit['route_request_ids']+unit.get('auxiliary_menu_ids',[]):
  m=json.loads((p/f'{id}.json').read_text());rec['pages'].append(id)
  for l in navlinks(m)[:3]:
   if l['url']!=m.get('final_url') and l['url']!=m['request_url']:
    jobs[l['url']]=l;rec['selected_navigation'].append(l)
 inspection.append(rec)
def go(u):
 u=urllib.parse.quote(u,safe=':/?&=%#');id=digest(u.encode())[:20];f=p/f'{id}.json';m=json.loads(f.read_text()) if f.exists() else fetch(u)
 if m.get('status') is None and 'SSLCertVerification' in m.get('error',''):
  from curl_repair import curl_fetch
  ff=p/f'{id}-curl.json';m=json.loads(ff.read_text()) if ff.exists() else curl_fetch(u)
 return u,m
print('layer1 requests',len(jobs),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:got=dict(ex.map(go,jobs))
for r in inspection:
 for l in r['selected_navigation']:
  u=urllib.parse.quote(l['url'],safe=':/?&=%#');r['pages'].append(got[u]['id'])
# One adaptive second step follows links found on actual result/election pages.
jobs2={}
for r in inspection:
 chosen=set(json.loads((p/f'{id}.json').read_text()).get('final_url') for id in r['pages']);r['second_navigation']=[]
 c=[]
 for id in r['pages'][1:]:
  m=json.loads((p/f'{id}.json').read_text())
  c.extend(navlinks(m))
 for l in sorted(c,key=lambda l:-score(l)):
  if l['url'] not in chosen:
   chosen.add(l['url']);r['second_navigation'].append(l);jobs2[l['url']]=l
   if len(r['second_navigation'])>=2:break
print('layer2 requests',len(jobs2),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:got2=dict(ex.map(go,jobs2))
for r in inspection:
 for l in r['second_navigation']:
  u=urllib.parse.quote(l['url'],safe=':/?&=%#');r['pages'].append(got2[u]['id'])
(ROOT/'priority-crawl.json').write_text(json.dumps(inspection,indent=2)+'\n')
print('done pages',sum(len(r['pages']) for r in inspection),flush=True)
