from fetch_maps import *
urls={
'geauga-recorder-archpage':'https://web.archive.org/web/20240806213216if_/https://recorder.co.geauga.oh.us/document/voting-precincts/',
'butler-precinctmap-current':'https://elections.bcohio.gov/Maps/index.cfm',
'summit-council2010':'https://web.archive.org/web/20101128153418if_/http://summitcountyboe.com/Maps/County%20CouncilAll.pdf',
'butler-countywide-archive':'https://web.archive.org/cdx/search/cdx?url=elections.bcohio.gov/Maps/*&output=json&filter=statuscode:200&collapse=urlkey',
'geauga-boe-oldretry':'https://web.archive.org/cdx/search/cdx?url=boe.co.geauga.oh.us/*&output=json&filter=statuscode:200&filter=mimetype:application/pdf&collapse=urlkey',
'richland-archversions':'https://web.archive.org/cdx/search/cdx?url=www.boe.ohio.gov/richland/c/pdf/MapRCPrecincts.pdf&output=json&filter=statuscode:200',
'portage-newgis':'https://www.portagecounty-oh.gov/geographic-information-systems',
'fairfield-open':'https://www.co.fairfield.oh.us/auditor/GIS-Data.html',
'butler-elections-oldpage':'https://web.archive.org/web/20241001if_/https://elections.bcohio.gov/Maps/index.cfm'}
def work(kv):
 k,u=kv;m,b=fetch('historical/'+k,u,raw=k=='summit-council2010');s={'status':m['status'],'url':u,'bytes':len(b),'path':m['stored_path']}
 try:s['data']=json.loads(b)
 except:s['links']=[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('map|gis|zip|precinct|voting',u+' '+t,re.I)][-20:]
 print(k,json.dumps(s)[:4000],flush=True);return k,s
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:d=dict(ex.map(work,urls.items()))
(ROOT/'historical-discovery.json').write_text(json.dumps(d,indent=2))
