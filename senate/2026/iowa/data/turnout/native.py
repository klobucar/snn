#!/usr/bin/env python3
"""Read source Excel XML/XLSX directly; preserve sparse cells, native headers and units."""
import csv,gzip,io,json,posixpath,re,zipfile
import xml.etree.ElementTree as E
from collections import Counter,defaultdict
import build as b
S='urn:schemas-microsoft-com:office:spreadsheet'
M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def colnum(s):
    x=0
    for c in s:x=x*26+ord(c)-64
    return x
def number(v):
    if v is None or v=='':return None
    if isinstance(v,(int,float)) and v==int(v):return int(v)
    s=str(v).replace(',','').strip()
    return int(s) if re.fullmatch(r'-?\d+',s) else None
def sheetrows(s):return {r['r']:{c['c']:c['value'] for c in r['cells']} for r in s['rows']}
def readbook(data):
    out=[];meta={}
    if data[:2]==b'PK':
        z=zipfile.ZipFile(io.BytesIO(data));ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():ss=[''.join(t.itertext()) for t in E.fromstring(z.read('xl/sharedStrings.xml'))]
        rs={r.get('Id'):r.get('Target') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        if 'docProps/core.xml' in z.namelist():meta['core_xml']=z.read('docProps/core.xml').decode()
        for ws in E.fromstring(z.read('xl/workbook.xml')).findall('{'+M+'}sheets/{'+M+'}sheet'):
            target=rs[ws.get('{'+REL+'}id')];target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            root=E.fromstring(z.read(target));rows=[]
            for row in root.findall('{'+M+'}sheetData/{'+M+'}row'):
                cells=[]
                for c in row:
                    ref=c.get('r');typ=c.get('t','n');v=c.findtext('{'+M+'}v')
                    if typ=='s':v=ss[int(v)] if v is not None else None
                    elif typ=='inlineStr':v=''.join(c.find('{'+M+'}is').itertext())
                    elif typ=='n' and v is not None:v=number(v) if number(v) is not None else float(v)
                    cells.append(dict(c=colnum(re.match('[A-Z]+',ref).group()),ref=ref,type=typ,value=v,formula=c.findtext('{'+M+'}f')))
                rows.append(dict(r=int(row.get('r')),cells=cells))
            out.append(dict(name=ws.get('name'),sheet_native_id=ws.get('sheetId'),part=target,rows=rows,merges=[c.get('ref') for c in root.findall('{'+M+'}mergeCells/{'+M+'}mergeCell')]))
    else:
        root=E.fromstring(data);dp=root.find('{urn:schemas-microsoft-com:office:office}DocumentProperties')
        if dp is not None:meta['document_properties']={v.tag.split('}')[-1]:v.text for v in dp}
        for ws in root.findall('{'+S+'}Worksheet'):
            table=ws.find('{'+S+'}Table');rows=[];ri=0
            for row in table.findall('{'+S+'}Row'):
                ri=int(row.get('{'+S+'}Index',ri+1));ci=0;cells=[]
                for c in row.findall('{'+S+'}Cell'):
                    ci=int(c.get('{'+S+'}Index',ci+1));d=c.find('{'+S+'}Data');v=d.text if d is not None else None;typ=d.get('{'+S+'}Type') if d is not None else None
                    if typ=='Number' and v is not None:v=number(v) if number(v) is not None else float(v)
                    merge=int(c.get('{'+S+'}MergeAcross',0));cells.append(dict(c=ci,type=typ,value=v,formula=c.get('{'+S+'}Formula'),merge_across=merge,merge_down=int(c.get('{'+S+'}MergeDown',0))));ci+=merge
                rows.append(dict(r=ri,cells=cells))
            out.append(dict(name=ws.get('{'+S+'}Name'),sheet_native_id=None,rows=rows))
    return out,meta

def workbooks():
    votes=[];units=[];regs=[];issues=[];coverage=[];sheetcontext=[]
    for year in [2022,2020]:
        cellpath=b.ROOT/f'workbook-cells-{year}.jsonl.gz'
        with gzip.GzipFile(filename=str(cellpath),mode='wb',mtime=0) as fout:
            for r in b.SOURCES:
                if not (r['id'].startswith(f'sos-{year}-workbook') or (year==2022 and r['id']=='black-hawk-2022-filename-repair')) or r.get('status')!=200:continue
                data=b.raw(r)
                if data.startswith(b'%PDF'):continue
                sheets,meta=readbook(data);county='Black Hawk' if r['id']=='black-hawk-2022-filename-repair' else r['link_label'];assert county in b.COUNTIES,(r['id'],county)
                fips=b.COUNTIES[county]['county_fips'];found=False
                fout.write((json.dumps(dict(source_id=r['id'],county=county,county_fips=fips,metadata=meta,sheets=sheets),ensure_ascii=False,separators=(',',':'))+'\n').encode())
                for s in sheets:
                    rr=sheetrows(s)
                    title=' '.join(str(v) for v in rr.get(1,{}).values() if v)
                    if s['name']=='Registered Voters':
                        headers=rr.get(1,{})
                        for no,row in rr.items():
                            if no==1:continue
                            name=row.get(1)
                            if name is None:continue
                            for col,label in headers.items():
                                if label and col!=1:regs.append(dict(year=year,county=county,county_fips=fips,source_id=r['id'],source_sheet=s['name'],source_row=no,source_column=col,native_unit_label=name,metric=label,value=row.get(col),registration_status='source unspecified; zero may be unpopulated; not election-date registry control'))
                    if 'United States Senator' not in title:continue
                    found=True
                    methods=next(((no,row) for no,row in rr.items() if 'Election Day' in row.values() and 'Absentee' in row.values()),None)
                    assert methods,(r['id'],s['name'])
                    hno,header=methods;names=rr[hno-1]
                    # Each explicit candidate heading starts a 3-column method group.
                    candheads={c:str(v) for c,v in names.items() if v not in [None,''] and c>1}
                    for no,row in rr.items():
                        if no<=hno or not row.get(1):continue
                        name=str(row[1]);kind='source_county_total' if name.strip().lower().startswith('total') else 'native_reporting_row_unclassified'
                        if 'abs' in name.lower() and kind!='source_county_total':kind='absentee_named_reporting_row'
                        uid=f"{r['id']}|{s['name']}|r{no}"
                        units.append(dict(year=year,county=county,county_fips=fips,source_id=r['id'],source_sheet=s['name'],source_row=no,unit_key=uid,native_unit_label=name,native_unit_numeric_id=None,unit_kind=kind,source_contest_title=title,geography_status='historical export row; physical/split/style/polling-place identity not established'))
                        for col,label in header.items():
                            if label in ['Registered Voters','Total']:
                                sheetcontext.append(dict(year=year,county=county,county_fips=fips,source_id=r['id'],source_sheet=s['name'],source_row=no,source_column=col,unit_key=uid,native_unit_label=name,native_metric=label,value=row.get(col),scope='candidate-sheet printed context; Registered Voters zero may be unpopulated; Total sums candidate groups, not ballots'))
                        lasthead=None
                        for col,method in sorted(header.items()):
                            if col in candheads:lasthead=candheads[col]
                            if method not in ['Election Day','Absentee','Total Votes']:continue
                            assert lasthead is not None,(r['id'],col,names)
                            val=number(row.get(col))
                            votes.append(dict(year=year,contest='United States Senator',county=county,county_fips=fips,source_id=r['id'],source_sheet=s['name'],source_row=no,source_column=col,unit_key=uid,native_unit_label=name,unit_kind=kind,native_candidate_label=lasthead,native_method=method,votes=val,raw_cell_value=row.get(col)))
                coverage.append(dict(year=year,county=county,county_fips=fips,source_id=r['id'],senate_sheet_found=found,metadata=meta))
    # Scott's actual linked 2020 county download is a canvass PDF, not a workbook.
    r=b.BYID['sos-2020-workbook-154-scott.pdf'];t=b.pdftext(r);start=t.index('United States Senator');section=t[start:];section=section[:section.index('SCOTT COUNTY ELECTION CANVASS SUMMARY')]
    data=[]
    for no,line in enumerate(section.splitlines(),1):
        clean=re.sub(r'Page\s+\d+\s+of\s+\d+','',line)
        m=re.search(r'((?:\d[\d,]*\s+){7}\d[\d,]*)\s*$',clean)
        if m:data.append((no,clean[:m.start()].strip(),[int(x.replace(',','')) for x in m.group(1).split()]))
    assert len(data)%3==1,len(data)
    for idx,(no,prefix,vals) in enumerate(data):
        aggregate=idx==len(data)-1;method='Total' if aggregate else ['Election Day','Absentee','Total'][idx%3]
        if idx%3==0 and not aggregate:
            name=re.sub(r'\s+Election Day$','',prefix);assert name.startswith('('),name
            uid=f"{r['id']}|Senate|section-line{no}"
            nativeid=re.match(r'\(([^)]+)\)',name).group(1)
            units.append(dict(year=2020,county='Scott',county_fips='19163',source_id=r['id'],source_sheet='Senate PDF section',source_row=no,unit_key=uid,native_unit_label=name,native_unit_numeric_id=nativeid,unit_kind='native_reporting_row_unclassified',source_contest_title='United States Senator',geography_status='historical source label/code; no current crosswalk'))
        if aggregate:
            name='Total';uid=f"{r['id']}|Senate|section-line{no}"
            units.append(dict(year=2020,county='Scott',county_fips='19163',source_id=r['id'],source_sheet='Senate PDF section',source_row=no,unit_key=uid,native_unit_label=name,native_unit_numeric_id=None,unit_kind='source_county_total',source_contest_title='United States Senator',geography_status='administrative aggregate, not a precinct'))
        for col,(label,v) in enumerate(zip(['Theresa Greenfield','Joni Ernst','Rick Stewart','Suzanne Herzog','Write-in','Undervotes','Overvotes','Total'],vals),1):
            votes.append(dict(year=2020,contest='United States Senator',county='Scott',county_fips='19163',source_id=r['id'],source_sheet='Senate PDF section',source_row=no,source_column=col,unit_key=uid,native_unit_label=name,unit_kind='source_county_total' if aggregate else 'native_reporting_row_unclassified',native_candidate_label=label,native_method=method,votes=v,raw_cell_value=v))
    b.csvout('native-unit-candidate-method.csv',votes);b.csvout('native-units.csv',units);b.csvout('native-registration-ballots.csv',regs)
    b.csvout('native-candidate-sheet-context.csv',sheetcontext)
    b.dump('workbook-coverage.json',coverage)
    print('workbooks',len(coverage),'units',len(units),'votes',len(votes))
    return votes,units

if __name__=='__main__':workbooks()
