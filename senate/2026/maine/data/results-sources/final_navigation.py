from research import *
from curl_repair import curl_fetch
p=ROOT/'requests';ind=json.loads((ROOT/'municipal-route-discovery.json').read_text())
for r in ind:
 if r['rank']==1:r['route_request_ids'] += ['450018e7c1ea2e236009-curl','dec6f58dc2ad1bea5f13-curl']
 if r['rank']==14:r['route_request_ids'].append('b003b346eef2d89950b7-curl')
(ROOT/'municipal-route-discovery.json').write_text(json.dumps(ind,indent=2)+'\n')
# Primary observed Portland result link and its actually linked, complete public CMS bundle.
for u in ['https://www.portlandmaine.gov/past-election-results','https://cdn-live.evolve.civicplus.io/build/assets/index-CiOfClup.js']:
 m=curl_fetch(u);print(m['id'],m.get('status'),m['entity_bytes_retained'],flush=True)
