from research import *
p=ROOT/'requests';jobs=[]
for l in json.loads((p/'80980b86f6df4740a540.links.json').read_text())['links']:
 if re.search(r'Representative to Congress District 2 - Democratic.xlsx|CG2 Democratic RCV Summary Report.pdf|Representative to Congress District 2 \(D\) UOCAVA.xlsx',l['url']):jobs.append(l['url'])
jobs+=['https://legislature.maine.gov/legis/statutes/21-A/title21-Asec673.html','https://www.berwickmaine.org/government/town_clerk/elections.php']
for u in jobs:
 u=urllib.parse.quote(u,safe=':/?&=%#');m=fetch(u)
 if m.get('status')!=200 and urllib.parse.urlparse(u).netloc=='www.maine.gov':m=fetch(u.replace('https://www.maine.gov/','https://www3.maine.gov/'),publisher_url=u)
 print(m['id'],m.get('status'),m['entity_bytes_retained'],flush=True)
