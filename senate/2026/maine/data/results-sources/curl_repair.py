from research import *
import subprocess
# macOS SecureTransport CA trust is an independent verified-TLS retrieval route.
# Never use --insecure. Retain the earlier Python TLS failures as separate records.
def curl_fetch(url):
 id=digest(url.encode())[:20]+'-curl';tmp=ROOT/f'.{id}.tmp';head=ROOT/f'.{id}.headers.tmp'
 t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 r=subprocess.run(['curl','--location','--max-redirs','10','--max-time','30','--max-filesize',str(MAX),'--silent','--show-error','--user-agent','Maine-public-election-research/1.0','--dump-header',str(head),'--output',str(tmp),'--write-out','%{json}',url],capture_output=True)
 try:info=json.loads(r.stdout)
 except Exception:info={}
 b=tmp.read_bytes() if tmp.exists() else b'';h=head.read_text(errors='replace') if head.exists() else '';blob=gzip.compress(b,mtime=0);obj=ROOT/'objects'/f'{digest(b)}.gz'
 if not obj.exists():obj.write_bytes(blob)
 m={'id':id,'publisher_url':url,'request_url':url,'retrieved_utc':t,'transport':'curl macOS SecureTransport; TLS verification enabled','status':info.get('http_code'),'final_url':info.get('url_effective',url),'curl_exit':r.returncode,'curl_stderr':r.stderr.decode(errors='replace'),'curl_metadata':info,'headers_raw':h,'headers':[],'redirects':'see original complete header blocks','complete':r.returncode==0,'entity_bytes_retained':len(b),'entity_sha256':digest(b),'body_path':str(obj.relative_to(ROOT)),'saved_sha256':digest(obj.read_bytes()),'saved_bytes':obj.stat().st_size,'max_entity_bytes':MAX}
 # Last response header block; full header chain retained separately above.
 blocks=re.split(r'\r?\n\r?\n',h.strip());last=next((x for x in reversed(blocks) if x.startswith('HTTP/')),'')
 m['headers']=[line.split(': ',1) for line in last.splitlines()[1:] if ': ' in line]
 (ROOT/'requests'/f'{id}.json').write_text(json.dumps(m,indent=2)+'\n')
 for f in [tmp,head]:
  if f.exists():f.unlink()
 return m
if __name__=='__main__':
 for u in sys.argv[1:]:
  m=curl_fetch(u);print(m['id'],m.get('status'),m['entity_bytes_retained'],m['curl_exit'],flush=True)
