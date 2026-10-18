#!/usr/bin/env python3
"""Verify every shared peer statistics numeric cell directly against retained PDF
text, without using the peer's derivation script. Reuse peer files read-only.
This verifies source transcription, not voter-registration vintage equivalence.
"""
import collections,csv,gzip,json,re
from common import *
def main():
    pages={r['id']:gzip.decompress((ROOT/('text/'+r['id']+'.txt.gz')).read_bytes()).decode().split('\f') for r in sources() if any(r['id'].endswith('-'+s) for s in ['statestats','countystats','precinctstats'])}
    path=TURNOUT/'statistics-rows.csv.gz';count=0;cells=0;diffs=[];keys=set();sumdiff=[]
    with gzip.open(path,'rt') as f:
        for row in csv.DictReader(f):
            key=(row['source_id'],row['source_page'],row['source_page_line']);assert key not in keys;keys.add(key)
            line=pages[row['source_id']][int(row['source_page'])-1].splitlines()[int(row['source_page_line'])-1]
            if line!=row['raw_line']:diffs.append({'key':key,'kind':'raw line differs'})
            m=re.search(r'\b(REGISTERED|TOTAL VOTED|ABSENTEE|TURNOUT)\b',line)
            values=line[m.end():].split() if m else []
            fields=['age17','age18_24','age25_34','age35_49','age50_64','age65_plus','age_unknown','total']
            actual=[row[x] for x in fields]
            # Printed comma grouping is harmless source formatting, preserved in raw_line.
            values=[x.replace(',','') for x in values]
            if values!=actual:diffs.append({'key':key,'kind':'values','source':values,'peer':actual})
            if m and m[1]!=row['metric']:diffs.append({'key':key,'kind':'metric'})
            if row['metric']!='TURNOUT' and len(values)==8 and all(x.isdigit() for x in values):
                difference=sum(int(x) for x in values[:-1])-int(values[-1])
                if difference:sumdiff.append({'key':key,'county':row['county'],'unit':row['native_unit_label'],'category':row['demographic_category'],'metric':row['metric'],'age_sum_minus_total':difference,'raw_line':line})
            count+=1;cells+=8
    unitpath=TURNOUT/'statistics-units.csv';unitdiff=[];unitcount=0
    for r in csv.DictReader(unitpath.open()):
        lines=pages[r['source_id']][int(r['source_page'])-1].splitlines();i=int(r['source_page_line'])-1
        # Wrapped names have original newlines; verify contiguous original lines,
        # stripping their visual indentation only. No label-based crosswalk.
        expected=r['native_unit_label'].split('\n');actual=[x.strip() for x in lines[i:i+len(expected)]]
        if actual!=expected:unitdiff.append({'key':r['unit_key'],'source':actual,'peer':expected})
        unitcount+=1
    dump('statistics-verification.json',{'status':'pass' if not diffs and not unitdiff else 'disagreement','scope':'read-only peer full numeric transcriptions and unit source-line identity independently checked against original PDF layout text; demographics overlap; source vintages not substituted for election-date turnout','rows_checked':count,'numeric_or_percent_cells_checked':cells,'native_labels_checked':unitcount,'differences':diffs,'unit_label_differences':unitdiff,'source_age_total_disagreements':sumdiff,'peer_artifacts':[{'path':'../turnout/'+p.name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in [path,unitpath]]})
    print('Statistics',count,cells,unitcount,'differences',len(diffs),len(unitdiff),'age/total disagreements',len(sumdiff))
if __name__=='__main__':main()
