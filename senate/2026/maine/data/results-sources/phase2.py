from research import *
p=ROOT/'requests';jobs=[]
for l in json.loads((p/'329b5f92851a4fdca8d1.links.json').read_text())['links']:
 if re.search('Voting Place Report|Municipal Office Hours',l['url']) and l['url'].endswith('.xlsx'):jobs.append(l['url'])
jobs += ['https://www.maine.gov/local/index.html','https://www3.maine.gov/sos/elections-voting/upcoming/ranked-choice-voting-tabs','https://www3.maine.gov/sos/elections-voting/absentee-voting','https://www3.maine.gov/sos/elections-voting/ranked-choice-voting-frequently-asked-questions','https://www3.maine.gov/sos/elections-voting/military-and-overseas-voters','https://www.mainelegislature.org/legis/statutes/search.htm']
for sec in ['1','621','626','711','722','722-A','723-A','724','725','737-A','753-A','753-B','755','756','759','760-B']:
 jobs.append(f'https://legislature.maine.gov/legis/statutes/21-A/title21-Asec{sec}.html')
def go(u):
 u=urllib.parse.quote(u,safe=':/?&=%#');m=fetch(u)
 if m.get('status')!=200 and urllib.parse.urlparse(u).netloc=='www.maine.gov':m=fetch(u.replace('https://www.maine.gov/','https://www3.maine.gov/'),publisher_url=u)
 return {'url':u,'id':m['id'],'status':m.get('status'),'bytes':m['entity_bytes_retained']}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:r=list(ex.map(go,jobs))
(ROOT/'phase2.json').write_text(json.dumps(r,indent=2)+'\n')
for x in r:print(x)
