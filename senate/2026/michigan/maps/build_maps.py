#!/usr/bin/env python3
"""Download public official GIS responses (--refresh), or rebuild offline; stdlib only.
Raw responses are losslessly gzip-compressed. Derived GeoJSON retains full server
coordinate precision; SVG previews round projected display coordinates only.
"""
import argparse,collections,concurrent.futures,csv,datetime,gzip,hashlib,html,json,math,pathlib,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parent
SOURCES={'2024':'https://gisagocss.state.mi.us/arcgis/rest/services/OpenData/boundaries/MapServer/9','2026':'https://services3.arcgis.com/dxRQUfTDNtfqZ301/arcgis/rest/services/VotingPrecincts2026_051926_gdb/FeatureServer/0'}
OWNER='Michigan Department of State Bureau of Elections; State of Michigan DTMB Center for Shared Solutions'
COLS='county,fips,sourceURL,official_owner,geometry_vintage,retrieved_utc,local_path,format,crs,feature_count,sha256,limitations'.split(',')
def packed(o):return json.dumps(o,separators=(',',':'),ensure_ascii=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def savegz(path,b):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(gzip.compress(b,mtime=0))
def request(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Michigan precinct research (public data archival)'}),timeout=90) as r:
  b=r.read();return b,{'url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':r.status,'headers':dict(r.headers),'response_sha256':sha(b)}
def fetch(county,year):
 fips=county['county_fips'];slug=county['county'].lower().replace('.','').replace(' ','-'); raw=ROOT/'raw'/year/(slug+'.json.gz'); meta=raw.with_suffix('.retrieval.json')
 cf='COUNTYFIPS' if year=='2024' else 'CountyFIPS'
 where=f"{cf}='{fips[2:]}'"
 base=SOURCES[year]+'/query?'
 if REFRESH or not meta.exists():
  b,m=request(base+urllib.parse.urlencode({'where':where,'returnIdsOnly':'true','f':'json'}));ids=json.loads(b)
  assert 'error' not in ids,ids
  oids=sorted(ids['objectIds']);features=[];pages=[]
  # ID batching avoids dependence on resultOffset support and service feature limits.
  for start in range(0,len(oids),200):
   url=base+urllib.parse.urlencode({'objectIds':','.join(map(str,oids[start:start+200])),'outFields':'*','returnGeometry':'true','outSR':'4326','f':'geojson'})
   pb,pm=request(url);d=json.loads(pb);assert 'error' not in d,d
   assert not d.get('exceededTransferLimit'),d.keys()
   pg=ROOT/'raw'/year/(slug+f'-page-{start//200:02d}.geojson.gz');savegz(pg,pb);pm['local_path']=str(pg.relative_to(ROOT));pm['saved_sha256']=sha(pg.read_bytes());pages.append(pm);features.extend(d['features'])
  assert len(features)==len(oids),(slug,len(features),len(oids))
  m.update({'ids_response':ids,'pages':pages});meta.write_text(json.dumps(m,indent=2)+'\n')
 m=json.loads(meta.read_text());d={'type':'FeatureCollection','features':sum((json.loads(gzip.decompress((ROOT/pm['local_path']).read_bytes()))['features'] for pm in m['pages']),[])}
 for pm in m['pages']:
  page_bytes=(ROOT/pm['local_path']).read_bytes();assert sha(page_bytes)==pm['saved_sha256'];assert sha(gzip.decompress(page_bytes))==pm['response_sha256']
 fs=d['features'];assert fs
 idfield='PRECINCTID' if year=='2024' else 'PrecinctID';yf='ELECTIONYE' if year=='2024' else 'ElectionYe'
 errors=[];points=[];paths=[]
 def xy(p):return (p[0]*math.cos(math.radians(43)), -p[1])
 for i,f in enumerate(fs):
  assert f['properties'][cf]==fips[2:]
  g=f.get('geometry');assert g and g['type'] in ('Polygon','MultiPolygon')
  polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
  for poly in polys:
   for ring in poly:
    if len(ring)<4 or ring[0]!=ring[-1]:errors.append({'feature':i,'error':'unclosed/short ring'})
    for p in ring:assert len(p)>=2 and math.isfinite(p[0]) and math.isfinite(p[1]) and -180<=p[0]<=180 and -90<=p[1]<=90
    points.extend(map(xy,ring))
 assert not errors,errors
 xs,ys=zip(*points);xmin,xmax,ymin,ymax=min(xs),max(xs),min(ys),max(ys);scale=min(920/(xmax-xmin),680/(ymax-ymin))
 for f in fs:
  g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates'];cmd=[]
  for poly in polys:
   for ring in poly:
    ps=[f'{30+(xy(p)[0]-xmin)*scale:.2f},{80+(xy(p)[1]-ymin)*scale:.2f}' for p in ring];ps=[p for i,p in enumerate(ps) if i==0 or p!=ps[i-1]];cmd.append('M'+' L'.join(ps)+' Z')
  label=str(f['properties'].get(idfield))+' '+str(f['properties'].get('Precinct_Long_Name',f['properties'].get('PrecinctLo','')))
  paths.append('<path d="'+' '.join(cmd)+'"><title>'+html.escape(label)+'</title></path>')
 out=ROOT/year;out.mkdir(exist_ok=True);geo=out/(slug+'.geojson');geo.write_bytes(packed(d));svg=out/(slug+'.svg')
 svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 800"><rect width="1000" height="800" fill="white"/><text x="30" y="28" font-size="21">'+html.escape(county['county'])+f' — {year} source snapshot ({len(fs)} features)</text><text x="30" y="52" font-size="14">Generated preview · research 2026-10-17 · hover for source precinct ID · not an official published map</text><g fill="#dce9ef" fill-rule="evenodd" stroke="#355368" stroke-width="0.45">'+''.join(paths)+'</g></svg>')
 limitation=('2024 cycle; most but not all jurisdictions validated' if year=='2024' else '2026 labeled layer; Nov 3 approval unverified')+'; structural geometry validation only; not a reporting-board crosswalk'
 rows=[]
 for path,fmt,crs in [(geo,'GeoJSON','OGC:CRS84 (longitude,latitude; server outSR=4326)'),(svg,'SVG (generated preview)','Local display projection: lon*cos(43 degrees), -lat')]:
  rows.append(dict(zip(COLS,[county['county'],fips,SOURCES[year],OWNER,year+' election-cycle label; snapshot 2026-10-17',m['retrieved_utc'],str(path.relative_to(ROOT)),fmt,crs,len(fs),sha(path.read_bytes()),limitation])))
 ids=[f['properties'].get(idfield) for f in fs]
 return rows,{'county':county['county'],'fips':fips,'year':year,'features':len(fs),'unique_precinct_ids':len(set(ids)),'duplicate_or_missing_id_count':len(ids)-len(set(ids))+sum(x is None for x in ids),'year_values':dict(collections.Counter(str(f['properties'].get(yf)) for f in fs)),'sample_properties':[f['properties'] for f in fs[:2]],'structural_errors':errors,'topology_validity':'not tested by stdlib; see optional validate_topology.py','bbox':[min(p[0] for f in [] for p in [])] if False else [xmin/math.cos(math.radians(43)),-ymax,xmax/math.cos(math.radians(43)),-ymin]}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');args=parser.parse_args();REFRESH=args.refresh
 counties=list(csv.DictReader((ROOT.parent/'data/county-turnout.csv').open()))[:23];assert len(counties)==23
 tasks=[(c,y) for c in counties for y in SOURCES]
 rows=[];checks=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for r,c in pool.map(lambda t:fetch(*t),tasks):rows.extend(r);checks.append(c);print(c['county'],c['year'],c['features'],flush=True)
 with (ROOT/'manifest.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(rows)
 (ROOT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
 assert len(rows)==92 and len(checks)==46
 # Supplemental official municipal map, with no implied polygon feature count.
 evidence=ROOT/'evidence-manifest.json'
 if evidence.exists():
  for e in json.loads(evidence.read_text()):
   if e.get('local_path')=='raw/meridian-2026.pdf':
    row=dict(zip(COLS,['Ingham','26065',e['url'],'Charter Township of Meridian','PDF printed Last Updated 05/29/2026',e['retrieved_utc'],e['local_path'],'PDF','not specified','',e['sha256'],'Municipal supplement only; not countywide; no Nov 2026 approval established']))
    with (ROOT/'manifest.csv').open('a') as f:csv.DictWriter(f,fieldnames=COLS).writerow(row)
 index=['<!doctype html><meta charset="utf-8"><title>Michigan precinct snapshots</title><h1>Michigan precinct snapshots — research 2026-10-17</h1><p>Generated previews; separate 2024 baseline and 2026-labeled snapshot. November 2026 approval unverified. See precinct-maps.md and manifest.csv.</p><table><tr><th>County</th><th>2024</th><th>2026</th></tr>']
 for c in counties:
  slug=c['county'].lower().replace('.','').replace(' ','-');index.append('<tr><td>'+html.escape(c['county'])+'</td>'+''.join(f'<td><a href="{y}/{slug}.svg">Map</a> · <a href="{y}/{slug}.geojson">GeoJSON</a></td>' for y in SOURCES)+'</tr>')
 (ROOT/'index.html').write_text('\n'.join(index+['</table>']))
