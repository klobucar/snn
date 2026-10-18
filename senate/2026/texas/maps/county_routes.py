#!/usr/bin/env python3
"""Retain exact official routes and their advertised links. No guessed downloads."""
from acquire import *
import csv, concurrent.futures

ROUTES = {
'Harris':['https://cao.harriscountytx.gov/Commissioner-Precinct-Redistricting/Adopted-Plan-for-New-Election-Precincts'],
'Dallas':['https://www.dallascountyvotes.org/'],
'Tarrant':['https://www.tarrantcountytx.gov/en/elections/interactive-maps.html'],
'Bexar':['https://elections.bexar.gov/173/Voter-Precinct-Maps','https://home.bexar.org/electionsResources/votermaps.html'],
'Travis':['https://tax-office.traviscountytx.gov/voters','https://www.traviscountytx.gov/intergovernmental-relations/redistricting'],
'Collin':['https://www.collincountytx.gov/Government/Commissioners-Court/precincts'],
'Denton':['https://www.dentoncounty.gov/1147/Geographic-Information-Systems-GIS','https://www.votedenton.gov/'],
'Fort Bend':['https://www.fortbendcountytx.gov/government/departments/elections-voter-registration','https://www.fortbendcountytx.gov/government/departments/elections-voter-registration/maps/voter-precinct-maps'],
'Montgomery':['https://elections.mctx.org/Maps.asp'],
'Williamson':['https://www.wilcotx.gov/190/Maps'],
'El Paso':['https://epcountyvotestx.gov/maps/el-paso-county-map'],
'Hidalgo':['https://www.hidalgocounty.us/'],
'Brazoria':['https://www.brazoriacountyclerktx.gov/departments/elections/precinct-maps'],
'Galveston':['https://www.galvestonvotes.org/'],
'Bell':['https://www.bellcountytx.com/departments/elections/'],
'Hays':['https://www.hayscountytx.gov/elections'],
'Lubbock':['https://www.votelubbock.org/'],
'Nueces':['https://www.nuecesco.com/quick-links/maps/election-gis-maps'],
'Cameron':['https://www.cameroncountytx.gov/elections/index.php/maps/'],
'Comal':['https://www.comalcounty.gov/880/Precinct-Maps'],
'Smith':['https://www.smith-county.com/QuickLinks.aspx'],
'McLennan':['https://www.mclennan.gov/337/Elections','https://www.mclennan.gov/370/Precinct-Street-Guide'],
'Ellis':['https://elliscountytx.gov/629/Upcoming-Elections'],
'Brazos':['https://elections.brazoscountytx.gov/'],
'Parker':['https://www.parkercountytx.gov/521/Maps'],
'Jefferson':['https://www.jeffersonelections.com/'],
'Guadalupe':['https://www.guadalupetx.gov/page/elections.precinct_maps','https://www.guadalupetx.gov/page/elections.home'],
'Johnson':['https://www.johnsoncountytx.org/departments/elections-office/precinct-maps'],
'Kaufman':['https://www.kaufmancounty.net/445/RESOURCES'],
'Randall':['https://www.randallcounty.gov/166/Election-Administration'],
'Grayson':['https://www.co.grayson.tx.us/page/elec.home'],
'Webb':['https://www.webbcountytx.gov/580/Map-Book','https://www.webbcountytx.gov/'],
'Rockwall':['https://www.rockwallcountytexas.com/889/County-Maps','https://www.rockwallvotes.com/'],
'Midland':['https://midlandtexas.gov/1196/GIS-Mapping'],
}
def slug(s): return s.lower().replace(' ','-')
def discover(t):
    county, urls=t; out=[]
    for i,u in enumerate(urls):
        d=fetch('route-'+slug(county)+f'-{i+1}',u)
        links=[]
        if 'stored_parts' in d:
            soup=BeautifulSoup(original(d),'html.parser')
            for a in soup.select('[href],iframe[src],option[value],button[onclick],img[src]'):
                raw=a.get('href') or a.get('src') or a.get('value') or a.get('onclick')
                label=a.get_text(' ',strip=True) or a.get('alt','')
                if not raw:continue
                links.append(dict(tag=a.name,label=label,url=urljoin(d.get('final_url',u),raw)))
        out.append(dict(source_id=d['id'],url=u,status=d.get('status'),error=d.get('error'),links=links))
    save_json(ROOT/'discovery'/f'{slug(county)}.json',dict(county=county,routes=out))
    print(county,[(r['status'],len(r['links'])) for r in out],flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(discover,ROUTES.items()))
