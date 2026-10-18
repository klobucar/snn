"""Read OOXML cached values independently, without editing the workbooks."""
import gzip, io, posixpath, re, zipfile
from pathlib import Path
from xml.etree import ElementTree as E

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def read(path):
    raw=Path(path).read_bytes()
    if str(path).endswith('.gz'): raw=gzip.decompress(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for item in E.fromstring(z.read('xl/sharedStrings.xml')):
                strings.append(''.join(x.text or '' for x in item.findall('.//s:t',NS)))
        rels={x.get('Id'):x.get('Target') for x in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sheet in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS):
            target=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=[]
            for row in E.fromstring(z.read(target)).findall('.//s:sheetData/s:row',NS):
                values={}; formulas={}
                for cell in row:
                    address=cell.get('r');column=re.sub(r'\d','',address)
                    value=cell.find('s:v',NS)
                    value=value.text if value is not None else None
                    if cell.get('t')=='s' and value is not None: value=strings[int(value)]
                    elif cell.get('t')=='inlineStr': value=''.join(x.text or '' for x in cell.findall('.//s:t',NS))
                    if value is not None: values[column]=value
                    formula=cell.find('s:f',NS)
                    if formula is not None:formulas[column]=formula.text
                if values:rows.append(dict(row=int(row.get('r')),values=values,formulas=formulas))
            sheets[sheet.get('name')]=rows
        return sheets
