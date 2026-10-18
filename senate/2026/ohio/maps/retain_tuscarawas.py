from fetch_maps import *
d=json.loads((ROOT/'last-alternatives.json').read_text())['tusc-old-cdx']['data'];rows=[dict(zip(d[0],r)) for r in d[1:]]
def work(r):
 u='https://web.archive.org/web/'+r['timestamp']+'if_/'+r['original'];label=r['original'].rsplit('/',1)[-1];m,b=fetch('pdf/tuscarawas-2016/'+label.replace('.pdf',''),u,raw=True)
 print(label,m['status'],len(b),b[:4].decode(errors='replace'),flush=True)
 return dict(county='tuscarawas',label=label+' (2016 historical capture)',url=u,original_url=r['original'],landing='https://gis.co.tuscarawas.oh.us/arcgis/rest/services/CountyWebServices/BOE_Precints/MapServer/0',archive_timestamp=r['timestamp'],vintage='historical official BOE individual precinct map; 2016 archive capture, not 2026 approval',path=m['stored_path'],status=m['status'],is_pdf=b.startswith(b'%PDF'),sha256=m['sha256'])
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:out=list(ex.map(work,rows))
p=ROOT/'documents.json';D=json.loads(p.read_text());known={x['url'] for x in D};D.extend(x for x in out if x['url'] not in known);p.write_text(json.dumps(D,indent=2)+'\n');(ROOT/'tuscarawas-historical-selection.json').write_text(json.dumps(out,indent=2)+'\n')
