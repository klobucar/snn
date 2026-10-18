from research import *
p=ROOT/'requests'
jobs=['https://www3.maine.gov/REVENUE/forms/property/pubs/municlisting.pdf','https://legislature.maine.gov/legis/statutes/21-A/title21-Asec756-A.html','https://legislature.maine.gov/legis/statutes/21-A/title21-Asec631-A.html']
for u in jobs:
 m=fetch(u);print(m['id'],m.get('status'),m['entity_bytes_retained'])
for l in json.loads((p/'cc5fbb49c205820d20e1.links.json').read_text())['links']:
 if 'AB Voter File' in l['url']:
  u=urllib.parse.quote(l['url'],safe=':/?&=%#');m=fetch(u,limit=65536,headers={'Range':'bytes=0-65535'})
  if m.get('status')!=200 and m.get('status')!=206:m=fetch(u.replace('www.maine.gov','www3.maine.gov'),limit=65536,publisher_url=u,headers={'Range':'bytes=0-65535'})
  print('absentee sample',m['id'],m.get('status'),m['entity_bytes_retained'],m['complete'])
