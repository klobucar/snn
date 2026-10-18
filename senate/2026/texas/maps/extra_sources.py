#!/usr/bin/env python3
"""Explicit second-depth choices from retained county pages/search evidence."""
from acquire import *
from county_routes import slug
import concurrent.futures
JOBS=[
 ('jefferson-order','Jefferson','https://jeffersoncountytx.gov/Documents/Notices/Signed_Order_with_updated_maps.pdf','https://jeffersoncountytx.gov/','Search-discovered final order with updated maps; inspect effective scope in original'),
 ('jefferson-map-page','Jefferson','https://jeffersoncountytx.gov/voter/prct_maps.htm','https://jeffcotax.com/news-release-2/','Primary county voter precinct map route advertised by county tax office'),
 ('denton-hub','Denton','https://data-dentoncounty.hub.arcgis.com/','https://www.dentoncounty.gov/1147/Geographic-Information-Systems-GIS','Official linked data hub; JavaScript catalog discovery'),
 ('smith-100-portal','Smith','https://portal.laserfiche.com/Portal/DocView.aspx?id=2090&repo=r-927d42fb','https://www.smith-county.com/QuickLinks.aspx','2026 Election Precinct100 vendor document viewer; inspect actual download path'),
 ('galveston-city-gis','Galveston','https://gis.galvestontx.gov/GISdata/','https://www.galvestontx.gov/501/Voting-Districts','City GIS download catalog; city coverage not presumed countywide'),
 ('hays-2026-map','Hays','https://www.hayscountytx.gov/DocumentCenter/View/1666/2026-Election-Precincts-High-Resolution-PDF','https://www.hayscountytx.gov/256/Precinct-Data-Maps','2026 Election Precincts High Resolution PDF'),
 ('harris-zip-https','Harris','https://cao.harriscountytx.gov/Portals/20/Documents/Adopted-Precincts/HarrisCo_AdoptedPrecincts_20211220.zip','https://cao.harriscountytx.gov/Commissioner-Precinct-Redistricting/Adopted-Plan-for-New-Election-Precincts','HTTPS repair of advertised HTTP shapefile; 2021 adopted precincts'),
 ('travis-map','Travis','https://www.traviscountytx.gov/images/intergovernmental_relations/Doc/G1_Election_Precincts_Final_Map.pdf','https://www.traviscountytx.gov/intergovernmental-relations/redistricting','New Election Precinct Map; adopted December 14 2021'),
 ('travis-plan','Travis','https://www.traviscountytx.gov/images/intergovernmental_relations/Doc/Agenda_Back_Up_20211214_Memo.pdf','https://www.traviscountytx.gov/intergovernmental-relations/redistricting','Election Precinct Boundaries Proposed Plan for 2022'),
 ('nueces-map','Nueces','https://www.nuecesco.com/home/showpublisheddocument/31462/638544757609070000','https://www.nuecesco.com/county-services/county-clerk/elections-department/election-gis-maps/-folder-192','Nueces County Voting Precincts 1-129'),
 ('grayson-vtd-map','Grayson','https://www.co.grayson.tx.us/upload/page/0189/docs/maps_VTD_2026_Countywide.pdf','https://www.co.grayson.tx.us/page/elec.maps','VTD; countywide map says Voter Tabulation Districts; not silently treated as native precincts'),
 ('grayson-101','Grayson','https://www.co.grayson.tx.us/upload/page/0189/docs/VP_101.pdf','https://www.co.grayson.tx.us/page/elec.maps','Voter Precinct 101; partial county PDF, statewide TLC supplies countywide reference'),
 ('rockwall-voting-boxes','Rockwall','https://www.rockwallcountytexas.com/DocumentCenter/View/14413','https://www.rockwallcountytexas.com/889/County-Maps','Updated Voting Boxes; inspect actual title and scope'),
 ('hays-map-page','Hays','https://www.hayscountytx.gov/256/Precinct-Data-Maps','https://www.hayscountytx.gov/elections','Precinct Data & Maps'),
 ('dallas-alternate','Dallas','https://www.dallascounty.org/departments/elections/','https://www.dallascountyvotes.org/','Official county alternate after vote site HTTP202 challenge'),
 ('galveston-alternate','Galveston','https://www.galvestoncountytx.gov/our-county/county-clerk/elections','https://www.galvestonvotes.org/','Official county alternate after vote site HTTP202 challenge'),
 ('jefferson-alternate','Jefferson','https://jeffersoncountytx.gov/','https://www.jeffersonelections.com/','Official county alternate after vote site HTTP202 challenge'),
 ('cameron-alternate','Cameron','https://www.cameroncountytx.gov/elections/','https://www.cameroncountytx.gov/elections/index.php/maps/','Official elections root repair after maps page403'),
 ('bell-adopted-mapbook','Bell','https://cms3.revize.com/revize/bellcountytx/departments/elections/uploads/BellCO_EP_DraftPlanC_DDP_JPB_Roads_Mapbook_Adopted_Dec6_2021.pdf','https://www.bellcountytx.com/departments/elections/','Search-discovered official vendor mapbook; Adopted December6 2021'),
]
def run(t):
 key,c,u,p,title=t;d=fetch('extra-'+key,u,p);d.update(county=c,advertised_title=title);save_json(ROOT/'sources'/f'extra-{key}.json',d)
 if 'stored_parts' in d and not original(d).startswith((b'%PDF',b'PK')):
  soup=BeautifulSoup(original(d),'html.parser');ll=[dict(tag=a.name,label=a.get_text(' ',strip=True) or a.get('alt',''),url=urljoin(d.get('final_url',u),a.get('href') or a.get('src'))) for a in soup.select('a[href],iframe[src],img[src]')]
  save_json(ROOT/'discovery'/f'extra-{key}.json',dict(county=c,routes=[dict(source_id=d['id'],url=u,status=d.get('status'),links=ll)]))
 print(key,d.get('status'),d.get('original_bytes'),flush=True)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(run,JOBS))
