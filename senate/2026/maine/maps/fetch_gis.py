#!/usr/bin/env python3
"""Acquire exact Esri native polygon responses in ID-bounded batches."""
import argparse,json
from urllib.parse import urlencode
from acquire import fetch,load,ROOT
def acquire_layer(key,url):
    schema=json.loads(fetch(key+'-layer',url+'?f=pjson'))
    oid=schema.get('objectIdField') or next(x['name'] for x in schema['fields'] if x['type']=='esriFieldTypeOID')
    def q(tag,**params):
        return json.loads(fetch(key+'-'+tag,url+'/query?'+urlencode({'f':'json','where':'1=1',**params})))
    count=q('count',returnCountOnly='true')['count']
    ids=q('ids',returnIdsOnly='true')['objectIds'];assert len(ids)==len(set(ids))==count
    batches=[];allids=[]
    for offset in range(0,len(ids),80):
        selected=sorted(ids)[offset:offset+80]
        tag=f'batch-{offset//80:03d}'
        j=q(tag,objectIds=','.join(map(str,selected)),outFields='*',returnGeometry='true',returnZ='true',returnM='true',returnTrueCurves='true')
        assert not j.get('exceededTransferLimit'),j
        actual=[f['attributes'][oid] for f in j['features']]
        assert sorted(actual)==selected,(tag,len(actual),len(selected))
        allids+=actual;batches.append({'key':key+'-'+tag,'local_path':'raw/'+key+'-'+tag+'.gz','requested_ids':selected,'returned_ids':actual,'exceededTransferLimit':j.get('exceededTransferLimit',False),'spatialReference':j.get('spatialReference')})
    assert sorted(allids)==sorted(ids)
    ids_after=q('ids-after',returnIdsOnly='true')['objectIds']
    count_after=q('count-after',returnCountOnly='true')['count']
    assert sorted(ids_after)==sorted(ids) and count_after==count
    p=ROOT/'gis-downloads.json';d=json.loads(p.read_text()) if p.exists() else {}
    d[key]={'url':url,'oid_field':oid,'count':count,'ids':sorted(ids),'after_count':count_after,'after_ids':sorted(ids_after),'native_crs':schema['extent']['spatialReference'],'hasZ':schema.get('hasZ'),'hasM':schema.get('hasM'),'supportsTrueCurve':schema.get('advancedQueryCapabilities',{}).get('supportsTrueCurve'),'batches':batches}
    p.write_text(json.dumps(d,indent=2)+'\n')
    print(key,'COMPLETE',count,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('key');p.add_argument('url');a=p.parse_args();acquire_layer(a.key,a.url)
