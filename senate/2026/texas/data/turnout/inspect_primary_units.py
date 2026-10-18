#!/usr/bin/env python3
"""Inspect original county reports without changing their candidate universes."""
import collections,csv,gzip,hashlib,io,json,re,subprocess,zipfile,xml.etree.ElementTree as E
from build_turnout import ROOT,RAW,readraw,writecsv,dump
NS={'s':'urn:schemas-microsoft-com:office:spreadsheet'};ATTR='{urn:schemas-microsoft-com:office:spreadsheet}'

def expanded(row):
    vals=[]
    for c in row.findall('s:Cell',NS):
        ix=int(c.attrib.get(ATTR+'Index',len(vals)+1));vals+=['']*max(0,ix-1-len(vals));data=c.find('s:Data',NS);vals.append(''.join(data.itertext()) if data is not None else '');vals+=['']*int(c.attrib.get(ATTR+'MergeAcross','0'))
    return vals

def inspect():
    rosters=[];cells=[];diagnostics=[]
    for county,code in [('dallas','48113'),('travis','48453')]:
        source='original-'+county+'-2024';z=zipfile.ZipFile(io.BytesIO(readraw(source)));root=E.fromstring(z.read(z.namelist()[0]));units={};source_diag={'source_id':source,'worksheets':[],'selected_contest_controls':[]}
        for ws in root.findall('s:Worksheet',NS):
            name=ws.attrib[ATTR+'Name'];rs=[expanded(r) for r in ws.findall('.//s:Row',NS)]
            if name=='Table of Contents':continue
            first=rs[0][0] if rs and rs[0] else ''
            headeridx=next((i for i,r in enumerate(rs) if r and r[0]=='Precinct'),None)
            if headeridx is None:continue
            selected=name=='Registered Voters' or 'President' in first or 'United States Senator' in first
            candidates=rs[headeridx-1] if headeridx>0 else []
            labels=rs[headeridx];sums=None;total=None;numeric_rows=0
            for ri,row in enumerate(rs[headeridx+1:],headeridx+2):
                if not row or not row[0]:continue
                aggregate=row[0].strip().lower().startswith('total')
                if not all(re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?%?',x or '') for x in row[1:]):continue
                numeric_rows+=1
                if not aggregate:
                    units.setdefault(row[0],{'source_id':source,'county_fips':code,'native_unit_id':row[0],'first_worksheet':name,'first_source_row':ri,'observed_worksheets':set()})['observed_worksheets'].add(name)
                if selected:
                    cells.append({'source_id':source,'county_fips':code,'source_worksheet':name,'source_row':ri,'native_unit_id':row[0],'record_scope':'county aggregate control' if aggregate else 'source reporting unit','source_title':first,'candidate_header_json':json.dumps(candidates,separators=(',',':')),'column_header_json':json.dumps(labels,separators=(',',':')),'source_values_json':json.dumps(row,separators=(',',':'))})
                    nums=[int(v) for v in row[1:] if re.fullmatch(r'-?[0-9]+',v)]
                    if aggregate:total=nums
                    elif sums is None:sums=nums
                    else:
                        assert len(sums)==len(nums),(source,name,row)
                        sums=[a+b for a,b in zip(sums,nums)]
            if selected:
                assert sums==total,(source,name,'unit sum differs from native source Total:',sums,total)
                source_diag['selected_contest_controls'].append({'worksheet':name,'title':first,'native_column_labels':labels,'candidate_header':candidates,'source_total_values':total,'unit_sum_values':sums,'numeric_source_rows':numeric_rows})
            source_diag['worksheets'].append({'worksheet':name,'title':first,'numeric_source_rows':numeric_rows,'selected_detail':selected})
        for r in units.values():r['observed_worksheets']=sorted(r['observed_worksheets']);r['classification']='native vendor reporting unit; no2026 geographic match established';rosters.append(r)
        diagnostics.append(source_diag)
    # All native unit identities across every page of four original PDFs.
    for county,code in [('angelina','48005'),('midland','48329'),('bexar','48029'),('harris','48201')]:
        source='original-'+county+'-2024';cache=ROOT/(source+'.txt.gz')
        text=gzip.decompress(cache.read_bytes()) if cache.exists() else subprocess.run(['pdftotext','-layout','-','-'],input=readraw(source),capture_output=True,check=True).stdout
        (ROOT/(source+'.txt.gz')).write_bytes(gzip.compress(text,mtime=0));units={};counts=collections.Counter()
        for pi,page in enumerate(text.decode().split('\f'),1):
            if county in ['angelina','bexar']:
                pat=r'^\s*(Precinct \d+[A-Za-z]*|\d+ BS \d+)\s*$'
                for m in re.finditer(pat,page,re.M):units.setdefault(m[1],{'source_id':source,'county_fips':code,'native_unit_id':m[1],'first_pdf_page':pi,'classification':'native precinct/ballot-style report identity; polygon equivalence unverified'})
            else:
                for line in page.splitlines():
                    m=re.fullmatch(r'\s*(\S(?:.*?\S)?)\s{2,}([-0-9,]+(?:\s+[-0-9,.]+%?)+)\s*',line)
                    if not m:continue
                    unit=m[1].strip()
                    if unit.lower().startswith(('total','run ','registered','precincts')):continue
                    if re.fullmatch(r'\d{4} - \d+',unit) if county=='harris' else re.fullmatch(r'\d+[A-Z]?',unit):
                        units.setdefault(unit,{'source_id':source,'county_fips':code,'native_unit_id':unit,'first_pdf_page':pi,'classification':'native precinct/ballot-style report identity; polygon equivalence unverified'})
                    else:counts[unit]+=1
        assert units,source
        rosters.extend(units.values());diagnostics.append({'source_id':source,'native_units':len(units),'pdf_pages':len(text.decode().split('\f'))-1,'unclassified_numeric_row_labels':dict(counts),'scope':'Full original PDF text retained; roster only. Candidate/method rows in raw PDF remain authoritative, all-unit candidate/control validation not claimed.'})
    fields=['source_id','county_fips','native_unit_id','classification','first_worksheet','first_source_row','observed_worksheets','first_pdf_page']
    writecsv(ROOT/'primary-native-units.csv.gz',[{k:r.get(k,'') for k in fields} for r in rosters],fields)
    writecsv(ROOT/'primary-native-records.csv.gz',cells);dump('primary-native-diagnostics.json',diagnostics)
    priority=json.load(open(ROOT/'priority-set.json'))
    for g in priority['groups']:
        g['native_constituents']=[r for r in g['native_constituents'] if r['layer']!='Original county precinct/vendor report']
        g['native_constituents'] += [{'layer':'Original county precinct/vendor report','source_id':r['source_id'],'year':'2024','native_id':r['native_unit_id'],'unit_type':r['classification']} for r in rosters if r['county_fips']==g['county_fips']]
    dump('priority-set.json',priority)
    print('Original primary native rosters',len(rosters),'unit-source identities; vendor selected rows',len(cells))
if __name__=='__main__':inspect()
