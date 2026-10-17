"""Save small public samples plus HTTP headers and checksums. Explicit URLs only."""
import subprocess,hashlib,json,datetime,sys
from pathlib import Path
P=Path(__file__).resolve().parent
for name,url in [x.split('=',1) for x in sys.argv[1:]]:
 p=P/name;h=P/(name+'.headers');r=subprocess.run(['curl','-LsS','-A','Mozilla/5.0','--max-time','25','--max-filesize','2500000','-D',str(h),'-o',str(p),'-w','%{http_code}\n%{url_effective}',url],capture_output=True)
 meta={'url':url,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'curl_exit':r.returncode,'status_final_url':r.stdout.decode(),'error':r.stderr.decode()}
 if p.exists():meta.update(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 (P/(name+'.meta.json')).write_text(json.dumps(meta,indent=2));print(name,r.stdout.decode())
