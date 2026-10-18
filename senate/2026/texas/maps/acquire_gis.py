#!/usr/bin/env python3
"""ArcGIS originals with pre/post counts and complete ID-set batch accounting."""
from acquire import *
from urllib.parse import urlencode
import concurrent.futures

LAYERS=[
 ('bell-2022','Bell','https://services3.arcgis.com/jjDKBbyoUNyhuTYf/arcgis/rest/services/Bell_County_Voting_Precincts_2022/FeatureServer/0','https://www.bellcountytx.com/departments/elections/'),
 ('hays-2026','Hays','https://services5.arcgis.com/bVphnK8rPe5MHUSr/arcgis/rest/services/Hays_County_Elections_Precincts_Effective_Jan_2026/FeatureServer/7','https://www.hayscountytx.gov/256/Precinct-Data-Maps'),
 ('johnson-2022','Johnson','https://services7.arcgis.com/gVohhGAlfFScDJGs/arcgis/rest/services/Voting_Districts_2022/FeatureServer/0','https://www.johnsoncountytx.org/departments/elections-office/precinct-maps'),
 ('bexar-voter','Bexar','https://maps.bexar.org/arcgis/rest/services/EL/VoterPrecincts/MapServer/0','https://elections.bexar.gov/173/Voter-Precinct-Maps'),
 ('travis-precincts','Travis','https://taxmaps.traviscountytx.gov/arcgis/rest/services/Precincts/MapServer/0','https://tax-office.traviscountytx.gov/voters'),
 ('fort-bend-2025','Fort Bend','https://gisportal.fortbendcountytx.gov/arcgis/rest/services/InteractiveMap/Elections_Public/MapServer/1','https://www.fortbendcountytx.gov/government/departments/elections-voter-registration'),
 ('fort-bend-2022','Fort Bend','https://gisportal.fortbendcountytx.gov/arcgis/rest/services/InteractiveMap/Elections_Public/MapServer/5','https://www.fortbendcountytx.gov/government/departments/elections-voter-registration'),
 ('brazoria-2024','Brazoria','https://arcgis-web.brazoriacountytx.gov/arcgis/rest/services/general/Political_Boundaries/MapServer/9','https://www.brazoriacountyclerktx.gov/departments/elections/precinct-maps'),
 ('brazoria-2026','Brazoria','https://arcgis-web.brazoriacountytx.gov/arcgis/rest/services/general/Political_Boundaries/MapServer/11','https://www.brazoriacountyclerktx.gov/departments/elections/precinct-maps'),
]
def run(t):
 key,county,url,parent=t; audit=ROOT/'gis'/f'{key}-audit.json'
 if audit.exists() and json.loads(audit.read_text()).get('status')=='pass':return
 def get(label,u):
  d=fetch('gis-'+key+'-'+label,u,parent)
  if d.get('status')!=200 or 'error' in d:raise ValueError(d)
  j=json.loads(original(d))
  if 'error' in j:raise ValueError(j)
  return j,d
 def query(label,**kw):return get(label,url+'/query?'+urlencode(dict(f='json',where='1=1',**kw)))
 a=dict(id=key,county=county,layer_url=url,authority_parent=parent,
        authority_scope='County-controlled GIS hostname, independently discovered; parent election page retained. Direct service discovery is not a proven app-to-service link unless separately captured.',
        approval_status='unknown for November 2026; service name/edit dates are not legal approval',geometry_request='No outSR, precision, quantization, generalization or maxAllowableOffset; returnZ/M/TrueCurves=true; all attributes.')
 try:
  layer,ld=get('layer',url+'?f=pjson');service,sd=get('service',url.rsplit('/',1)[0]+'?f=pjson')
  a.update(layer_metadata_source=ld['id'],service_metadata_source=sd['id'],native_spatial_reference=layer.get('extent',{}).get('spatialReference',service.get('spatialReference')),hasZ=layer.get('hasZ'),hasM=layer.get('hasM'),advancedQueryCapabilities=layer.get('advancedQueryCapabilities'),editingInfo=layer.get('editingInfo'),maxRecordCount=layer.get('maxRecordCount'),serviceItemId=service.get('serviceItemId'))
  if service.get('serviceItemId'):
   try:get('item','https://www.arcgis.com/sharing/rest/content/items/'+service['serviceItemId']+'?f=pjson')
   except Exception as e:a['item_metadata_gap']=repr(e)
  pre,_=query('pre-count',returnCountOnly='true');ids,_=query('pre-ids',returnIdsOnly='true')
  requested=sorted(ids['objectIds']);oid=ids['objectIdFieldName'];batches=[];returned=[]
  assert len(requested)==len(set(requested))==pre['count']
  batch_size=min(100,int(layer.get('maxRecordCount') or 100))
  for i in range(0,len(requested),batch_size):
   req=requested[i:i+batch_size]
   j,d=query(f'batch-{i//batch_size+1:03d}',objectIds=','.join(map(str,req)),outFields='*',returnGeometry='true',returnZ='true',returnM='true',returnTrueCurves='true')
   got=[f['attributes'][oid] for f in j['features']]
   batches.append(dict(source_id=d['id'],requested_ids=req,returned_ids=got,exceededTransferLimit=j.get('exceededTransferLimit',False),spatialReference=j.get('spatialReference'),hasZ=j.get('hasZ'),hasM=j.get('hasM'),features=len(got),curve_geometry_count=sum(bool(f.get('geometry',{}).get('curveRings') or f.get('geometry',{}).get('curvePaths')) for f in j['features'])))
   assert sorted(req)==sorted(got) and not j.get('exceededTransferLimit',False)
   returned+=got
  post,_=query('post-count',returnCountOnly='true');post_ids,_=query('post-ids',returnIdsOnly='true')
  assert requested==sorted(post_ids['objectIds'])==sorted(returned) and pre['count']==post['count']
  a.update(status='pass',pre_count=pre['count'],post_count=post['count'],pre_ids=requested,post_ids=sorted(post_ids['objectIds']),object_id_field=oid,batches=batches,all_fields=layer['fields'])
 except Exception as e:a.update(status='gap',error=repr(e))
 save_json(audit,a);print(key,a['status'],a.get('pre_count'),str(a.get('error',''))[:200],flush=True)

if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:list(ex.map(run,LAYERS))
