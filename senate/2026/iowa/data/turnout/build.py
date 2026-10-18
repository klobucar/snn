#!/usr/bin/env python3
"""Offline, integer-preserving extraction of retained Iowa primary sources."""
import csv,gzip,hashlib,io,json,re,subprocess,zipfile,posixpath
import xml.etree.ElementTree as ET
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCES=json.loads((ROOT/'source-manifest.json').read_text())
BYID={r['id']:r for r in SOURCES}
def sha(b):return hashlib.sha256(b).hexdigest()
def raw(r):
    b=(ROOT/r['path']).read_bytes();assert sha(b)==r['stored_sha256']
    v=gzip.decompress(b);assert sha(v)==r['original_sha256'];return v
def dump(name,obj): (ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def csvout(name,rows,fields=None):
    target=ROOT/name
    opener=gzip.open(target,'wt',newline='') if name.endswith('.gz') else target.open('w',newline='')
    with opener as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def pdftext(r,refresh=False):
    p=ROOT/'text'/f"{r['id']}.txt.gz"
    if p.exists() and not refresh:return gzip.decompress(p.read_bytes()).decode()
    t=subprocess.run(['pdftotext','-layout','-','-'],input=raw(r),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    (ROOT/'text').mkdir(exist_ok=True);p.write_bytes(gzip.compress(t.stdout,mtime=0))
    (ROOT/'text'/f"{r['id']}.stderr.txt").write_bytes(t.stderr)
    return t.stdout.decode()

CENSUS=list(csv.DictReader(io.StringIO(raw(BYID['census-county-codes']).decode()),delimiter='|'))
COUNTIES={r['COUNTYNAME'].removesuffix(' County'):dict(county=r['COUNTYNAME'].removesuffix(' County'),county_fips=r['STATEFP']+r['COUNTYFP'],census_countyns=r['COUNTYNS']) for r in CENSUS if r['STATE']=='IA'}
assert len(COUNTIES)==99
LABELS={
2024:['Kamala D. Harris and Tim Walz, DEM','Donald J. Trump and JD Vance, REP','Chase Oliver and Mike ter Maat, LIB','Shiva Ayyadurai and Crystal Ellis','Claudia De la Cruz and Karina Garcia, PSL','William P. Stodden and Stephanie H. Cholensky, SOC','Robert F. Kennedy Jr and Nicole Shanahan, WTP','Write-in','Under Votes','Over Votes','Total'],
2022:['Chuck Grassley, REP','Michael Franken, DEM','Write-in','Under Votes','Over Votes','Total'],
2020:['Joni Ernst, REP','Theresa Greenfield, DEM','Rick Stewart, LIB','Suzanne Herzog','Write-in','Under Votes','Over Votes','Total']}
CONTESTS={2024:'President and Vice President',2022:'United States Senator',2020:'United States Senator'}

def canvasses():
    out=[];controls={};wide={}
    for year in [2024,2022,2020]:
        r=BYID[f'sos-{year}-canvass'];t=pdftext(r,refresh=True);section=t[t.index(CONTESTS[year]):];section=section[:section.index('United States Representative')]
        # A numeric row contains exactly the printed source columns at its right.
        # The 2024 Election Day label wraps around the numeric row; sequence is explicit.
        data=[];page=t[:t.index(CONTESTS[year])].count('\f')+1
        for line_no,line in enumerate(section.splitlines(),1):
            line=re.sub(r'Page\s+\d+\s+of\s+\d+','',line)
            m=re.search(r'((?:\d[\d,]*\s+){'+str(len(LABELS[year])-1)+r'}\d[\d,]*)\s*$',line)
            if not m:continue
            nums=[int(v.replace(',','')) for v in m.group(1).split()]
            prefix=line[:m.start()].strip()
            # No arbitrary prefix-to-county normalization: accepted native county is from Census list.
            data.append((nums,prefix,line_no,line))
        expected=300 if year in [2024,2022] else 298
        assert len(data)==expected,(year,len(data))
        totals=[]
        for idx,(vals,prefix,line_no,line) in enumerate(data):
            group=idx//3;method=['Election Day','Absentee','Total'][idx%3] if idx<297 or year!=2020 else 'Total'
            if group<99:
                if idx%3==0:
                    native=re.sub(r'\s+Election(?:\s+Day)?$','',prefix)
                    assert native in COUNTIES,(year,prefix,native)
                county=native;fips=COUNTIES[county]['county_fips']
            else:county='State of Iowa';fips='19'
            if method=='Total':totals.append((county,vals))
            for col,(label,v) in enumerate(zip(LABELS[year],vals),1):
                metric='under_votes' if label=='Under Votes' else 'over_votes' if label=='Over Votes' else 'reported_contest_total' if label=='Total' else 'generic_writein' if label=='Write-in' else 'named_candidate'
                out.append(dict(year=year,election_date=f'{year}-11-'+{2024:'05',2022:'08',2020:'03'}[year],contest=CONTESTS[year],county=county,county_fips=fips,native_county_label=county if fips!='19' else prefix,native_method=method,source_id=r['id'],source_column=col,candidate_or_metric_label=label,metric=metric,votes=v,section_text_line=line_no,source_row_prefix=prefix,raw_line=line))
        countyvals=dict(totals[:99]);state=totals[-1][1]
        for j in range(len(state)):assert sum(x[j] for x in countyvals.values())==state[j],(year,j)
        # Preserve candidate + under/over accounting and every county method balance.
        for i in range(99):
            ed,ab,tot=[data[3*i+k][0] for k in range(3)]
            assert [a+b for a,b in zip(ed,ab)]==tot,(year,i)
            assert sum(tot[:-1])==tot[-1],(year,i)
        if year in [2024,2022]:
            for m in [0,1]:
                assert [sum(data[3*i+m][0][j] for i in range(99)) for j in range(len(state))]==data[297+m][0]
        controls[str(year)]=dict(source_id=r['id'],original_sha256=r['original_sha256'],contest=CONTESTS[year],column_labels=LABELS[year],state_counts=state,candidate_generic_writein_votes=sum(state[:-3]),named_candidate_votes=sum(state[:-4]),generic_writein_votes=state[-4],under_votes=state[-3],over_votes=state[-2],reported_contest_total=state[-1],county_count=99,method_rows=297,state_rows=len(data)-297,canvass_date=re.search(r'Canvass date:\s*([^\n]+)',t).group(1).strip() if 'Canvass date:' in t else None)
        wide[year]=countyvals
    csvout('canvass-candidate-method.csv',out);dump('state-controls.json',controls)
    return wide,controls

def turnout_reports():
    rows=[]
    for year in [2024,2022,2020]:
        r=BYID[f'sos-{year}-turnout'];t=pdftext(r,refresh=True)
        for no,line in enumerate(t.splitlines(),1):
            m=re.match(r'^\s*(.+?)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d.]+)%\s+([\d,]+)\s+([\d.]+)%\s*$',line)
            if not m:continue
            county,ed,ab,total,active,ar,inactive,tr=m.groups()
            assert county in COUNTIES or county=='Total',(year,county)
            ed,ab,total,active,inactive=[int(s.replace(',','')) for s in [ed,ab,total,active,inactive]]
            assert ed+ab==total
            rows.append(dict(year=year,county=county,county_fips=COUNTIES[county]['county_fips'] if county in COUNTIES else '19',source_id=r['id'],election_day_voters=ed,absentee_voters=ab,total_voters=total,active_registered=active,inactive_registered=inactive,registration_as_of=f'{year}-11-'+{2024:'05',2022:'08',2020:'03'}[year],published_active_turnout_pct=ar,published_total_turnout_pct=tr,source_text_line=no))
        sub=[x for x in rows if x['year']==year];assert len(sub)==100
        for f in ['election_day_voters','absentee_voters','total_voters','active_registered','inactive_registered']:assert sum(x[f] for x in sub if x['county_fips']!='19')==next(x[f] for x in sub if x['county_fips']=='19'),(year,f)
    csvout('turnout-report-counties.csv',rows);return rows

def ranking(wide,controls,turnouts):
    rows=[];den=controls['2024']['candidate_generic_writein_votes'];running=0;crossing=None
    for i,(county,vals) in enumerate(sorted(wide[2024].items(),key=lambda kv:(-sum(kv[1][:-3]),COUNTIES[kv[0]]['county_fips'])),1):
        votes=sum(vals[:-3]);previous=running;running+=votes
        if crossing is None and 5*running>=4*den:crossing=i
        row=dict(rank_2024=i,county=county,county_fips=COUNTIES[county]['county_fips'],native_county_label=county,county_source_id='sos-2024-canvass',county_native_numeric_id=None,pres2024_named_candidate_votes=sum(vals[:-4]),pres2024_generic_writein_votes=vals[-4],pres2024_candidate_generic_writein_votes=votes,pres2024_under_votes=vals[-3],pres2024_over_votes=vals[-2],pres2024_reported_contest_total=vals[-1],state_candidate_generic_writein_denominator=den,cumulative_candidate_generic_writein_votes=running,share_numerator=votes,share_denominator=den,in_top15=i<=15,in_minimum80=False)
        for y in [2024,2022,2020]:
            tr=next(x for x in turnouts if x['year']==y and x['county']==county)
            vv=wide[y][county]
            row.update({f'{y}_{k}':tr[k] for k in ['election_day_voters','absentee_voters','total_voters','active_registered','inactive_registered','registration_as_of','published_active_turnout_pct','published_total_turnout_pct']})
            if y!=2024:row.update({f'sen{y}_candidate_generic_writein_votes':sum(vv[:-3]),f'sen{y}_generic_writein_votes':vv[-4],f'sen{y}_under_votes':vv[-3],f'sen{y}_over_votes':vv[-2],f'sen{y}_reported_contest_total':vv[-1]})
        rows.append(row)
    for r in rows:r['in_minimum80']=r['rank_2024']<=crossing
    csvout('../county-turnout.csv',rows)
    obj=dict(schema_version=1,acceptance_status='independent turnout calculation; coordinator/peer reconciliation pending',baseline=dict(year=2024,election_date='2024-11-05',contest=CONTESTS[2024],source_id='sos-2024-canvass',original_sha256=BYID['sos-2024-canvass']['original_sha256'],denominator=den,denominator_definition='Sum of seven printed named-ticket columns plus generic Write-in. Generic write-in validity/named allocation not supplied; under/over excluded.'),sort='descending candidate_generic_writein_votes; county FIPS ascending tie-break',threshold=dict(numerator=4,denominator=5,minimum_count=crossing,votes=sum(r['pres2024_candidate_generic_writein_votes'] for r in rows[:crossing]),preceding_count=crossing-1,preceding_votes=sum(r['pres2024_candidate_generic_writein_votes'] for r in rows[:crossing-1]),crossing_county=rows[crossing-1]['county'],crossing_county_fips=rows[crossing-1]['county_fips']),top15=dict(count=15,votes=sum(r['pres2024_candidate_generic_writein_votes'] for r in rows[:15]),denominator=den),all_counties=rows,native_constituents_status='native-unit extraction in progress; final build attaches source-scoped historical units; no approved 2026 crosswalk')
    dump('priority-set.json',obj);return rows,obj

def main():
    wide,controls=canvasses();tr=turnout_reports();rows,obj=ranking(wide,controls,tr)
    print(json.dumps(dict(controls=controls,threshold=obj['threshold'],top15=obj['top15']),indent=2))
if __name__=='__main__':main()
