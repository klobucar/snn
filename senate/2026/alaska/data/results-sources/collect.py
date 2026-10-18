#!/usr/bin/env python3
"""Bounded primary-source retrieval; system curl keeps default TLS verification.
Usage: python3 collect.py ID URL [PARENT_ID]. No discovery by guessed URL.
Bodies are losslessly gzip-compressed; HTML-derived links/text are separate.
"""
import datetime,gzip,hashlib,html.parser,json,pathlib,subprocess,sys,tempfile,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parent
LIMIT=20*1024*1024
class Page(html.parser.HTMLParser):
 def __init__(self,base):
  super().__init__(); self.base=base; self.links=[]; self.text=[]; self.skip=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ('script','style'): self.skip+=1
  for attr in ('href','src','action'):
   if a.get(attr): self.links.append({'tag':tag,'attribute':attr,'url':urllib.parse.urljoin(self.base,a[attr])})
  if tag=='option' and a.get('value','').startswith(('http://','https://')):
   self.links.append({'tag':tag,'attribute':'value','url':a['value']})
 def handle_endtag(self,tag):
  if tag in ('script','style'): self.skip=max(0,self.skip-1)
 def handle_data(self,s):
  if not self.skip and s.strip(): self.text.append(s.strip())
def fetch(key,url,parent=None):
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with tempfile.TemporaryDirectory() as td:
  body=pathlib.Path(td)/'body'; headers=pathlib.Path(td)/'headers'
  args=['/usr/bin/curl','--location','--silent','--show-error','--connect-timeout','15','--max-time','45','--max-filesize',str(LIMIT),'--dump-header',str(headers),'--output',str(body),'--write-out','%{json}',url]
  r=subprocess.run(args,capture_output=True)
  raw=body.read_bytes() if body.exists() else b''
  assert len(raw)<=LIMIT
  h=headers.read_bytes() if headers.exists() else b''
  # Keep HTTP headers and transport errors; not a TLS bypass.
  (ROOT/(key+'.headers')).write_bytes(h)
  try: curl=json.loads(r.stdout)
  except ValueError: curl={'unparsed_stdout':r.stdout.decode(errors='replace')}
  asset=key+'.body.gz'; (ROOT/asset).write_bytes(gzip.compress(raw,mtime=0))
  m={'id':key,'url':url,'parent_id':parent,'retrieved_utc':start,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'transport':'/usr/bin/curl; default TLS verification','curl_exit':r.returncode,'stderr':r.stderr.decode(errors='replace'),'http_status':curl.get('http_code'),'effective_url':curl.get('url_effective'),'content_type':curl.get('content_type'),'bytes':len(raw),'raw_sha256':hashlib.sha256(raw).hexdigest(),'asset':asset,'stored_sha256':hashlib.sha256((ROOT/asset).read_bytes()).hexdigest(),'headers':key+'.headers','headers_sha256':hashlib.sha256(h).hexdigest(),'curl_metadata':curl,'complete':r.returncode==0}
  if 'html' in (m['content_type'] or '') and raw:
   p=Page(m['effective_url'] or url); p.feed(raw.decode(errors='replace'))
   (ROOT/(key+'.links.json')).write_text(json.dumps(p.links,indent=2)+'\n')
   (ROOT/(key+'.txt')).write_text('\n'.join(p.text)+'\n')
  (ROOT/(key+'.meta.json')).write_text(json.dumps(m,indent=2)+'\n')
  print(key,m['http_status'],len(raw),m['effective_url'],m['curl_exit'])
  return m
if __name__=='__main__': fetch(*sys.argv[1:])
