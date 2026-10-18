from fetch_maps import *
urls={
'montgomery-download':'https://go.mcohio.org/embed/auditor/downloads/gis_downloads.cfm',
'montgomery-zip':'https://go.mcohio.org/embed/auditor/downloads/Shape_files/SHAPEFILE_BOARD_OF_ELECTIONS.zip',
'summit-admin':'https://scgis.summitoh.net/hosted/rest/services/Admin_and_Planning?f=pjson',
'summit-fiscal':'https://scgis.summitoh.net/hosted/rest/services/fiscal?f=pjson',
'summit-app-js':'https://summitmaps.summitoh.net/ThemeViewer/js/app.js',
'summit-new':'https://summitcountyboe.gov/',
'fairfield-new':'https://fairfieldcountyohioelections.gov/',
'erie-new':'https://eriecountyohioboe.gov/',
'medina-config':'https://gm.medinaco.org/geomoose/config.js',
'medina-auditor-data':'https://engineer.medinaco.org/gisdata/auditor/',
'medina-planning-data':'https://engineer.medinaco.org/gisdata/planning/',
'wood-maps':'https://boe.woodcountyohio.gov/232/Maps',
'columbiana-layer':'https://services8.arcgis.com/234WKrCI77bh5yOY/arcgis/rest/services/Columbiana_GIS_Map/FeatureServer?f=pjson',
'ashtabula-districts':'https://gis2.ashtabulacounty.us/arcgis/rest/services/Districts_Voting/MapServer?f=pjson',
'ashtabula-newmap':'https://www.arcgis.com/sharing/rest/content/items/5c26d068afb545a2996446e276f152c0/data?f=pjson',
'tuscarawas-layer':'https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer?f=pjson',
'butler-officialgis':'https://www.butlercountyohio.org/gis/',
'butler-server':'https://maps.bcohio.gov/arcgis/rest/services?f=pjson',
'mahoning-gis':'https://gis.mahoningcountyoh.gov/arcgis/rest/services?f=pjson',
'mahoning-gisweb':'https://gis.mahoningcountyoh.gov/',
'richland-new':'https://www.richlandcountyoh.gov/',
'richland-boepdf':'https://www.boe.ohio.gov/richland/c/upload/Info_MapRCPrecincts.pdf'}
def work(kv):
 k,u=kv;m,b=fetch('routes/'+k,u,raw=u.endswith(('.pdf','.zip')));s={'status':m['status'],'url':u,'bytes':len(b)}
 try:
  d=json.loads(b);s['layers']=[(x.get('id'),x.get('name'),x.get('title'),x.get('url')) for x in d.get('layers',d.get('operationalLayers',[]))];s['services']=d.get('services');s['folders']=d.get('folders')
 except:
  s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip',u+' '+t,re.I)][-45:]
 print(k,json.dumps(s)[:4500],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'primary-routes.json').write_text(json.dumps(d,indent=2))
