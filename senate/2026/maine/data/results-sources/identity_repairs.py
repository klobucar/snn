from research import *
p=ROOT/'requests';rs=json.loads((ROOT/'municipal-route-discovery.json').read_text());rep={119:['https://newportme.org/townoffice'],163:['https://www.townofansonme.net/town-clerk']}
for r in rs:
 if r['rank'] in (119,122,163):
  # retain rejected attempts separately, including malicious/unrelated redirect without treating as official.
  if r['rank']==122:
   bad=[x for x in r['discovery_routes'] if 'pittsfield' in x['url']]
  else:bad=r['discovery_routes'][:1]
  r['rejected_discovery_routes']=r.get('rejected_discovery_routes',[])+bad;r['discovery_routes']=[x for x in r['discovery_routes'] if x not in bad]
  badids=[]
  for id in r['route_request_ids']:
   m=json.loads((p/f'{id}.json').read_text())
   if any(x['url']==m['request_url'] for x in bad):badids.append(id)
  r['rejected_request_ids']=r.get('rejected_request_ids',[])+badids;r['route_request_ids']=[id for id in r['route_request_ids'] if id not in badids]
  r['rejection_reason']={119:'Discovery directory links Newport to New Portland; wrong municipality.',122:'Discovery directory links Pittston to Pittsfield; wrong municipality.',163:'Old discovery route redirects to unrelated coli.ph; reject as official authority channel.'}[r['rank']]
 if r['rank'] in rep:
  for u in rep[r['rank']]:
   m=fetch(u);r['route_request_ids'].append(m['id']);r['discovery_routes'].append({'url':u,'route_type':'primary repair','discovery_label':'primary town clerk page','discovery_evidence':'web-repair-8.txt'})
(ROOT/'municipal-route-discovery.json').write_text(json.dumps(rs,indent=2)+'\n')
print('fixed priority identities119,122,163',flush=True)
