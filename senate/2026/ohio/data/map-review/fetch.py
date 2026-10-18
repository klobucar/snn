#!/usr/bin/env python3
"""Bounded public research captures, with exact source metadata and compressed bytes."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import datetime,gzip,hashlib,json,requests,subprocess,tempfile
ROOT=Path(__file__).resolve().parent
URLS={'richland-county-shapes': 'https://www.richlandcountyoh.gov/departments/auditor/CamaData', 'richland-map-services': 'https://maps.richlandcountyoh.us/richlandgis/rest/services?f=pjson', 'richland-current-pdf': 'https://www.boe.ohio.gov/richland/c/upload/Info_PrecinctMaps.pdf', 'tuscarawas-precinct-locator': 'https://lookup.boe.ohio.gov/vtrapp/tuscarawas/precandpoll.aspx', 'IASWOLRD_LGIM': 'https://maps.richlandcountyoh.us/richlandgis/rest/services/IASWOLRD_LGIM/MapServer?f=pjson', 'Richland_OH_Boundary_Basemap': 'https://maps.richlandcountyoh.us/richlandgis/rest/services/Richland_OH_Boundary_Basemap/MapServer?f=pjson', 'Parcels': 'https://maps.richlandcountyoh.us/richlandgis/rest/services/Parcels/MapServer?f=pjson', 'richland-geopolitical-layer': 'https://maps.richlandcountyoh.us/richlandgis/rest/services/Richland_OH_Boundary_Basemap/MapServer/0?f=pjson', 'richland-geopolitical-types': 'https://maps.richlandcountyoh.us/richlandgis/rest/services/Richland_OH_Boundary_Basemap/MapServer/0/query?f=json&where=1%3D1&outFields=OBJECTID%2CNAME%2CGEOTYPE%2CFULLFIPS%2CEFFECTDATE%2CENDDATE&returnGeometry=false', 'richland-official-shapefiles-folder': 'https://drive.google.com/drive/folders/1_3AxSbDx__knCxPQuO4wSgPUEZozcqTv', 'richland-geopolitical-shapefile': 'https://drive.google.com/uc?export=download&id=1L1sREqYAsPeZwaxAUqqe4z7ycf16e3Qz', 'richland-county-district-shapefile': 'https://drive.google.com/uc?export=download&id=10YAZwhVrmrn3RjlC932kn85sOaDzYrM_', 'tuscarawas-server': 'https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer?f=pjson', 'tuscarawas-minimal-geometry': 'https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer/0/query?f=json&where=OBJECTID%3D1&outFields=OBJECTID%2CPRECT_NA&returnGeometry=true', 'tuscarawas-official-render': 'https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer/export?f=image&bbox=2184251.303550693%2C196665.41216384678%2C2315450.294216496%2C371073.5033010313&bboxSR=3734&imageSR=3734&size=2000%2C2600&dpi=96&format=png32&transparent=false&layers=show%3A0'}
def fetch(item):
 key,url=item;row={'id':key,'url':url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  r=requests.get(url,timeout=35);path=ROOT/(key+'.html.gz');path.write_bytes(gzip.compress(r.content,mtime=0))
  row.update(status=r.status_code,final_url=r.url,raw_sha256=hashlib.sha256(r.content).hexdigest(),asset=path.name,stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=len(r.content),headers=dict(r.headers))
 except requests.exceptions.SSLError as e:
  row['requests_error']=str(e)
  with tempfile.TemporaryDirectory() as t:
   body=Path(t)/'body';hdr=Path(t)/'headers'
   c=subprocess.run(['curl','--silent','--show-error','--location','--max-time','35','--dump-header',str(hdr),'--output',str(body),'--write-out','%{http_code}\\n%{url_effective}',url],capture_output=True,text=True)
   row['transport']='system curl with default certificate verification'
   if c.returncode==0:
    code,final=c.stdout.split('\\n',1) if '\\n' in c.stdout else c.stdout.split('\n',1)
    raw=body.read_bytes();path=ROOT/(key+'.html.gz');path.write_bytes(gzip.compress(raw,mtime=0))
    row.update(status=int(code),final_url=final,raw_sha256=hashlib.sha256(raw).hexdigest(),asset=path.name,stored_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=len(raw),raw_headers=hdr.read_text())
   else:row['error']=c.stderr
 except requests.RequestException as e:row['error']=str(e)
 return row
if __name__=='__main__':
 rows=list(ThreadPoolExecutor(max_workers=4).map(fetch,URLS.items()));(ROOT/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
 for r in rows:print(r['id'],r.get('status',r.get('error')))
