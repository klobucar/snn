from fetch_maps import *
urls={
'trumbull-gov':'https://boe.co.trumbull.oh.gov/',
'geauga-geocortex':'https://geaugarealink.geauga.oh.gov/Geocortex/Essentials/REST/sites/GeaugaRL/map?f=json',
'geauga-arcservices':'https://geaugarealink.geauga.oh.gov/arcgis/rest/services?f=pjson',
'geauga-archpdf':'https://web.archive.org/web/20240806213216if_/https://recorder.co.geauga.oh.us/wp-content/uploads/sites/21/2021/06/Voting-Precincts.pdf',
'portage-polling':'https://www.portagecounty-oh.gov/board-elections/pages/polling-locations',
'fairfield-shapes':'https://www.co.fairfield.oh.us/gis/',
'butler-archivegis':'https://web.archive.org/web/20241001if_/https://www.butlercountyauditor.org/Home/GIS-Maps',
'richland-retryold':'https://www.boe.ohio.gov/richland/c/pdf/MapRCPrecincts.pdf'}
def work(kv):
 k,u=kv;m,b=fetch('newhosts/'+k,u,raw=k=='geauga-archpdf');s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:
  d=json.loads(b);s['data']={a:d.get(a) for a in ['services','folders']};s['mapServices']=[(x.get('id'),x.get('displayName'),x.get('url')) for x in d.get('mapServices',[])]
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('map|gis|zip|precinct|voting',u+' '+t,re.I)][-30:]
 print(k,json.dumps(s)[:4000],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'newhosts-discovery.json').write_text(json.dumps(d,indent=2))
