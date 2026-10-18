#!/usr/bin/env python3
"""Independently extract turnout-report scopes; retain complete PDF text evidence."""
import re
from common import *
def main():
    fmap=fipsmap();rows=[]
    for meta in sources():
        if not any(meta['id'].endswith('-'+s) for s in ['turnout','countystats','statestats','precinctstats']):continue
        if meta['status']!=200:continue
        text=pdftext(raw(meta));gzwrite('text/'+meta['id']+'.txt.gz',text.encode())
        if not meta['id'].endswith('-turnout'):continue
        year=int(re.search(r'202[024]',meta['id'])[0]);seen=set()
        for pi,page in enumerate(text.split('\f'),1):
            for ln,line in enumerate(page.splitlines(),1):
                m=re.fullmatch(r'\s*(.*?)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+(\d[\d,]*)\s+([\d.]+)%\s+(\d[\d,]*)\s+([\d.]+)%\s*',line)
                if not m:continue
                county=m[1];fips='19' if county=='Total' else fmap.get(county)
                if fips is None:continue
                assert fips not in seen;seen.add(fips)
                ed,ab,total,active,inactive=[int(m[k].replace(',','')) for k in [2,3,4,5,7]]
                assert ed+ab==total
                rows.append({'year':year,'county':county,'county_fips':fips,'election_day_voters':ed,'absentee_voters':ab,'total_voters':total,'active_registered':active,'inactive_registered':inactive,'registration_as_of':f'{year}-11-'+('05' if year==2024 else '08' if year==2022 else '03'),'published_active_turnout_pct':m[6],'published_total_turnout_pct':m[8],'source_id':meta['id'],'source_page':pi,'source_line':ln,'raw_line':line})
        assert len(seen)==100,(year,len(seen))
    csvout('turnout-report.csv',rows)
    checks=[];can=records('canvass-candidate-method.csv')
    for row in rows:
        for method,col in [('Election Day','election_day_voters'),('Absentee','absentee_voters'),('Total','total_voters')]:
            vals=[r for r in can if r['year']==str(row['year']) and r['county_fips']==('' if row['county_fips']=='19' else row['county_fips']) and r['native_method']==method and r['metric']=='reported_total']
            control=int(vals[0]['votes']) if len(vals)==1 else None
            checks.append({'year':row['year'],'county_fips':row['county_fips'],'native_method':method,'turnout_report_voters':row[col],'canvass_reported_contest_total':control,'difference':row[col]-control if control is not None else None,'status':'match' if control==row[col] else 'unpublished statewide method control' if control is None else 'source disagreement; preserved'})
    csvout('turnout-scope-checks.csv',checks)
    print('Independently extracted',len(rows),'turnout rows; all demographic PDFs text retained')
if __name__=='__main__':main()
