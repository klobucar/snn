from acquire import *
more={
'erie':('https://services3.arcgis.com/r00vmm8eIzAwdHlO/arcgis/rest/services/EC_Precincts/FeatureServer/0','Erie County Auditor GIS / Erie Regional Planning Commission; official portal linked by Auditor','catalog created 2016; current publication with effective date unestablished'),
'tuscarawas':('https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer/0','Tuscarawas County GIS precinct webmap','current-published; effective date unestablished')}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(lambda kv:service(*kv),more.items()))
urls={
'medina-wfs-cap':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetCapabilities',
'medina-wms-cap':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WMS&VERSION=1.1.1&REQUEST=GetCapabilities',
'butler-taxmap-current':'https://gismaps.bceo.org/server/rest/services/Public/TaxmapWebmapCurrent/MapServer?f=pjson',
'butler-basemap':'https://gismaps.bceo.org/server/rest/services/ReadOnly/Basemap/MapServer?f=pjson',
'butler-auditor':'https://www.butlercountyauditor.org/Home/GIS-Maps',
'mahoning-webmap':'https://www.arcgis.com/sharing/rest/content/items/ea9d36192e4f4170ad0d37edd6510e4c/data?f=pjson',
'columbiana-hub':'https://columbiana-county-gis-data-columauditor.hub.arcgis.com/pages/downloads',
'ashtabula-hub':'https://gis-ashtabulacounty.opendata.arcgis.com/',
'erie-auditor':'https://auditor.eriecounty.oh.gov/gis-and-maps',
'erie-org':'https://www.arcgis.com/sharing/rest/portals/r00vmm8eIzAwdHlO?f=pjson',
'ashtabula-org':'https://www.arcgis.com/sharing/rest/portals/LbREO35fKGJZptlq?f=pjson',
'portage-user':'https://www.arcgis.com/sharing/rest/community/users/TommyW3?f=pjson',
'fairfield-user':'https://www.arcgis.com/sharing/rest/community/users/CurtTruax?f=pjson'}
def work(kv):
 k,u=kv;m,b=fetch('moreacquire/'+k,u)
 try:
  d=json.loads(b);print(k,m['status'],json.dumps({a:d.get(a) for a in ['name','username','fullName','description','orgId','urlKey','url']})[:500],[(x.get('id'),x.get('name'),x.get('title'),x.get('url')) for x in d.get('layers',d.get('operationalLayers',[])) if re.search('precinct|vot',str(x),re.I)],flush=True)
 except:print(k,m['status'],len(b),b[:140],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(work,urls.items()))
