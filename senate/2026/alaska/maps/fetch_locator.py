"""Download every locator polygon by verified object-ID batches, native CRS.

Run fetch_maps.py first. URLs follow the DOE-linked app -> webmap -> layer.
No quantization, geometry precision, simplification, bounding box, or outSR.
"""
import argparse
import json
from urllib.parse import urlencode
from fetch_maps import ROOT, fetch

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--refresh',action='store_true'); a=ap.parse_args()
    # Entry-point evidence: the primary DOE page links this exact ArcGIS app.
    fetch('https://www.elections.alaska.gov/', 'raw/doe-home.html.gz', a.refresh)
    fetch('https://www.elections.alaska.gov/election-polls/', 'raw/polling-places.html.gz', a.refresh)
    item='https://www.arcgis.com/sharing/rest/content/items/'
    appid='579890d66c7e40ae9f7cc227d76669b1'
    fetch(item+appid+'?f=pjson','raw/locator-item.json',a.refresh)
    fetch(item+appid+'/data?f=pjson','raw/locator-config.json',a.refresh)
    app=json.loads((ROOT/'raw/locator-config.json').read_text())
    webid=app['map']['itemId']
    portal=app['map']['portalUrl']
    item='https://www.arcgis.com/sharing/rest/content/items/'
    fetch(item+webid+'?f=pjson','raw/locator-webmap-item.json',a.refresh)
    web=json.loads(fetch(item+webid+'/data?f=pjson','raw/locator-webmap-data.json',a.refresh))
    layers=[l for l in web['operationalLayers'] if l.get('title')=='Precincts']
    assert len(layers)==1
    base=layers[0]['url']
    layer=json.loads(fetch(base+'?f=pjson','raw/locator-precinct-layer.json',a.refresh))
    fetch(item+layer['serviceItemId']+'?f=pjson','raw/locator-service-item.json',a.refresh)
    fetch(base.rsplit('/',1)[0]+'?f=pjson','raw/locator-service.json',a.refresh)
    def q(params,name):
        return json.loads(fetch(base+'/query?'+urlencode(dict(f='json',**params)),name,a.refresh))
    count=q(dict(where='1=1',returnCountOnly='true'),'raw/locator-count.json')['count']
    ids=q(dict(where='1=1',returnIdsOnly='true'),'raw/locator-ids.json')
    oids=sorted(ids['objectIds']); assert len(set(oids))==len(oids)==count
    seen=[]
    for i in range(0,len(oids),50):
        batch=oids[i:i+50]
        d=q(dict(objectIds=','.join(map(str,batch)),outFields='*',returnGeometry='true'),
            f'raw/locator-features-{i//50+1:03d}.json.gz')
        assert 'error' not in d and not d.get('exceededTransferLimit',False), d.keys()
        got=[f['attributes'][ids['objectIdFieldName']] for f in d['features']]
        assert sorted(got)==batch
        seen+=got
    assert sorted(seen)==oids
    print('Verified complete native locator download:',count,'features in',(count+49)//50,'batches')

if __name__=='__main__': main()
