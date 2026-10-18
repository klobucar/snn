from research import *
p=ROOT/'requests'
jobs=[]
for fid in ['329b5f92851a4fdca8d1','d0518a36fbed38d82d5c','cc5fbb49c205820d20e1']:
 links=json.loads((p/f'{fid}.links.json').read_text())['links']
 for l in links:
  if re.search(r'General Election Candidates|Withdrawals and Replacement|Declared Write|Voting Place Report|Municipal Office Hours|Intent to Process|download this list|Absentee Voter Data File Layout',l['text'],re.I):
   u=l['url'];jobs.append((u,l['text']))
# Preserve publisher vs actual request host separately. Escape spaces in observed URL.
def go(job):
 u,label=job;u=urllib.parse.quote(u,safe=':/?&=%#')
 m=fetch(u)
 if m.get('status')!=200 and urllib.parse.urlparse(u).netloc=='www.maine.gov':
  m=fetch(u.replace('https://www.maine.gov/','https://www3.maine.gov/'),publisher_url=u)
 return {'label':label,'request_id':m['id'],'publisher_url':u,'status':m.get('status'),'size':m['entity_bytes_retained']}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:rows=list(ex.map(go,jobs))
(ROOT/'state-assets.json').write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:print(r)
