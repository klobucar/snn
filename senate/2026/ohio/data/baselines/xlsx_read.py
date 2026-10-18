"""Read saved Excel XML using Python stdlib; source coordinates and text retained."""
import zipfile,xml.etree.ElementTree as ET,re
N={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
class Book:
 def __init__(self,path):
  self.z=zipfile.ZipFile(path)
  self.ss=[''.join(t.itertext()) for t in ET.fromstring(self.z.read('xl/sharedStrings.xml')).findall('x:si',N)] if 'xl/sharedStrings.xml' in self.z.namelist() else []
  rels={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))}
  self.sheets={x.attrib['name']:'xl/'+rels[x.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']].lstrip('/') for x in ET.fromstring(self.z.read('xl/workbook.xml')).findall('x:sheets/x:sheet',N)}
 def rows(self,name):
  with self.z.open(self.sheets[name]) as f:
   for event,r in ET.iterparse(f,events=('end',)):
    if r.tag!='{'+N['x']+'}row':continue
    d={}
    for c in r:
     v=c.findtext('x:v','',N)
     if c.attrib.get('t')=='s':v=self.ss[int(v)]
     elif c.attrib.get('t')=='inlineStr':v=''.join(c.find('x:is',N).itertext())
     d[re.sub('[0-9]','',c.attrib['r'])]=v
    yield int(r.attrib['r']),d
    r.clear()
