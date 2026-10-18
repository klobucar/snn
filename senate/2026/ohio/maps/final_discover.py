from fetch_maps import *
urls={
'census-state-vtd':'https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/tl_2020_39_vtd20.zip',
'mahoning-2025':'https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/Precincts_2025.zip',
'mahoning-2020':'https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/Precincts_2020.zip',
'mahoning-current':'https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/Voting_Precincts.zip',
'richland-history':'https://web.archive.org/web/20220124064019if_/https://www.boe.ohio.gov/richland/c/pdf/MapRCPrecincts.pdf',
'butler-public':'https://gismaps.bceo.org/server/rest/services/Public?f=pjson',
'butler-readonly':'https://gismaps.bceo.org/server/rest/services/ReadOnly?f=pjson',
'butler-taxmap':'https://gismaps.bceo.org/server/rest/services/TaxMap?f=pjson',
'medina-mapserver-proxy':'https://gm.medinaco.org/php/mapserver.php?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&REQUEST=GetCapabilities',
'medina-mapbook2':'https://gm.medinaco.org/php/getmapbook.php',
'summit-archive-cdx':'https://web.archive.org/cdx/search/cdx?url=www.boe.ohio.gov/summit/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*map.*&collapse=urlkey',
'geauga-mapserver':'https://gis.geauga.oh.gov/arcgis/rest/services?f=pjson',
'geauga-gis-old':'https://gis.co.geauga.oh.us/arcgis/rest/services?f=pjson',
'geauga-downloads':'https://auditor.geauga.oh.gov/gis/',
'columbiana-gis-current':'https://gis.columbianacountyohio.gov/',
'columbiana-data':'https://www.columbianacounty.org/columbiana-county-gis',
'erie-hub':'https://data-eriecounty-oh.opendata.arcgis.com/',
'portage-gis':'https://portagecounty-oh.gov/gis',
'fairfield-gis':'https://www.co.fairfield.oh.us/auditor/gis.html'}
def work(kv):
 k,u=kv;m,b=fetch('finaldiscovery/'+k,u,raw=k in ['census-state-vtd','mahoning-2025','mahoning-2020','mahoning-current','richland-history']);s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']=d if isinstance(d,list) else {a:d.get(a) for a in ['services','folders','layers']}
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip',u+' '+t,re.I)][-15:]
 print(k,json.dumps(s)[:3000],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'final-discovery.json').write_text(json.dumps(d,indent=2))
