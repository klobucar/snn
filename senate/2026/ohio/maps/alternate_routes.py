from fetch_maps import *
urls={
'census-2020-vtd':'https://www2.census.gov/geo/tiger/TIGER2020/VTD/tl_2020_39_vtd20.zip',
'mahoning-ftp':'https://gisapp.mahoningcountyoh.gov/Public_FTP_Folder/',
'mahoning-mapservices':'https://gis.mahoningcountyoh.gov/565/Map-Services',
'mahoning-map':'https://gisapp.mahoningcountyoh.gov/mahgis/',
'butler-gis-site':'https://www.bceo.org/gismapping.html',
'butler-gis-new':'https://gis.bcohio.gov/',
'butler-maps-new':'https://maps.bcohio.gov/MapViewer/',
'wood-cities':'https://boe.woodcountyohio.gov/233/Cities',
'wood-townships':'https://boe.woodcountyohio.gov/234/Townships',
'geauga-wp':'https://recorder.co.geauga.oh.us/wp-json/wp/v2/search?search=Voting&per_page=20',
'geauga-media':'https://recorder.co.geauga.oh.us/wp-json/wp/v2/media?search=Voting&per_page=20',
'geauga-archive-cdx':'https://web.archive.org/cdx/search/cdx?url=www.boe.ohio.gov/geauga/c/upload/PrecinctPollingLocationMaps.pdf&output=json&filter=statuscode:200&collapse=timestamp:4',
'richland-archive-cdx':'https://web.archive.org/cdx/search/cdx?url=www.boe.ohio.gov/richland/c/upload/Info_MapRCPrecincts.pdf&output=json&filter=statuscode:200&collapse=timestamp:4',
'columbiana-arc-item':'https://www.arcgis.com/sharing/rest/content/items/0f7f99ebcedf421c9c60d540ef82e1ea?f=pjson',
'erie-arc-item':'https://www.arcgis.com/sharing/rest/content/items/514fc88ae5b148c185781a473f3bfb4d?f=pjson',
'ashtabula-pdf-item':'https://www.arcgis.com/sharing/rest/content/items/ec5157a03a054487bc64be2cc861e6cc?f=pjson',
'portage-arc-item':'https://www.arcgis.com/sharing/rest/content/items/f6700a1ad5634ba2a0dba73b9b956269?f=pjson',
'fairfield-arc-item':'https://www.arcgis.com/sharing/rest/content/items/c070274589c647efbfce812a5db6f205?f=pjson'}
def work(kv):
 k,u=kv;m,b=fetch('alternate/'+k,u,raw=u.endswith(('.pdf','.zip')));s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']={k:d.get(k) for k in ['title','owner','orgId','description','url','extent','created','modified']} if isinstance(d,dict) else d
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('precinct|map|gis|\.pdf|\.zip',u+' '+t,re.I)][-18:]
 print(k,json.dumps(s)[:3300],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'alternate-routes.json').write_text(json.dumps(d,indent=2))
