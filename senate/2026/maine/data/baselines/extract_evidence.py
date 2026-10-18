#!/usr/bin/env python3
"""Reproduce searchable primary-PDF text and basic HTML text derivatives."""
import gzip, html, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
(ROOT/'extracted').mkdir(exist_ok=True)
for m in json.loads((ROOT/'manifest.json').read_text()):
    path=ROOT/m['saved_path']
    body=gzip.decompress(path.read_bytes())
    if body.startswith(b'%PDF'):
        result=subprocess.run(['pdftotext','-layout','-','-'],input=body,stdout=subprocess.PIPE,check=True)
        (ROOT/'extracted'/(m['source_id']+'.txt')).write_bytes(result.stdout)
    elif str(path).endswith('.html.gz'):
        s=body.decode('utf-8',errors='replace')
        s=re.sub('<script.*?</script>|<style.*?</style>','',s,flags=re.S)
        s=re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s)))
        (ROOT/'extracted'/(m['source_id']+'.txt')).write_text(s+'\n')
print('PDF/HTML text derivatives rebuilt; scanned rule PDF has no usable text, current statute controls.')
