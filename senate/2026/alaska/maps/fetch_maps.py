"""Acquire observed official map URLs with system curl and normal TLS validation.

Default: use retained bytes; --refresh replaces snapshots, so archive them first.
All writes stay under this script's maps directory. No credentials or live polling.
"""
from pathlib import Path
import argparse
import datetime as dt
import gzip
import hashlib
from html.parser import HTMLParser
import json
import subprocess
import tempfile
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent
def sha(b): return hashlib.sha256(b).hexdigest()
def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()
def fetch(url, name, refresh=False):
    target = ROOT / name
    meta = target.with_name(target.name + '.retrieval.json')
    if meta.exists() and not refresh:
        m = json.loads(meta.read_text())
        return gzip.decompress(target.read_bytes()) if name.endswith('.gz') else target.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    headers = target.with_name(target.name + '.headers')
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / 'body'
        start = utc()
        r = subprocess.run(['/usr/bin/curl', '--location', '--silent', '--show-error',
            '--connect-timeout', '25', '--max-time', '180', '--dump-header', str(headers),
            '--output', str(raw), '--write-out', '%{json}', url], capture_output=True, text=True)
        b = raw.read_bytes() if raw.exists() else b''
        stored = gzip.compress(b, mtime=0) if name.endswith('.gz') else b
        target.write_bytes(stored)
        try: stats = json.loads(r.stdout)
        except ValueError: stats = {'raw_write_out': r.stdout}
        m = dict(source_url=url, started_utc=start, retrieved_utc=utc(),
            curl_exit_code=r.returncode, stderr=r.stderr, curl=stats,
            tls_validation='system curl default certificate validation; no insecure flag',
            raw_bytes=len(b), raw_sha256=sha(b), stored_bytes=len(stored),
            stored_sha256=sha(stored), local_path=name,
            headers_path=str(headers.relative_to(ROOT)), headers_sha256=sha(headers.read_bytes()))
        meta.write_text(json.dumps(m, indent=2)+'\n')
        print(stats.get('http_code'), len(b), name, flush=True)
        return b

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.urls=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            d=dict(attrs)
            if 'href' in d: self.urls.append(d['href'])

def main():
    a=argparse.ArgumentParser(); a.add_argument('--refresh', action='store_true'); args=a.parse_args()
    landing='https://www.elections.alaska.gov/research/district-maps/'
    body=fetch(landing, 'raw/district-maps.html.gz', args.refresh)
    p=Links(); p.feed(body.decode())
    urls=[urljoin(landing,u) for u in p.urls]
    priority=json.loads((STATE/'data/turnout/priority-set.json').read_text())
    # Required acquisition order follows the reconciled baseline, never county names.
    for d in priority['districts']:
        u=d['map_source_url']
        assert u in urls, ('dispatch URL absent from current primary landing',u)
        fetch(u, 'originals/'+u.rsplit('/',1)[1], args.refresh)
    z=[u for u in urls if u.endswith('.zip') and 'Precinct' in u]
    assert len(z)==1, z
    fetch(z[0], 'originals/'+z[0].rsplit('/',1)[1], args.refresh)
    (ROOT/'observed-map-links.json').write_text(json.dumps(urls,indent=2)+'\n')

if __name__=='__main__': main()
