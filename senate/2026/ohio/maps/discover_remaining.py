from fetch_maps import *
urls={
'summit-services':'https://scgis.summitoh.net/hosted/rest/services?f=pjson',
'summit-theme':'https://summitmaps.summitoh.net/ThemeViewer/',
'medina-gm':'https://gm.medinaco.org/',
'medina-data':'https://gisdata.co.medina.oh.us/',
'medina-auditor':'https://auditor.medinacounty.gov/',
'montgomery-open':'https://www.mcohio.org/629/GIS-Data',
'montgomery-open2':'https://www.mcohio.org/departments/auditor/gis/gis_data.php',
'wayne-maps':'https://www.waynecountyoh.gov/precincts-voter-ward-precinct-maps/',
'allen':'https://gis.allencountyohio.com/GIS/Downloads.html',
'ashtabula-app':'https://www.arcgis.com/sharing/rest/content/items/3686a631916141b8a01329ef004f0104/data?f=pjson',
'ashtabula-webmap':'https://www.arcgis.com/sharing/rest/content/items/63ee6a886e6e4d5a8045821acdc250cd/data?f=pjson',
'erie-layer':'https://services3.arcgis.com/r00vmm8eIzAwdHlO/arcgis/rest/services/EC_Precincts/FeatureServer?f=pjson',
'erie-boe':'https://www.boe.ohio.gov/erie/precinct-and-polling-location-info/',
'erie-gis':'https://www.eriecounty.oh.gov/GIS.aspx',
'geauga-recorder':'https://recorder.geauga.oh.gov/document/voting-precincts/',
'geauga-legacy':'https://recorder.co.geauga.oh.us/wp-content/uploads/2020/07/Voting-Precincts.pdf',
'geauga-gis':'https://gis.geauga.oh.gov/',
'richland-gis':'https://www.richlandcountyoh.gov/GIS',
'richland-maps':'https://richlandmaps.com/content/maps',
'miami-ftp':'https://ftp.miamicountyohio.gov/GIS/Board%20Of%20Elections-Precinct%20Maps/',
'trumbull-boe':'https://www.boe.co.trumbull.oh.us/',
'trumbull-gis':'https://auditor.co.trumbull.oh.us/auditor/GIS',
'butler-gis':'https://maps.bcohio.gov/',
'butler-legacy':'https://elections.bcohio.gov/Maps/index.cfm',
'mahoning-sitemap':'https://vote.mahoningcountyoh.gov/sitemap',
'muskingum-maps':'https://www.muskingumcountyoh.gov/Muskingum-County-Maps/',
'columbiana-gis':'https://www.columbianacountygis.org/',
'tuscarawas-map':'https://www.arcgis.com/sharing/rest/content/items/26d1b374f3074678b1a5855e0f9bbdfa/data?f=pjson',
'wood-county-map':'https://boe.woodcountyohio.gov/boe/PDF_Files/Precinct_Maps/county%20map.pdf'}
def work(kv):
 k,u=kv;m,b=fetch('remaining/'+k,u,raw=u.endswith('.pdf'));s={'status':m['status'],'url':u}
 try:
  d=json.loads(b);s['map']=d.get('map');s['layers']=d.get('layers',d.get('operationalLayers'));s['services']=d.get('services');s['folders']=d.get('folders')
 except:
  s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip',u+' '+t,re.I)][-45:]
 print(k,json.dumps(s)[:5500],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'remaining-discovery.json').write_text(json.dumps(d,indent=2))
