#!/usr/bin/env python3
from fetch_maps import *
SERVICES={
'cuyahoga':('https://services7.arcgis.com/GXM8JipKyc0m6HBi/arcgis/rest/services/Voting_Precincts_region/FeatureServer/0','County BOE linked app → webmap → countywide layer; remove app display filter','current-published; effective date unestablished'),
'hamilton':('https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/Open_Data_Feature_Collection/FeatureServer/41','Cincinnati Area Geographic Information System (CAGIS) open data','current-published; effective date unestablished'),
'lucas':('https://services3.arcgis.com/T8dczfwPixv79EgZ/arcgis/rest/services/Lucas_County_Wards_and_Precincts/FeatureServer/8','Lucas County GIS','current-published; effective date unestablished'),
'stark':('https://scgisa.starkcountyohio.gov/arcgis/rest/services/BoardOfElections/PollingLocationsAndPrecincts/MapServer/1','Stark County BOE / GIS','current-published; effective date unestablished'),
'delaware':('https://services2.arcgis.com/ziXVKVy3BiopMCCU/arcgis/rest/services/Precincts/FeatureServer/0','Delaware County Auditor GIS','current-published; effective date unestablished'),
'licking':('https://gis.lickingcounty.gov/server/rest/services/Auditor/Boundaries/MapServer/2','Licking County Auditor GIS','current-published; effective date unestablished'),
'greene':('https://gis.greenecountyohio.gov/webgis2/rest/services/OpenData/OpenData/MapServer/20','Greene County GIS','current-published; effective date unestablished'),
'clark':('https://ago.clarkcountyohio.gov/ccoarcgis/rest/services/WMAS/VotingPrecincts/MapServer/0','Clark County GIS','current-published; effective date unestablished'),
'muskingum':('https://services5.arcgis.com/N1ybEAKiuuUIL8Mz/arcgis/rest/services/VotingPrecincts/FeatureServer/0','Muskingum County GIS','current-published; effective date unestablished'),
'fairfield':('https://services2.arcgis.com/L7YSCDUQyC7Biss6/arcgis/rest/services/Precincts/FeatureServer/0','Fairfield County GIS; authority chain to be checked','current-published; effective date unestablished'),
'portage':('https://services3.arcgis.com/USPCOVt8MExYdEzE/arcgis/rest/services/Voting_Precincts/FeatureServer/0','Portage County GIS; authority chain to be checked','layer named precinct_2017; historical until confirmed')}
def jfetch(k,u):
 m,b=fetch(k,u)
 if m['status']!=200:raise ValueError((m['status'],u))
 d=json.loads(b)
 if 'error' in d:raise ValueError(d)
 return d,m

def service(k,v):
 url,authority,vintage=v
 try:
  md,mm=jfetch('gis/'+k+'/layer',url+'?f=pjson')
  params={'f':'json','where':'1=1'}
  count,cm=jfetch('gis/'+k+'/count',url+'/query?'+urllib.parse.urlencode(params|{'returnCountOnly':'true'}))
  ids,im=jfetch('gis/'+k+'/ids',url+'/query?'+urllib.parse.urlencode(params|{'returnIdsOnly':'true'}))
  oid=ids.get('objectIdFieldName',md.get('objectIdField'));oids=sorted(ids.get('objectIds',[]));assert len(oids)==count['count'] and len(oids)==len(set(oids))
  pages=[];got=[]
  for n in range(0,len(oids),50):
   want=oids[n:n+50]
   p,pm=jfetch('gis/'+k+'/batch-'+str(n//50).zfill(3),url+'/query?'+urllib.parse.urlencode({'f':'json','objectIds':','.join(map(str,want)),'outFields':'*','returnGeometry':'true','returnZ':'true','returnM':'true','returnTrueCurves':'true'}))
   vals=[f['attributes'][oid] for f in p.get('features',[])];assert sorted(vals)==want and not p.get('exceededTransferLimit',False)
   got+=vals;pages.append(pm['stored_path'])
  assert sorted(got)==oids
  result={'county':k,'url':url,'authority':authority,'vintage':vintage,'approved_nov2026':False,'layer_metadata_path':mm['stored_path'],'count_path':cm['stored_path'],'ids_path':im['stored_path'],'batch_paths':pages,'feature_count':len(got),'object_id_field':oid,'native_sr':md.get('sourceSpatialReference',md.get('extent',{}).get('spatialReference')),'query_sr':p.get('spatialReference'),'fields':[x['name'] for x in md.get('fields',[])],'pagination':'count equals unique ID set equals every requested and returned batch ID; no transfer flag; no filter or simplification or reprojection'}
  (ROOT/'datasets').mkdir(exist_ok=True);(ROOT/'datasets'/f'{k}.json').write_text(json.dumps(result,indent=2)+'\n');print(k,len(got),result['query_sr'],result['fields'],flush=True)
 except Exception as e:print('FAIL',k,str(e),flush=True)

def franklin():
 m,b=fetch('sources/franklin','https://vote.franklincountyohio.gov/maps-and-data/gis-shape-files');ls=[(u,t) for u,t in links(b,m['final_url']) if '/getmedia/' in u]
 groups=[('2025',ls[:8]),('2023',ls[8:16]),('2022',ls[17:25])]
 for year,group in groups:
  comps={}
  for u,t in group:
   ext=t.rsplit('_',1)[-1] if '_' in t else t.rsplit('-',1)[-1]
   if ext=='xml':ext='shp.xml'
   mm,bb=fetch('assets/franklin-'+year+'/Voting_Precinct.'+ext,u,raw=True);assert mm['status']==200;comps[ext]=mm['stored_path']
  (ROOT/'datasets').mkdir(exist_ok=True);(ROOT/'datasets'/f'franklin-{year}.json').write_text(json.dumps({'county':'franklin','kind':'shapefile-components','vintage':year+' section on BOE page; effective date unestablished','approved_nov2026':False,'authority':'Franklin County Board of Elections','url':m['final_url'],'components':comps},indent=2)+'\n')
  print('franklin',year,comps,flush=True)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(lambda kv:service(*kv),SERVICES.items()))
 franklin()
