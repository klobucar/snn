#!/usr/bin/env python3
"""Follow advertised county links; retain parent evidence and actual PDF originals."""
from acquire import *
from county_routes import slug
import concurrent.futures

FOLLOW={
'Tarrant':['https://www.tarrantcountytx.gov/en/elections/interactive-maps/voting-precinct-maps.html'],
'Bell':['https://www.bellcountytx.com/departments/elections/precinct_maps.php'],
'Kaufman':['https://www.kaufmancounty.net/DocumentCenter/Index/378'],
'Grayson':['https://www.co.grayson.tx.us/page/elec.maps'],
'Nueces':['https://www.nuecesco.com/county-services/county-clerk/elections-department/election-gis-maps/-folder-192'],
'Hidalgo':['https://www.hidalgocounty.us/DocumentCenter/View/55742'],
'Lubbock':['https://www.lubbockcounty.gov/eGov/apps/document/center.egov?id=2828&view=item','https://assets01.aws.connect.clarityelections.com/Assets/Connect/RootPublish/lubbock-tx.connect.clarityelections.com/Maps2022/VoterPrecincts2022.pdf'],
'Cameron':['https://cameroncountytx.gov/elections/wp-content/uploads/2018/03/PRECINCT-53-LS.pdf'],
'Brazos':['https://www.brazoscountytx.gov/DocumentCenter/View/5003/voter-precincts-map-10232024-optimized'],
}

def run_follow(t):
 c,urls=t; records=[]
 for i,u in enumerate(urls):
  d=fetch('follow-'+slug(c)+f'-{i+1}',u,parent='Search-discovered official county publication; see county discovery routes')
  links=[]
  if 'stored_parts' in d and not original(d).startswith(b'%PDF'):
   soup=BeautifulSoup(original(d),'html.parser')
   for a in soup.select('a[href],iframe[src],img[src]'):
    links.append(dict(tag=a.name,label=a.get_text(' ',strip=True) or a.get('alt',''),url=urljoin(d.get('final_url',u),a.get('href') or a.get('src'))))
  records.append(dict(source_id=d['id'],url=u,status=d.get('status'),links=links))
 save_json(ROOT/'discovery'/f'{slug(c)}-follow.json',dict(county=c,routes=records))

def pdfs():
 jobs=[]
 for p in sorted((ROOT/'discovery').glob('*.json')):
  d=json.loads(p.read_text());c=d['county']; s=slug(c)
  chosen=[]
  for r in d['routes']:
   for l in r.get('links',[]):
    label=l['label'];u=l['url']
    if "document.location=" in u:
     m=re.search(r"document.location='([^']+)'",u)
     if m:u=urljoin(r['url'],m[1])
    # Countywide precinct maps, complete mapbooks, dated notices/orders; avoid district/commissioner maps.
    accept=(re.search(r'(all voting precincts|Voter Precincts.*PDF|Voting Precincts PDF|Election Precincts Map|all voting precincts|Voting District - Precinct Map|Precinct Boundary Lines Map|Election/Voting Precincts|ElectionVoting-Precincts|Complete updated county map|Voting Precincts - County|Signed Order to Approve|Notice of Boundary Change|Certified County Election Precinct Order)',label,re.I) or
      (c=='Montgomery' and re.search('ED_11x17|AllPrecinct',u,re.I)) or
      (c=='Harris' and re.search(r'shapefile|Harris County Election Precincts',label,re.I)) or
      (c=='Tarrant' and re.search(r'Precincts_Basemap\.pdf',u,re.I)))
    if accept and not re.search(r'#|\.jpg|\.png|experience\.arcgis',u,re.I) and u.startswith('http'):
     chosen.append(dict(url=u,label=label,parent=r['url']))
  for i,x in enumerate({x['url']:x for x in chosen}.values()): jobs.append((f'local-{s}-{i+1}',x['url'],x['parent'],c,x['label']))
 # Download unique exact URLs once, even if indexed in several county routes.
 seen=set();unique=[]
 for x in jobs:
  if x[1] not in seen:seen.add(x[1]);unique.append(x)
 def work(t):
  k,u,p,c,l=t;d=fetch(k,u,p);d.update(county=c,advertised_title=l);save_json(ROOT/'sources'/f'{k}.json',d);print(k,d.get('status'),d.get('original_bytes'),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(work,unique))

if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(run_follow,FOLLOW.items()))
 pdfs()
