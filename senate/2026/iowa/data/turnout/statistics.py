#!/usr/bin/env python3
"""Preserve source-scoped registration/voting demographics and historical unit names."""
import re
from collections import Counter,defaultdict
import build as b

def extract():
    rows=[];unitstarts=[];unknown=[]
    for year in [2024,2022,2020]:
        for kind in ['statestats','countystats','precinctstats']:
            src=b.BYID[f'sos-{year}-{kind}'];text=b.pdftext(src);county=None;unit=None;category=None;date=None;unitseq=0;unitkey=None;pending_unit=None
            for page_no,page in enumerate(text.split('\f'),1):
                if not page.strip():continue
                header=re.search(r'County:\s*(.*?)\s{2,}',page)
                hcounty=header.group(1).strip() if header else None
                if hcounty and hcounty!='State of Iowa' and county!=hcounty:county=hcounty;unit=None;category=None
                if kind=='statestats':county='State of Iowa';unit='Statewide Voters'
                d=re.search(r'(?:Run Date:|Date\s*:)\s*([\d/]+)',page)
                if d:date=d.group(1)
                body=False
                for lineno,line in enumerate(page.splitlines(),1):
                    if 'AGE:' in line:
                        body=True
                        prefix=line.split('AGE:',1)[0].strip()
                        if kind=='countystats' and prefix in b.COUNTIES:county=prefix;unit=prefix;category=None
                        continue
                    if not body or not line.strip() or re.match(r'^\s*Page\s*:',line):continue
                    m=re.match(r'^\s*(.*?)\s*(REGISTERED|TOTAL VOTED|ABSENTEE|TURNOUT)\s+(.*?)\s*$',line)
                    if not m:
                        label=line.strip()
                        if kind=='countystats' and label in b.COUNTIES:county=label;unit=label;category=None
                        elif kind=='precinctstats':
                            if pending_unit is not None:
                                pending_unit['native_unit_label']+='\n'+label;unit=pending_unit['native_unit_label']
                            else:
                                unit=label;unitseq+=1;category=None
                                unitkey=f"{src['id']}|{county}|p{page_no}l{lineno}"
                                pending_unit=dict(year=year,county=county,county_fips=b.COUNTIES.get(county,{}).get('county_fips'),source_id=src['id'],native_unit_label=label,unit_key=unitkey,source_page=page_no,source_page_line=lineno,unit_kind='registration_statistics_precinct_label; reporting/polygon equivalence unestablished',source_date=date)
                                unitstarts.append(pending_unit)
                        else:unknown.append(dict(source_id=src['id'],page=page_no,line=lineno,text=label))
                        continue
                    cat,metric,tail=m.groups()
                    if cat:category=cat.strip()
                    pending_unit=None
                    if category=='Grand Totals' and kind=='countystats':county='State of Iowa';unit='Statewide Voters'
                    vals=tail.split()
                    assert len(vals)==8,(src['id'],page_no,lineno,vals)
                    assert county in b.COUNTIES or county=='State of Iowa',(src['id'],page_no,county)
                    assert unit is not None,(src['id'],page_no)
                    numeric=[v if metric=='TURNOUT' else int(v.replace(',','')) for v in vals]
                    rows.append(dict(year=year,county=county,county_fips=b.COUNTIES.get(county,{}).get('county_fips','19'),source_id=src['id'],source_kind=kind,native_unit_label='Grand Totals' if category=='Grand Totals' else unit,unit_key=f"{src['id']}|{county}|grand-total" if category=='Grand Totals' else unitkey,demographic_category=category,metric=metric,age17=numeric[0],age18_24=numeric[1],age25_34=numeric[2],age35_49=numeric[3],age50_64=numeric[4],age65_plus=numeric[5],age_unknown=numeric[6],total=numeric[7],source_date=date,registration_status='report REGISTERED definition; not assumed active or election-date snapshot',source_page=page_no,source_page_line=lineno,raw_line=line))
            print(src['id'],'rows',sum(x['source_id']==src['id'] for x in rows),flush=True)
    b.csvout('statistics-rows.csv.gz',rows);b.csvout('statistics-units.csv',unitstarts);b.dump('statistics-unparsed-lines.json',unknown)
    print('units',len(unitstarts),'unparsed',len(unknown))

if __name__=='__main__':extract()
