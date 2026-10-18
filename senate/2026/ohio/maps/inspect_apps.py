from fetch_maps import *
urls={
'montgomery-services':'https://gis.mcohio.org/server/rest/services?f=pjson',
'summit-juris':'https://scgis.summitoh.net/hosted/rest/services/fiscal/Jurisdictions/MapServer?f=pjson',
'medina-mapbook':'https://gm.medinaco.org/php/getmapbook.php',
'butler-oldgis':'https://maps.butlercountyohio.org/',
'butler-oldservices':'https://maps.butlercountyohio.org/arcgis/rest/services?f=pjson',
'mahoning-services':'https://gis.mahoningcountyoh.gov/server/rest/services?f=pjson',
'mahoning-auditor':'https://auditor.mahoningcountyoh.gov/',
'columbiana-home':'https://columbiana.boe.ohio.gov/',
'ashtabula-gis':'https://www.ashtabulacounty.us/228/GIS',
'erie-gis2':'https://www.eriecounty.oh.gov/GISDepartment.aspx',
'richland-archive':'https://archive.org/wayback/available?url=https%3A%2F%2Fwww.boe.ohio.gov%2Frichland%2Fc%2Fupload%2FInfo_MapRCPrecincts.pdf&timestamp=20261001',
'summit-archive':'https://archive.org/wayback/available?url=https%3A%2F%2Fwww.boe.ohio.gov%2Fsummit%2Fprecinct-and-polling-location-info%2Fmaps%2F&timestamp=20261001',
'geauga-archive':'https://archive.org/wayback/available?url=https%3A%2F%2Fwww.boe.ohio.gov%2Fgeauga%2Fc%2Fupload%2FPrecinctPollingLocationMaps.pdf&timestamp=20261001',
'geauga-archiveold':'https://archive.org/wayback/available?url=https%3A%2F%2Frecorder.co.geauga.oh.us%2Fwp-content%2Fuploads%2Fsites%2F21%2F2021%2F06%2FVoting-Precincts.pdf&timestamp=20261001'}
def work(kv):
 k,u=kv;m,b=fetch('apps/'+k,u);s={'status':m['status'],'url':u,'bytes':len(b)}
 try:
  d=json.loads(b);s['layers']=[(x.get('id'),x.get('name')) for x in d.get('layers',[])];s['services']=d.get('services');s['folders']=d.get('folders');s['archives']=d.get('archived_snapshots')
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip',u+' '+t,re.I)][-20:]
 print(k,json.dumps(s)[:4200],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'app-discovery.json').write_text(json.dumps(d,indent=2))
