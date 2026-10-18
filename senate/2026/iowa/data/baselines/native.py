#!/usr/bin/env python3
"""Independent stdlib XML/XLSX cell extraction, with source row identity intact."""
import collections, io, json, posixpath, re, zipfile
import xml.etree.ElementTree as E
from common import *
S='urn:schemas-microsoft-com:office:spreadsheet'
def ncol(s):
    n=0
    for c in s:n=n*26+ord(c)-64
    return n
def sheets(b):
    if b[:2]==b'PK':
        z=zipfile.ZipFile(io.BytesIO(b));ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            ss=[''.join(t.text or '' for t in e.findall('.//{*}t')) for e in E.fromstring(z.read('xl/sharedStrings.xml'))]
        rels={e.get('Id'):e.get('Target') for e in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        for sheet in E.fromstring(z.read('xl/workbook.xml')).findall('.//{*}sheet'):
            target=rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]
            name=posixpath.normpath('xl/'+target) if not target.startswith('/') else target.lstrip('/')
            root=E.fromstring(z.read(name));rows=[]
            for row in root.findall('.//{*}sheetData/{*}row'):
                cells=[]
                for c in row:
                    v=c.find('{*}v');v=v.text if v is not None else ''
                    if c.get('t')=='s':value=ss[int(v)]
                    elif c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//{*}t'))
                    else:value=v
                    cells.append({'column':ncol(re.match('[A-Z]+',c.get('r'))[0]),'address':c.get('r'),'value':value,'attributes':c.attrib,'formula':c.findtext('{*}f')})
                rows.append({'row':int(row.get('r')),'cells':cells})
            yield sheet.get('name'),rows
    else:
        root=E.fromstring(b)
        for sheet in root.findall(f'{{{S}}}Worksheet'):
            rows=[];ri=0
            for row in sheet.findall(f'{{{S}}}Table/{{{S}}}Row'):
                ri=int(row.get(f'{{{S}}}Index',ri+1));ci=0;cells=[]
                for c in row:
                    ci=int(c.get(f'{{{S}}}Index',ci+1));d=c.find(f'{{{S}}}Data')
                    cells.append({'column':ci,'address':'R'+str(ri)+'C'+str(ci),'value':''.join(d.itertext()) if d is not None else '', 'attributes':c.attrib,'formula':c.get(f'{{{S}}}Formula')})
                    ci+=int(c.get(f'{{{S}}}MergeAcross',0))
                rows.append({'row':ri,'cells':cells})
            yield sheet.get(f'{{{S}}}Name'),rows
def integer(v):
    if v is None:return None
    s=str(v).strip().replace(',','')
    return int(s) if re.fullmatch(r'-?\d+',s) else None
