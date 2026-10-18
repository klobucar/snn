from research import *
p=ROOT/'requests';records=json.loads((ROOT/'priority-crawl.json').read_text())
# Extend completed priority chain with independent TLS repair successes.
for r in records:
 if r['rank']==1:r['pages']+=['450018e7c1ea2e236009-curl','9f00c1fd2906725b9672-curl']
 if r['rank']==14:r['pages']+=['b003b346eef2d89950b7-curl']
 if r['rank']==22:r['pages']=['9aefb960640e24b8df40','80980b86f6df4740a540']
 r['pages']=list(dict.fromkeys(r['pages']))
def urlkey(u):
 p=urllib.parse.urlparse(urllib.parse.unquote(u));return (p.netloc.replace('www3.maine.gov','www.maine.gov').removeprefix('www.'),p.path,p.query)
reused={}
for m in json.loads((ROOT.parent/'turnout/manifest.json').read_text()):
 for k in ['original_url','request_url','final_url']:
  if m.get(k):reused[urlkey(m[k])]=m

def links(id):
 f=p/f'{id}.links.json';return json.loads(f.read_text())['links'] if f.exists() else []
def score(l):
 t=l['text'].lower();u=urllib.parse.unquote(l['url']).lower()
 if re.search(r'water|lead|radon|bid result|recycling|assessment|tax.bill|real.estate|zoning|ordinance|comprehensive|valuation|annual.report|street.list|ward.map',t+' '+u):return -100
 sc=0
 if re.search('result|return of vote|tally',t+' '+u):sc+=30
 if re.search(r'nov.{0,9}5.{0,9}2024|2024.{0,10}nov|11[._/-]0?5[._/-](20)?24|general.{0,20}2024|2024.{0,20}general',t+' '+u):sc+=100
 if re.search(r'2026|[._/-]26[._/-]',t+' '+u):sc+=20
 if re.search(r'\b(state|federal|general)\b',t+' '+u):sc+=12
 if re.search('municipal|town meeting|school|rsu|msad',t+' '+u):sc-=10
 if re.search('sample|ballot.*blank',t+' '+u):sc-=100
 if re.search('201[0-9]|2020|2021',t+' '+u):sc-=20
 return sc
jobs={}
for r in records:
 r['downloads']=[];candidates=[]
 if r['rank']==22:
  r['downloads']=[{'request_id':id,'url':json.loads((p/f'{id}.json').read_text())['publisher_url'],'link_text':'State-administered publication / historical CD2 schema test; not current November counts','kind':'state publication'} for id in ['faa16009e9a48f60f351','bac6a7f3e0a72ffb3fdb','ea9168a83a2208b62e32','266a08d91013335ab173','3e8ead0ae70c94422366']]
  r['selected_download_links']=[]
  continue
 for id in r['pages']:
  m=json.loads((p/f'{id}.json').read_text());b=gzip.decompress((ROOT/m['body_path']).read_bytes())
  if b.startswith((b'%PDF',b'PK')) and m.get('status')==200:r['downloads'].append({'request_id':id,'url':m['publisher_url'],'link_text':'Downloaded through actual navigation/primary repair','kind':'existing public document'})
  for l in links(id):
   u=l['url'].split('#')[0]
   isasset=bool(re.search(r'\.(pdf|xlsx?|csv|txt|jpg|png)(?:\?|$)|/DocumentCenter/View/|/ImageRepository/Document|/resource-manager/view/|/media/[0-9]+|files.heygov.com',u,re.I))
   if isasset and score(l)>=30:candidates.append({**l,'parent_request_id':id})
 selected=[]
 for l in sorted(candidates,key=lambda x:-score(x)):
  if l['url'] not in {x['url'] for x in selected} and l['url'] not in {x['url'] for x in r['downloads']}:
   selected.append(l)
   if len(selected)>=3:break
 r['selected_download_links']=selected
 for l in selected:
  if urlkey(l['url']) not in reused:jobs[l['url']]=l
print('unique linked downloads',len(jobs),flush=True)
def go(u):
 u=urllib.parse.quote(u,safe=':/?&=%#');id=digest(u.encode())[:20];f=p/f'{id}.json';m=json.loads(f.read_text()) if f.exists() else fetch(u)
 if m.get('status') is None and 'SSLCertVerification' in m.get('error',''):
  from curl_repair import curl_fetch
  ff=p/f'{id}-curl.json';m=json.loads(ff.read_text()) if ff.exists() else curl_fetch(u)
 return u,m
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:got=dict(ex.map(go,jobs))
for r in records:
 for l in r['selected_download_links']:
  reuse=reused.get(urlkey(l['url']))
  if reuse:
   r['downloads'].append({'url':l['url'],'link_text':l['text'],'parent_request_id':l['parent_request_id'],'kind':'READ-ONLY existing turnout evidence','reuse_source_id':reuse['source_id'],'reused_body_path':'../turnout/'+reuse['saved_path'],'entity_sha256':reuse['original_sha256'],'http_status':reuse['http_status']})
  else:
   m=got[urllib.parse.quote(l['url'],safe=':/?&=%#')];r['downloads'].append({'url':l['url'],'link_text':l['text'],'parent_request_id':l['parent_request_id'],'kind':'new bounded complete public response' if m['complete'] else 'incomplete bounded response','request_id':m['id']})
(ROOT/'priority-inspections.json').write_text(json.dumps(records,indent=2)+'\n')
print('done records',len(records),'asset refs',sum(len(r['downloads']) for r in records),flush=True)
