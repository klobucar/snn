#!/usr/bin/env python3
"""Optional GEOS validation/cross-vintage diagnostics. Requires shapely (tested 2.2.0).
No geometry is repaired or substituted. ID matches are diagnostic, not a crosswalk.
"""
import csv,hashlib,json,pathlib,sys
import shapely
from shapely.geometry import shape
from shapely.validation import explain_validity
R=pathlib.Path(__file__).resolve().parent
rows=list(csv.DictReader((R/'manifest.csv').open()))
for row in rows:assert hashlib.sha256((R/row['local_path']).read_bytes()).hexdigest()==row['sha256']
report={'shapely_version':shapely.__version__,'geos_version':shapely.geos_version_string,'files':[],'cross_vintage':[]}
by={}
for row in rows:
 if row['format']!='GeoJSON':continue
 fs=json.loads((R/row['local_path']).read_text())['features'];year=row['local_path'].split('/')[0];key='PRECINCTID' if year=='2024' else 'PrecinctID';features={f['properties'][key]:f for f in fs};invalid=[];empty=[]
 for f in fs:
  g=shape(f['geometry'])
  if not g.is_valid:invalid.append({'precinct_id':f['properties'][key],'reason':explain_validity(g)})
  if g.is_empty:empty.append(f['properties'][key])
 report['files'].append({'county':row['county'],'year':year,'features':len(fs),'invalid':invalid,'empty':empty});by[row['county'],year]=features
for county in dict.fromkeys(r['county'] for r in rows):
 a,b=by[county,'2024'],by[county,'2026'];common=set(a)&set(b);same=0;different=0;not_comparable=0
 for k in common:
  x,y=shape(a[k]['geometry']),shape(b[k]['geometry'])
  if not x.is_valid or not y.is_valid:not_comparable+=1
  elif x.equals(y):same+=1
  else:different+=1
 report['cross_vintage'].append({'county':county,'common_ids':len(common),'only_2024_ids':len(set(a)-set(b)),'only_2026_ids':len(set(b)-set(a)),'exact_topological_equal_geometry':same,'different_geometry':different,'invalid_not_compared':not_comparable,'warning':'Different CRS transformations may cause tiny coordinate differences; this is not proof of boundary change.'})
(R/'topology-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('Checksums',len(rows),'files',len(report['files']),'invalid',sum(len(x['invalid']) for x in report['files']),'empty',sum(len(x['empty']) for x in report['files']))
