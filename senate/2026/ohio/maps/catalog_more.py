from fetch_maps import *
names=['Summit','Montgomery','Butler','Medina','Trumbull','Mahoning','Wood','Miami','Richland','Geauga','Wayne','Allen','Ashtabula','Erie','Tuscarawas']
def work(k):
 q=f'({k}) (precinct OR precincts OR voting)'
 m,b=fetch('catalog2/'+k.lower(),'https://www.arcgis.com/sharing/rest/search?'+urllib.parse.urlencode({'q':q,'f':'json','num':100}));d=json.loads(b)
 rs=[{a:x.get(a) for a in ['id','title','owner','url','type']} for x in d.get('results',[])]
 print(k,json.dumps(rs),flush=True);return k.lower(),rs
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,names))
(ROOT/'catalog-more.json').write_text(json.dumps(d,indent=2))
