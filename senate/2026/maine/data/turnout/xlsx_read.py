"""Small read-only OOXML extractor; retains Excel row/column addresses and caches.
No spreadsheet libraries or recalculation. Handles shared and inline strings.
"""
import gzip, io, posixpath, zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
   'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def read(path):
    b=Path(path).read_bytes()
    if str(path).endswith('.gz'): b=gzip.decompress(b)
    z=zipfile.ZipFile(io.BytesIO(b))
    shared=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        shared=[''.join(t.text or '' for t in s.findall('.//m:t',N)) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',N)]
    rel={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    sheets={}
    for s in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',N):
        target=rel[s.attrib['{'+N['r']+'}id']]
        name=posixpath.normpath('xl/'+target) if not target.startswith('/') else target.lstrip('/')
        rows=[]
        for row in ET.fromstring(z.read(name)).findall('m:sheetData/m:row',N):
            cells={}
            for c in row.findall('m:c',N):
                v=c.find('m:v',N); val=v.text if v is not None else None
                if c.attrib.get('t')=='s' and val is not None:val=shared[int(val)]
                elif c.attrib.get('t')=='inlineStr': val=''.join(t.text or '' for t in c.findall('.//m:t',N))
                if val is not None:cells[c.attrib['r']]=val
            if cells:rows.append({'row':int(row.attrib['r']),'cells':cells})
        sheets[s.attrib['name']]=rows
    return sheets
