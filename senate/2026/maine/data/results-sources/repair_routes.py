from research import *
# Exact routes observed in retained primary search observations / official announcements.
repairs={
1:['https://port.portlandmaine.gov/elections-voting','https://www.portlandmaine.gov/168/City-Clerk?contentId=ed3f621c-061c-4791-a7b9-e6ad2818d9fe'],
11:['https://www.gorhammaine.gov/sites/g/files/vyhlif4456/f/uploads/election_results_11-05-2024.pdf'],
14:['https://www.augustamaine.gov/how_do_i/online_services/index.php?section=elections'],
16:['https://www.falmouthme.org/339/Election-Information'],
23:['https://kitteryme.gov/359/Voting-Elections'],
24:['https://www.standishme.gov/m/newsflash/home/detail/22'],
28:['https://www.townofcumberlandmaine.gov/251/Election-Results'],
29:['https://www.graymaine.org/1359/Elections'],
32:['https://www.brewermaine.gov/190/Elections'],
33:['https://www.cityofbathmaine.gov/Departments/City-Clerk?lang_update=639262165571536618'],
36:['https://www.ellsworthmaine.gov/wp-content/uploads/2025/11/11-4-2025-Unofficial-Results-Municipal-and-State-Referendum-Election-1.pdf'],
41:['https://www.berwickmaine.org/government/town_clerk/elections.php'],
50:['https://www.rocklandmaine.gov/173/Voting-Elections'],
57:['https://www.polandtownoffice.org/home/files/town-meeting-election-results'],
59:['https://www.lebanon-me.org/town-clerk-tax-collector'],
60:['https://www.fairfield-me.gov/DocumentCenter/View/762/11-4-25-unofficial-results?bidId='],
62:['https://www.raymondmaine.gov/'],
64:['https://www.northyarmouth.org/1694/Polling-Place'],
65:['https://www.gardinermaine.gov/Resident/Voting-Elections'],
66:['https://www.hollismaine.org/1310/Election-Results'],
69:['https://sabattus.org/annual-town-meetings/'],
71:['https://www.parismaine.org/pages/town-clerk'],
86:['https://www.townofnaples.org/index.asp?SEC=6496F821-F913-4C22-A71B-FA211038F86A'],
92:['https://www.dover-foxcroft.org/171/Documents'],
100:['https://www.belgrademaine.gov/contact'],
104:['https://www.bristolmaine.org/252/Town-Clerk'],
111:['https://www.pittsfieldmaine.gov/media/771'],
115:['https://www.norridgewock.gov/1384/October-21-2026-Special-Town-Meeting'],
122:['https://www.pittstonmaine.gov/pages/town-services'],
124:['https://www.readfieldmaine.gov/home/news/town-readfield-election-results','https://www.readfieldmaine.gov/votingelectionstown-mtg/pages/past-town-meetings-and-elections'],
134:['https://www.manchesterme.org/town-clerk'],
146:['https://www.damariscottame.com/243/Elections'],
156:['https://www.mtdesert.org/1376/Elections-Voting'],
162:['https://www.townofsebago.org/sites/g/files/vyhlif3796/f/uploads/municipal_election_results_6_11_24.pdf']}
p=ROOT/'requests';index=json.loads((ROOT/'municipal-route-discovery.json').read_text());jobs=list(dict.fromkeys(u for us in repairs.values() for u in us))
def go(u):
 id=digest(u.encode())[:20];f=p/f'{id}.json';return u,json.loads(f.read_text()) if f.exists() else fetch(u)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:got=dict(ex.map(go,jobs))
for r in index:
 if r['rank'] not in repairs:continue
 if r['rank'] in (41,60):
  r['rejected_discovery_routes']=r['discovery_routes'];r['rejected_request_ids']=r['route_request_ids'];r['discovery_routes']=[];r['route_request_ids']=[];r['rejection_reason']='Discovery directory links Berwick to North Berwick / Fairfield to Fort Fairfield; wrong jurisdiction, never use as authority.'
 for u in repairs[r['rank']]:
  m=got[u];r['discovery_routes'].append({'url':u,'discovery_label':'repair from observed primary source route','discovery_evidence':'web-repair-*.txt or retained primary announcement','route_type':'primary repair'})
  if m['id'] not in r['route_request_ids']:r['route_request_ids'].append(m['id'])
(ROOT/'municipal-route-discovery.json').write_text(json.dumps(index,indent=2)+'\n')
(ROOT/'route-repair-tests.json').write_text(json.dumps([{'rank':k,'url':u,'request_id':got[u]['id'],'status':got[u].get('status')} for k,us in repairs.items() for u in us],indent=2)+'\n')
print('repair statuses',[(k,[(got[u].get('status'),got[u]['id']) for u in us]) for k,us in repairs.items()],flush=True)
