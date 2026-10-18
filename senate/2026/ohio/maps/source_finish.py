from fetch_maps import *
x=json.loads(gzip.decompress((ROOT/'evidence/resolve/summit-archive-old2.gz').read_bytes()))
rs=[r for r in x[1:] if re.search(r'/(420Precincts(?:-\d+)?|298ApprovedPrecincts(?:-\d+)?)\.pdf$',r[2],re.I)]
rs=sorted(rs,key=lambda r:(r[2].split('/uploads/')[-1][:7],r[1]),reverse=True)
urls={
'columbiana-webmap':'https://www.arcgis.com/sharing/rest/content/items/b4d95d31d76341379d1e0579cc59dd63/data?f=pjson',
'butler-webmap':'https://www.arcgis.com/sharing/rest/content/items/e69cbbd60caf4d89822b39ec0e16143d/data?f=pjson',
'geauga-real':'https://www.geaugarealink.co.geauga.oh.us/real/index.html',
'medina-hits':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&VERSION=1.1.0&REQUEST=GetFeature&TYPENAME=precincp&RESULTTYPE=hits',
'medina-highlimit':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=precincp&MAXFEATURES=100000',
'medina-first10':'https://gm.medinaco.org/gm-be/mapserv?map=/srv/geomoose/maps/medina/voting/precincp.map&SERVICE=WFS&VERSION=1.0.0&REQUEST=GetFeature&TYPENAME=precincp&MAXFEATURES=10',
'trumbull-http':'http://www.boe.co.trumbull.oh.us/',
'ashtabula-http':'http://gis2.ashtabulacounty.us/arcgis/rest/services/Districts_Voting/MapServer?f=pjson',
'butler-elections-cdx':'https://web.archive.org/cdx/search/cdx?url=elections.bcohio.gov/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&filter=urlkey:.*map.*&collapse=urlkey',
'geauga-recorder-cdx3':'https://web.archive.org/cdx/search/cdx?url=recorder.co.geauga.oh.us/wp-content/uploads/sites/21/2021/06/Voting-Precincts.pdf&output=json',
'summit-history0':'https://web.archive.org/web/'+rs[0][1]+'if_/'+rs[0][2],
'summit-history1':'https://web.archive.org/web/'+rs[-1][1]+'if_/'+rs[-1][2]}
(ROOT/'summit-historical-selection.json').write_text(json.dumps(rs,indent=2))
def work(kv):
 k,u=kv;m,b=fetch('finish/'+k,u,raw=k.startswith('summit-history'));s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']=d if isinstance(d,list) else {a:d.get(a) for a in ['services','folders','map','webmap']}
  if isinstance(d,dict) and 'operationalLayers' in d:s['layers']=[(l.get('title'),l.get('url')) for l in d['operationalLayers']]
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('map|gis|zip|precinct',u+' '+t,re.I)][:12]
 print(k,json.dumps(s)[:3000],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'finish-discovery.json').write_text(json.dumps(d,indent=2))
