#!/usr/bin/env python3
"""Rebuild text evidence from preserved PDF bytes; Poppler required.

Selected scanned Union warden returns also rendered to retained PNGs, inspected
visually. Other PDFs are controls/source-context rather than authored outputs.
"""
import gzip,json,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
for source in json.loads((ROOT/'manifest.json').read_text()):
    path=ROOT/source['saved_path']
    if source['http_status']!=200 or not path.name.endswith('.pdf.gz'):continue
    data=gzip.decompress(path.read_bytes())
    result=subprocess.run(['pdftotext','-layout','-','-'],input=data,capture_output=True,check=True)
    (ROOT/'extracted'/(source['source_id']+'.txt')).write_bytes(result.stdout)
    if source['source_id'] in ['union-2024-local','union-2022-local']:
        with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
            f.write(data);f.flush()
            subprocess.run(['pdftoppm','-r','125','-png','-singlefile',f.name,str(ROOT/'extracted'/source['source_id'])],check=True)
