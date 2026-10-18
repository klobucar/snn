#!/usr/bin/env python3
"""Bounded public evidence retrieval; cached originals are gzip-compressed losslessly.

Usage: collect.py ID URL [DISCOVERED_FROM]. No guessed endpoints are generated.
Each request uses curl default certificate verification, 12s connect / 40s total,
16 MiB body limit, at most six redirects. Re-running an ID preserves its snapshot.
"""
import concurrent.futures, datetime, gzip, hashlib, html, json, pathlib, re, subprocess, sys
from html.parser import HTMLParser
from urllib.parse import urljoin
ROOT = pathlib.Path(__file__).resolve().parent
def digest(b): return hashlib.sha256(b).hexdigest()
def save_json(p, d): p.write_text(json.dumps(d, indent=2, ensure_ascii=False)+'\n')
class Parse(HTMLParser):
    def __init__(self, base):
        super().__init__(); self.base=base; self.links=[]; self.text=[]; self.tag=None; self.attrs=None; self.buf=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='base' and a.get('href'): self.base=urljoin(self.base,a['href'])
        if tag in ('script','style'): self.skip+=1
        if tag in ('a','iframe','script','link'):
            u=a.get('href') or a.get('src')
            if u:
                item={'tag':tag,'url':urljoin(self.base,html.unescape(u)),'text':''}; self.links.append(item)
                if tag=='a': self.tag=item; self.buf=[]
        if tag in ('br','p','div','li','tr','h1','h2','h3','h4','h5'): self.text.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.skip=max(0,self.skip-1)
        if tag=='a' and self.tag is not None: self.tag['text']=' '.join(' '.join(self.buf).split()); self.tag=None
    def handle_data(self,d):
        if not self.skip: self.text.append(d+' ')
        if self.tag is not None: self.buf.append(d)
def fetch(key,url,parent='',refresh=False):
    assert re.fullmatch(r'[a-z0-9_-]+',key)
    mp=ROOT/(key+'.meta.json')
    if mp.exists() and not refresh: return json.loads(mp.read_text())
    raw=ROOT/(key+'.download'); hp=ROOT/(key+'.headers')
    start=datetime.datetime.now(datetime.timezone.utc).isoformat()
    cmd=['/usr/bin/curl','--silent','--show-error','--location','--max-redirs','6','--connect-timeout','12','--max-time','40','--max-filesize','16777216','--compressed','--dump-header',str(hp),'--output',str(raw),'--write-out','%{json}',url]
    p=subprocess.run(cmd,capture_output=True)
    try: transport=json.loads(p.stdout)
    except Exception: transport={'stdout':p.stdout.decode(errors='replace')}
    b=raw.read_bytes() if raw.exists() else b''
    raw.unlink(missing_ok=True)
    stored=gzip.compress(b,mtime=0); (ROOT/(key+'.body.gz')).write_bytes(stored)
    end=datetime.datetime.now(datetime.timezone.utc).isoformat()
    m={'id':key,'requested_url':url,'discovered_from':parent,'retrieval_started_utc':start,'retrieved_utc':end,'curl_exit':p.returncode,'error':p.stderr.decode(errors='replace'),'transport':transport,'original_bytes':len(b),'original_sha256':digest(b),'stored_sha256':digest(stored),'body':key+'.body.gz','headers':key+'.headers','complete_transport':p.returncode==0,'sample_policy':'Whole response; 16MiB limit. Nonzero curl exit means incomplete/failed, excluded from counts.'}
    typ=transport.get('content_type','') or ''
    if 'html' in typ or b.lstrip().lower().startswith((b'<!doctype html',b'<html')):
        parser=Parse(transport.get('url_effective',url)); parser.feed(b.decode('utf-8',errors='replace'))
        save_json(ROOT/(key+'.links.json'),parser.links)
        (ROOT/(key+'.txt')).write_text('\n'.join(' '.join(x.split()) for x in ''.join(parser.text).splitlines() if x.strip())+'\n')
    elif b.startswith(b'%PDF'):
        temp=ROOT/(key+'.pdf'); temp.write_bytes(b)
        proc=subprocess.run(['pdftotext','-layout',str(temp),str(ROOT/(key+'.txt'))],capture_output=True)
        m['pdftotext_exit']=proc.returncode; temp.unlink()
    elif len(b)<1200000:
        try: (ROOT/(key+'.txt')).write_text(b.decode('utf-8'))
        except UnicodeDecodeError: pass
    save_json(mp,m); return m
def batch(items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda x:fetch(*x),items))
    for m in results:
        print(m['id'],m['transport'].get('http_code'),m['original_bytes'],m['curl_exit'])
    return results
if __name__=='__main__':
    if len(sys.argv)>2: batch([sys.argv[1:]])
    else: raise SystemExit('collect.py ID URL [DISCOVERED_FROM]')
