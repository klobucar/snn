from fetch_maps import *
urls={
'medina-features':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=precincp',
'columbiana-boe-app':'https://www.arcgis.com/sharing/rest/content/items/88daba67d9a9419ca0b94cf457c9e2d0/data?f=pjson',
'butler-archive':'https://web.archive.org/cdx/search/cdx?url=elections.bcohio.us/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*[Mm]ap.*&collapse=urlkey',
'butler-catalogextent':'https://www.arcgis.com/sharing/rest/search?'+urllib.parse.urlencode({'q':'(precinct OR precincts OR voting)','bbox':'-84.9,39.3,-84.3,39.6','f':'json','num':100}),
'summit-archive-old':'https://web.archive.org/cdx/search/cdx?url=www.summitcountyboe.com/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*[Mm]ap.*&collapse=urlkey',
'summit-archive-old2':'https://web.archive.org/cdx/search/cdx?url=www.summitcountyboe.gov/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&collapse=urlkey',
'geauga-recorder-cdx2':'https://web.archive.org/cdx/search/cdx?url=recorder.co.geauga.oh.us/*&output=json&filter=statuscode:200&filter=urlkey:.*voting.*&collapse=urlkey',
'geauga-gisweb':'https://www.geaugarealink.co.geauga.oh.us/real/index.html',
'geauga-boe-old':'https://web.archive.org/cdx/search/cdx?url=www.boe.co.geauga.oh.us/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*[Mm]ap.*&collapse=urlkey',
'trumbull-public':'https://webgis.co.trumbull.oh.us/gisserver/rest/services/Maps?f=pjson',
'butler-app-data':'https://www.arcgis.com/sharing/rest/content/items/1a0204fe51364d4b82c6ceb2c66c8969/data?f=pjson'}
def work(kv):
 k,u=kv;m,b=fetch('resolve/'+k,u);s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']=d if isinstance(d,list) else {a:d.get(a) for a in ['services','folders','map','webmap']}
  if 'results' in d:s['results']=[(r['id'],r['title'],r['owner'],r.get('url')) for r in d['results']]
 except:s['prefix']=b[:150].decode('utf-8','replace')
 print(k,json.dumps(s)[:4500],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'resolve-discovery.json').write_text(json.dumps(d,indent=2))
