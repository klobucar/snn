#!/usr/bin/env python3
"""Independent coordinator OOXML cached-cell comparison of retained official vintages."""
from pathlib import Path
from collections import Counter
import datetime, gzip, hashlib, io, json, zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def workbook(rel):
    raw=gzip.decompress((ROOT/rel).read_bytes())
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        wb=ET.fromstring(z.read('xl/workbook.xml'));rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        links={e.get('Id'):e.get('Target') for e in rels};sheets={}
        for sheet in wb.findall('s:sheets/s:sheet',NS):
            target=links[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            path=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            cells={}
            for c in ET.fromstring(z.read(path)).findall('.//s:c',NS):
                val=c.find('s:v',NS);value=val.text if val is not None else None
                if c.get('t')=='s' and value is not None:value=strings[int(value)]
                if c.get('t')=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
                if value is not None:cells[c.get('r')]=value
            sheets[sheet.get('name')]=cells
        props=ET.fromstring(z.read('docProps/core.xml'))
        clocks={e.tag.split('}')[-1]:e.text for e in props if e.tag.split('}')[-1] in ('created','modified')}
    return sheets,{'path':rel,'original_sha256':hashlib.sha256(raw).hexdigest(),'document_clocks':clocks}

comparisons=[]
for contest,letter,unitrow,categories,old,new in [
    ('senate','b',517,['C','D','E','F','G','H'],[69,219,746,714,328,2076],[40,203,985,810,38,2076]),
    ('president','a',518,['C','D','E','F','G','H','I','J'],[680,31,23,891,39,0,412,2076],[981,13,17,1031,8,0,26,2076])]:
    before,bmeta=workbook(f'baselines/raw/legislature-2024-{letter}.xlsx.gz')
    after,ameta=workbook(f'baselines/raw/{contest}-2024.xlsx.gz')
    assert set(before)==set(after)
    changes=[]
    for sheet in before:
        b,a=before[sheet],after[sheet]
        for cell in sorted(set(b)|set(a)):
            if b.get(cell)!=a.get(cell):changes.append({'sheet':sheet,'cell':cell,'old':b.get(cell),'current':a.get(cell)})
    # The native main sheet is independently identified by the Alfred label.
    main=next(s for s,c in after.items() if c.get('B'+str(unitrow))=='Alfred')
    b,a=before[main],after[main]
    assert b['A'+str(unitrow)]==a['A'+str(unitrow)]=='YOR'
    assert [int(b[c+str(unitrow)]) for c in categories]==old
    assert [int(a[c+str(unitrow)]) for c in categories]==new
    changedrows=Counter(int(''.join(filter(str.isdigit,r['cell']))) for r in changes if r['sheet']==main)
    # Alfred is the only changed disjoint native-unit row; other changes are footers.
    native=__import__('csv').DictReader((ROOT/'county-baselines.csv').open())
    unitrows={int(r['source_row']) for r in native if r['source_id']==contest+'-2024'}
    assert set(changedrows)&unitrows=={unitrow}
    comparisons.append({'contest':contest,'archive':bmeta,'current':ameta,'changed_cells':changes,'changed_main_rows':{str(k):v for k,v in changedrows.items()},
                        'only_changed_disjoint_unit':'Alfred / YOR','native_row':unitrow,
                        'candidate_delta':sum(new[:-2])-sum(old[:-2]),'blank_delta':new[-2]-old[-2],'tbc_delta':new[-1]-old[-1]})
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'comparisons':comparisons,
        'scope':'cached cell values, native row identity and file hashes; no modification/release chronology inferred',
        'cause_and_publication_timing':'unresolved; document modified clocks alone do not establish a causal sequence'}
output=ROOT/'coordinator-vintage-review.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='comparisons'},indent=2))
for r in comparisons:print(r['contest'],r['changed_main_rows'],r['candidate_delta'],r['blank_delta'],r['tbc_delta'])
