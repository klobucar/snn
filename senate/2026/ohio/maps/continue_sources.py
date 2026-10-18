from fetch_maps import *
urls={
'census-vtd-directory':'https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/',
'wood-county-pdf':'https://boe.woodcountyohio.gov/DocumentCenter/View/241',
'ashtabula-pdf':'https://www.arcgis.com/sharing/rest/content/items/ec5157a03a054487bc64be2cc861e6cc/data',
'mahoning-shapes':'https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/Shape_Files/',
'mahoning-config':'https://gisapp.mahoningcountyoh.gov/mahgis/config.json',
'medina-wfs':'https://gm.medinaco.org/cgi-bin/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&REQUEST=GetCapabilities',
'medina-wms':'https://gm.medinaco.org/cgi-bin/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WMS&REQUEST=GetCapabilities',
'summit-fiscal-old':'https://summitmaps.summitoh.net/arcgis/rest/services/Fiscal_Mercator/MapServer?f=pjson',
'butler-bceo':'https://gismaps.bceo.org/server/rest/services?f=pjson',
'richland-cama':'https://www.richlandcountyoh.gov/departments/auditor/CamaData',
'richland-maparchive':'https://web.archive.org/cdx/search/cdx?url=www.boe.ohio.gov/richland/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*(map|Map).*&collapse=urlkey',
'geauga-recorderarchive':'https://web.archive.org/cdx/search/cdx?url=recorder.co.geauga.oh.us/*Voting*Precinct*&output=json&filter=statuscode:200&collapse=urlkey',
'boe-directory':'https://www.ohiosos.gov/elections/elections-officials/county-boards-of-elections-directory/'}
def work(kv):
 k,u=kv;m,b=fetch('continued/'+k,u,raw=k.endswith('-pdf'));s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']=d if isinstance(d,list) else {a:d.get(a) for a in ['services','folders','map','operationalLayers']}
  if isinstance(d,dict) and 'operationalLayers' in d:s['data']['operationalLayers']=[(l.get('title'),l.get('url')) for l in d['operationalLayers']]
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip|vtd',u+' '+t,re.I)][:12]
 print(k,json.dumps(s)[:3500],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'continued-discovery.json').write_text(json.dumps(d,indent=2))
