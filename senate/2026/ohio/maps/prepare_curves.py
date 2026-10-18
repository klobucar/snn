#!/usr/bin/env python3
"""Retain native curves, request separately labeled polygon derivative only where needed."""
from fetch_maps import *
for p in sorted((ROOT/'datasets').glob('*.json')):
 d=json.loads(p.read_text());ids=[]
 for path in d.get('batch_paths',[]):
  j=json.loads(gzip.decompress((ROOT/path).read_bytes()))
  ids += [f['attributes'][d['object_id_field']] for f in j['features'] if 'curveRings' in (f.get('geometry') or {})]
 if not ids:continue
 paths=[]
 for n in range(0,len(ids),50):
  want=ids[n:n+50];u=d['url']+'/query?'+urllib.parse.urlencode({'f':'json','objectIds':','.join(map(str,want)),'outFields':'*','returnGeometry':'true','returnTrueCurves':'false','returnZ':'true','returnM':'true'})
  # Existing single-response acquisition remains reproducible; new large lists are batched.
  tag='gis-derivative/'+p.stem+'/linearized' if len(ids)<=100 else 'gis-derivative/'+p.stem+'/linearized-'+str(n//50)
  if len(ids)<=100 and n:break
  if len(ids)<=100:
   u=d['url']+'/query?'+urllib.parse.urlencode({'f':'json','objectIds':','.join(map(str,ids)),'outFields':'*','returnGeometry':'true','returnTrueCurves':'false','returnZ':'true','returnM':'true'});want=ids
  m,b=fetch(tag,u);j=json.loads(b);assert not j.get('exceededTransferLimit');assert sorted(f['attributes'][d['object_id_field']] for f in j['features'])==sorted(want);assert not any('curveRings' in f['geometry'] for f in j['features']);paths.append(m['stored_path'])
 d['linearized_derivative_path']=paths[0];d['linearized_derivative_paths']=paths;d['native_curve_object_ids']=ids;p.write_text(json.dumps(d,indent=2)+'\n');print(p.stem,len(ids))
