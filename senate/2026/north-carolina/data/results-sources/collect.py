#!/usr/bin/env python3
"""Bounded public-source capture. No guessed election IDs; explicit URL inputs only.

python3 collect.py source_id URL [source_id URL ...]
Existing source IDs are immutable unless --refresh is supplied. Response bodies
are decoded by curl --compressed and then losslessly gzip-compressed for storage.
"""
import concurrent.futures
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
CAP = 8 * 1024 * 1024

class Page(HTMLParser):
    def __init__(self, url):
        super().__init__(); self.url=url; self.links=[]; self.text=[]; self.suppress=0; self.anchor=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag in ('script','style'): self.suppress+=1
        for key in ('href','src'):
            if a.get(key):
                obj={'tag':tag,'url':urljoin(self.url,a[key]),'label':a.get('title','')}
                self.links.append(obj)
                if tag=='a': self.anchor=obj
    def handle_endtag(self, tag):
        if tag in ('script','style'): self.suppress=max(0,self.suppress-1)
        if tag=='a': self.anchor=None
    def handle_data(self, data):
        s=' '.join(data.split())
        if s and not self.suppress: self.text.append(s)
        if s and self.anchor is not None: self.anchor['label']+=' '+s

def fetch(source_id, url, refresh=False, byte_range=None):
    assert re.fullmatch(r'[a-zA-Z0-9_-]+',source_id)
    meta=ROOT/(source_id+'.meta.json')
    if meta.exists() and not refresh: return json.loads(meta.read_text())
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    # Temporary files are confined to this assignment's evidence directory.
    body=ROOT/(source_id+'.capture'); headers=ROOT/(source_id+'.headers')
    command=['curl','--silent','--show-error','--location','--compressed',
        '--max-time','45','--max-filesize',str(CAP),'-A','Mozilla/5.0 (NC public election research)',
        '-D',str(headers),'-o',str(body),'-w','%{json}']
    if byte_range:command+=['--range',byte_range]
    p=subprocess.run(command+[url],capture_output=True)
    try: transfer=json.loads(p.stdout)
    except Exception: transfer={'curl_output':p.stdout.decode(errors='replace')}
    data=body.read_bytes() if body.exists() else b''
    saved=source_id+'.body.gz'; (ROOT/saved).write_bytes(gzip.compress(data,mtime=0))
    body.unlink(missing_ok=True)
    m={'source_id':source_id,'url':url,'final_url':transfer.get('url_effective',url),
       'retrieval_started_utc':start,'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'http_status':transfer.get('http_code'),'curl_exit':p.returncode,'error':p.stderr.decode(errors='replace'),
       'content_type':transfer.get('content_type'),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
       'saved_file':saved,'headers_file':headers.name,'complete':p.returncode==0,
       'storage':'curl --compressed response bytes; lossless gzip; hash is decompressed body',
       'cap_bytes':CAP}
    if byte_range:m.update(requested_range=byte_range,full_resource=False)
    meta.write_text(json.dumps(m,indent=2)+'\n')
    if 'html' in (m['content_type'] or ''):
        parser=Page(m['final_url']);parser.feed(data.decode('utf-8',errors='replace'))
        (ROOT/(source_id+'.page.json')).write_text(json.dumps({'source_id':source_id,
            'text':'\n'.join(parser.text),'links':parser.links},indent=2)+'\n')
    return m

def batch(items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for m in pool.map(lambda t:fetch(*t),items):
            print(m['source_id'],m['http_status'],m['bytes'],m['curl_exit'],flush=True)

if __name__=='__main__':
    args=sys.argv[1:]; refresh='--refresh' in args
    if refresh:args.remove('--refresh')
    if len(args)%2:raise SystemExit(__doc__)
    if refresh:
        for k,u in zip(args[::2],args[1::2]): print(fetch(k,u,True))
    else:batch(list(zip(args[::2],args[1::2])))
