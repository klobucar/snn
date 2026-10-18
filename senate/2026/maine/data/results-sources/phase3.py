from research import *
p=ROOT/'requests';jobs=[]
# URLs are actual pagination values advertised on the directory, traversed to its last page.
for i in range(34):jobs.append(f'https://www3.maine.gov/sos/elections-voting/find-a-municipal-clerk-or-registrar?page={i}')
# County routes are actual JS URLs on official portal, not county reporting substitutes.
m=json.loads((p/'ae6d2465181b36a562b0.json').read_text());body=gzip.decompress((ROOT/m['body_path']).read_bytes()).decode()
for u in re.findall(r"url: '([^']+)'",body):jobs.append(urllib.parse.urljoin(m['final_url'],u))
for fid in ['adea5ffdf064763aeb8a']:
 for l in json.loads((p/f'{fid}.links.json').read_text())['links']:
  if re.search('U.S. Senate|Rule Adopted|Rules Establishing|Uniformed Service and Overseas',l['text']):jobs.append(l['url'])
def go(u):
 u=urllib.parse.quote(u,safe=':/?&=%#');m=fetch(u)
 if m.get('status')!=200 and urllib.parse.urlparse(u).netloc=='www.maine.gov':m=fetch(u.replace('https://www.maine.gov/','https://www3.maine.gov/'),publisher_url=u)
 return {'url':u,'id':m['id'],'status':m.get('status'),'bytes':m['entity_bytes_retained']}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(go,dict.fromkeys(jobs)))
(ROOT/'phase3.json').write_text(json.dumps(r,indent=2)+'\n')
print('requests',len(r),'statuses', {str(s):sum(x['status']==s for x in r) for s in set(x['status'] for x in r)})
