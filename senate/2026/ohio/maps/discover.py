import concurrent.futures,json,re
from fetch_maps import *
urls={
'franklin':'https://vote.franklincountyohio.gov/maps-and-data/gis-shape-files',
'cuyahoga':'https://boe.cuyahogacounty.gov/maps-and-data/interactive-maps-by-city-and-cleveland-ward',
'hamilton':'https://votehamiltoncountyohio.gov/campaign-media/maps/',
'summit':'https://www.boe.ohio.gov/summit/precinct-and-polling-location-info/maps/',
'montgomery':'https://www.montgomery.boe.ohio.gov/candidate-tools/',
'clermont':'https://gis.clermontcountyohio.gov/download-gis-data/',
'lake':'https://www.lakecountyohio.gov/boe/precinct-maps/',
'greene':'https://www.greenecountyohio.gov/1807/Downloadable-Maps'}
def work(kv):
 k,u=kv;m,b=fetch('sources/'+k,u);ls=links(b,m.get('final_url',u));print(k,m['status'],[(u,t) for u,t in ls if re.search(r'precinct|\.zip|\.shp|\.dbf|\.prj|\.shx|gis|arcgis|maps',u+' '+t,re.I)][:50],flush=True)
 return k,{'url':u,'status':m['status'],'links':ls}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'discovery-pages.json').write_text(json.dumps(d,indent=2))
# Retain public catalog search responses for discovery, never assume ownership from title.
rows=list(__import__('csv').DictReader((ROOT.parent/'data/county-turnout.csv').open()))[:32]
def catalog(r):
 k=r['county'].lower();q=f'{r["county"]} Ohio precinct (type:"Feature Service" OR type:"Map Service" OR type:"Web Map")'
 u='https://www.arcgis.com/sharing/rest/search?'+urllib.parse.urlencode({'q':q,'f':'json','num':100})
 m,b=fetch('catalog/'+k,u)
 try:d=json.loads(b)
 except:d={}
 rs=[{a:x.get(a) for a in ['id','title','owner','url','type']} for x in d.get('results',[])]
 print('CAT',k,rs[:15],flush=True);return k,rs
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:c=dict(ex.map(catalog,rows))
(ROOT/'catalog-discovery.json').write_text(json.dumps(c,indent=2))
