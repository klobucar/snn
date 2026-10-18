from fetch_maps import *
urls={
 'richland-old-cdx':'https://web.archive.org/cdx/search/cdx?url=www.boe.co.richland.oh.us/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&collapse=urlkey',
 'tusc-old-cdx':'https://web.archive.org/cdx/search/cdx?url=boe.co.tuscarawas.oh.us/pctmaps/*&output=json&filter=statuscode:200&collapse=urlkey',
 'wood-cities':'https://boe.woodcountyohio.gov/233/Cities',
 'wood-townships':'https://boe.woodcountyohio.gov/234/Townships',
 'richland-gis-old':'https://www.richlandmaps.com/',
 'hamilton-cagis-landing':'https://www.cagis.org/Opendata/',
 'lucas-gis-landing':'https://lucascountyoh.gov/3145/GIS-Maps-Apps-Data',
 'census-techdoc':'https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2020pl/TGRSHP2020PL_TechDoc.pdf'}
def work(kv):
 k,u=kv;m,b=fetch('last/'+k,u,raw=k=='census-techdoc');o=dict(metadata=m)
 try:o['data']=json.loads(b)
 except:o['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('pdf|DocumentCenter|precinct|shp|zip|gis',u+' '+t,re.I)]
 print(k,m['status'],len(b),str(o.get('links',o.get('data')))[:2000],flush=True);return k,o
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'last-alternatives.json').write_text(json.dumps(d,indent=2)+'\n')
