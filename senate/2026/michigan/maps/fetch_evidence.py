#!/usr/bin/env python3
"""Preserve small public metadata/authority evidence with retrieval records."""
import datetime,hashlib,json,pathlib,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
BASE='https://www.arcgis.com/sharing/rest/content/items/'
urls={
'viewer.json':BASE+'a36d3f1069d34ed798659d2efa2b8231?f=pjson',
'viewer-data.json':BASE+'a36d3f1069d34ed798659d2efa2b8231/data?f=pjson',
'2026-item.json':BASE+'6a9596d0479c4770b4e943a4a82b14f1?f=pjson',
'2024-item.json':BASE+'02d40893317d46569017beeb14f9c63e?f=pjson',
'2024-metadata.xml':BASE+'02d40893317d46569017beeb14f9c63e/info/metadata/metadata.xml',
'2026-layer.json':'https://services3.arcgis.com/dxRQUfTDNtfqZ301/arcgis/rest/services/VotingPrecincts2026_051926_gdb/FeatureServer/0?f=pjson',
'2024-layer.json':'https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/boundaries/MapServer/9?f=pjson',
'boe-layer.json':'https://gisp.mcgi.state.mi.us/maps/rest/services/BOE/precinctmapping/MapServer/0?f=pjson',
'dtmb-boundaries.html':'https://www.michigan.gov/dtmb/services/maps/mgf-data-hub/boundaries-and-mgf',
'dtmb-maps.html':'https://www.michigan.gov/dtmb/services/maps',
'detroit-council-2026.pdf':'https://detroitmi.gov/sites/detroitmi.localhost/files/2025-04/Council%20District%20Maps%202025.pdf',
'meridian-2026.pdf':'https://www.meridian.mi.us/media/nxfeq31d/2026-precinct-and-polling-location-map-update.pdf'}
rows=[]
for name,url in urls.items():
 row={'url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  with urllib.request.urlopen(url,timeout=30) as r:b=r.read();row.update(status=r.status,headers=dict(r.headers))
  p=ROOT/'raw'/name;p.write_bytes(b);row.update(local_path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b))
 except Exception as e:row.update(error=str(e))
 rows.append(row);print(name,row.get('status',row.get('error')),flush=True)
(ROOT/'evidence-manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
