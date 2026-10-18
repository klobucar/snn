#!/usr/bin/env python3
"""Reconcile saved local PDF samples to the independent certified extract.

PDFs were rendered and visually inspected. Wake 2022 has a broken text encoding;
its page-1 transcription below is explicit and checked against the rendered PNG.
Wake groups write-ins; Catawba omits miscellaneous write-ins in these tables.
"""
import csv
import json
from pathlib import Path
import re
from build import ROOT,DATA,TURNOUT,METHODS,writecsv,save

def extract(name,year,county,candidates,style):
    t=(ROOT/(name+'.txt')).read_text().split('\f')[0]
    rows=[]
    for candidate in candidates:
        printed=candidate.replace(' (Write-In)','') if candidate.startswith('Michelle') else candidate
        line=next(s for s in t.splitlines() if printed in s)
        pattern=r'([\d,]+)\s+[\d.]+\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$' if style=='wake' else r'([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s*$'
        m=re.search(pattern,line);assert m,line
        rows.append(dict(source_id=name,year=str(year),county_native=county,candidate=candidate,pdf_page=1,
            extraction='pdftotext -layout; rendered page visually inspected',**dict(zip(METHODS,[int(x.replace(',','')) for x in m.groups()]))))
    return rows

def main():
    rows=extract('wake-2024-summary',2024,'WAKE',['Kamala D. Harris','Chase Oliver','Jill Stein','Randall Terry','Donald J. Trump','Cornel West','WRITE-IN.'],'wake')
    for candidate,values in [
        ('Matthew Hoh',[4085,2210,1388,440,47]),
        ('Cheri Beasley',[281367,105361,146433,28001,1572]),
        ('Shannon W. Bray',[6634,3926,2183,458,67]),
        ('Ted Budd',[160818,84226,68596,7179,817]),
        ('WRITE-IN.',[266,141,99,22,4])]:
        rows.append(dict(source_id='wake-2022-summary',year='2022',county_native='WAKE',candidate=candidate,pdf_page=1,
            extraction='manual transcription from rendered page; source text encoding is corrupt',**dict(zip(METHODS,values))))
    rows+=extract('catawba-2024-summary',2024,'CATAWBA',['Donald J. Trump','Kamala D. Harris','Chase Oliver','Jill Stein','Cornel West','Randall Terry'],'catawba')
    rows+=extract('catawba-2022-summary',2022,'CATAWBA',['Matthew Hoh','Michelle Estelle Lewis (Write-In)','Cheri Beasley','Shannon W. Bray','Ted Budd'],'catawba')
    cert=list(csv.DictReader((TURNOUT/'certified-candidate-extract.csv').open()))
    checks=[]
    for r in rows:
        expected=[x for x in cert if x['year']==r['year'] and x['county_native']==r['county_native'] and
            ((r['candidate']=='WRITE-IN.' and 'Write-In' in x['candidate']) or x['candidate']==r['candidate'])]
        assert expected
        assert r['total_votes']==sum(r[k] for k in METHODS[1:])
        for k in METHODS:
            v=sum(int(x[k]) for x in expected)
            checks.append(dict(source_id=r['source_id'],candidate=r['candidate'],field=k,local_pdf=r[k],certified=v,difference=r[k]-v))
    assert all(r['difference']==0 for r in checks)
    writecsv(ROOT/'local-summary-extract.csv',rows)
    writecsv(ROOT/'local-summary-checks.csv',checks)
    save('local-summary-checks.json',dict(rows=len(rows),candidate_method_checks=len(checks),differences=0,
        catawba_2024_omitted_miscellaneous_writeins=224,catawba_2022_omitted_miscellaneous_writeins=27,
        wake_2024_grouped_writeins=2784,wake_2022_grouped_writeins=266,
        wake_2024_local_registered_voters=862188,wake_2024_dashboard_registered_voters=857354,
        wake_2024_local_counted_units=237,wake_2024_dashboard_counted_precincts=212,
        wake_2022_local_counted_units=280,wake_2022_dashboard_counted_precincts=208,
        caveat='Registration discrepancy cause/vintage unestablished; preserve both. Native counted units are not remaining votes.'))
    print('23 local candidate/group rows; 115 candidate/method fields reconcile exactly.')

if __name__=='__main__':main()