def main():
    fmap=fipsmap();units=[];votes=[];reg=[];coverage=[]
    for meta in sources():
        if not ('workbook-' in meta['id'] or meta['id']=='black-hawk-2022-filename-repair'):continue
        year=2022 if '2022' in meta['id'] else 2020
        county='Black Hawk' if meta['id']=='black-hawk-2022-filename-repair' else meta['link_label'].strip()
        county=re.sub(r'\s+',' ',county).replace(' (PDF)','').replace(' (Excel)','')
        b=raw(meta)
        if meta['status']!=200:
            coverage.append({'source_id':meta['id'],'year':year,'county':county,'county_fips':fmap.get(county,''),'status':meta['status'],'scope':'failed exact linked alternative; retained; never zero-filled','unit_rows':0});continue
        if b.startswith(b'%PDF'):
            text=pdftext(b);gzwrite('text/'+meta['id']+'.txt.gz',text.encode())
            # Scott Senator pages 11-16 are the complete text table; later pages
            # include scanned unrelated contests. Scope is checked by header.
            pages=text.split('\f');sen=[(i+1,t) for i,t in enumerate(pages) if 'Theresa Greenfield,' in t and 'Joni Ernst,' in t]
            native=None;idx=0;labels=['Theresa Greenfield','Joni Ernst','Rick Stewart','Suzanne Herzog','Write-in','Under Votes','Over Votes','Total']
            section_lines=collections.defaultdict(list)
            for sli,sline in enumerate(text.split('United States Senator',1)[1].splitlines(),1):section_lines[sline].append(sli)
            for page,t in sen:
                for ln,line in enumerate(t.splitlines(),1):
                    clean=re.sub(r'Page\s+\d+\s+of\s+\d+.*$','',line)
                    vals=list(re.finditer(r'(?<!\S)\d[\d,]*(?!\S)',clean))
                    if len(vals)!=8:continue
                    prefix=clean[:vals[0].start()].strip();mt=re.search(r'(Election Day|Absentee|Total)\s*$',prefix)
                    if not mt:continue
                    method=mt[1];label=prefix[:mt.start()].strip()
                    if label:native=label;idx+=1
                    elif method=='Total' and units and units[-1]['native_unit_label']==native and any(v['source_id']==meta['id'] and v['native_unit_label']==native and v['native_method']=='Total' for v in votes):native='Total:'
                    section_line=section_lines[line].pop(0)
                    key=f"{meta['id']}/table/{idx}" if native!='Total:' else f"{meta['id']}/county-total"
                    if not any(u['unit_key']==key for u in units):
                        code=re.match(r'^\(([^)]+)\)',native)
                        units.append({'year':year,'county':county,'county_fips':fmap[county],'source_id':meta['id'],'sheet':'Senator PDF pages 11-16','source_row':section_line,'native_unit_label':native,'native_unit_numeric_id':code[1] if code else '', 'unit_key':key,'row_scope':'county total' if native=='Total:' else 'native reporting label; physical/split status unverified','source_page':page})
                    for col,(lab,m) in enumerate(zip(labels,vals),1):
                        votes.append({'year':year,'county':county,'county_fips':fmap[county],'source_id':meta['id'],'sheet':'Senator PDF pages 11-16','source_row':section_line,'source_column':col,'unit_key':key,'native_unit_label':native,'native_candidate_label':lab,'native_method':method,'metric':'candidate_votes' if col<=5 else ['undervotes','overvotes','reported_total'][col-6],'votes':integer(m[0]),'source_page':page,'raw_line':line})
            coverage.append({'source_id':meta['id'],'year':year,'county':county,'county_fips':fmap[county],'status':200,'scope':'complete Senate table; PDF native reporting labels','unit_rows':idx});continue
        allrows=[];n=0
        for sheet,rows in sheets(b):
            for row in rows:allrows.append({'source_id':meta['id'],'sheet':sheet,**row})
            grid={row['row']:{c['column']:c['value'] for c in row['cells']} for row in rows}
            if sheet=='Registered Voters':
                for ri,cells in grid.items():
                    if ri<=1:continue
                    for col,value in cells.items():
                        if col==1:continue
                        reg.append({'year':year,'county':county,'county_fips':fmap[county],'source_id':meta['id'],'sheet':sheet,'source_row':ri,'source_column':col,'native_unit_label':cells.get(1,''),'metric':grid.get(1,{}).get(col,''),'value':value,'scope':'source Registered Voters sheet; printed zero may be unpopulated'})
            if not any('United States Senator' in str(v) for v in grid.get(1,{}).values()):continue
            headers=grid.get(2,{});methods=grid.get(3,{})
            current='';column_labels={}
            for col in range(1,max(methods)+1):
                if str(headers.get(col,'')).strip():current=headers[col]
                column_labels[col]=current
            for ri,cells in grid.items():
                if ri<=3:continue
                native=cells.get(1,'');key=f"{meta['id']}/{sheet}/{ri}";n+=native!='Total:'
                units.append({'year':year,'county':county,'county_fips':fmap[county],'source_id':meta['id'],'sheet':sheet,'source_row':ri,'native_unit_label':native,'native_unit_numeric_id':'','unit_key':key,'row_scope':'county total' if native=='Total:' else 'native reporting label; physical/split status unverified','source_page':''})
                for col,value in cells.items():
                    if col==1:continue
                    method=methods.get(col,'');candidate=column_labels.get(col,'')
                    if method in ['Election Day','Absentee','Total Votes'] and candidate:metric='candidate_votes'
                    elif method=='Registered Voters':metric='registered_voters';candidate=''
                    elif method=='Total':metric='candidate_sheet_total';candidate=''
                    else:metric='unclassified_source_cell'
                    votes.append({'year':year,'county':county,'county_fips':fmap[county],'source_id':meta['id'],'sheet':sheet,'source_row':ri,'source_column':col,'unit_key':key,'native_unit_label':native,'native_candidate_label':candidate,'native_method':method,'metric':metric,'votes':integer(value),'source_page':'','raw_line':''})
        gzwrite('cells/'+meta['id']+'.jsonl.gz',('\n'.join(json.dumps(x,ensure_ascii=False) for x in allrows)+'\n').encode())
        coverage.append({'source_id':meta['id'],'year':year,'county':county,'county_fips':fmap[county],'status':200,'scope':'all workbook sheets/cells retained; Senate and registration normalized','unit_rows':n})
    csvout('native-units.csv',units);csvout('native-candidate-method.csv',votes);csvout('native-registration-ballots.csv',reg);csvout('native-coverage.csv',coverage)
    # Reconcile every native candidate/method aggregation and printed footer to
    # the primary statewide county table. Preserve disagreements as data.
    primary={(r['year'],r['county_fips'],r['candidate_or_metric_label'],r['native_method']):int(r['votes']) for r in records('canvass-candidate-method.csv') if r['county']!='STATE'}
    groups=collections.defaultdict(list)
    for v in votes:
        if v['metric'] not in ['candidate_votes','undervotes','overvotes','reported_total']:continue
        method='Total' if v['native_method']=='Total Votes' else v['native_method']
        groups[(v['year'],v['county_fips'],v['source_id'],v['native_candidate_label'],method)].append(v)
    checks=[]
    for (year,fips,sid,label,method),vs in groups.items():
        pool=[v for v in vs if v['native_unit_label']!='Total:'];footer=[v for v in vs if v['native_unit_label']=='Total:']
        total=sum(v['votes'] for v in pool if v['votes'] is not None);target=primary.get((str(year),fips,label,method));foot=footer[0]['votes'] if len(footer)==1 else None
        checks.append({'year':year,'county_fips':fips,'source_id':sid,'candidate_or_metric_label':label,'native_method':method,'native_row_sum':total,'native_footer':foot,'primary_county_control':target,'sum_minus_primary':total-target if target is not None else None,'footer_minus_primary':foot-target if foot is not None and target is not None else None,'scope':'no rescaling/deduplication/residual allocation'})
    csvout('native-checks.csv',checks)
    print('Native extraction',len(units),'unit rows,',len(votes),'metric cells;',len(checks),'candidate/method checks')
if __name__=='__main__':main()
