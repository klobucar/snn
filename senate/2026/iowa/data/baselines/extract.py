#!/usr/bin/env python3
"""Independent source-to-county extraction; no coordinator/peer derived input.
Match Census county labels at the left edge; parse trailing source columns on
every numeric row, including split-page methods and full pagination filtering.
"""
import collections, json, re
from common import *

def canvasses():
    counties=fipsmap();assert len(counties)==99
    native_names=sorted(counties,key=len,reverse=True)
    long=[];wide=[];controls=[];headers=[]
    for contest,spec in SPECS.items():
        meta=next(r for r in sources() if r['id']==f"sos-{spec['year']}-canvass")
        text=pdftext(raw(meta));gzwrite(f"text/{meta['id']}.txt.gz",text.encode())
        start=text.index(spec['title']);end=text.index('United States Representative District 1',start)
        section=text[start:end];width=len(spec['labels'])+3
        labels=spec['labels']+['Under Votes','Over Votes','Total']
        headers.append({'contest':contest,'source_id':meta['id'],'header_lines':section.splitlines()[:17],'labels':spec['labels'],'parties':spec['parties'],'party_blank_means':'not supplied in this header; no independent/coalition assumption'})
        county=None;parsed=[];page=text[:start].count('\f')+1
        for ln,line in enumerate(section.splitlines(),1):
            if '\f' in line:page+=line.count('\f')
            clean=re.sub(r'Page\s+\d+\s+of\s+\d+.*$','',line).lstrip('\f')
            values=list(re.finditer(r'(?<!\S)\d[\d,]*(?!\S)',clean))
            if len(values)<width:continue
            values=values[-width:];prefix=clean[:values[0].start()].strip()
            counts=[int(v[0].replace(',','')) for v in values]
            new=next((n for n in native_names if prefix==n or prefix.startswith(n+' ')),None)
            if new:county=new;prefix=prefix[len(new):].strip()
            elif prefix.startswith('TOTAL'):county='STATE';prefix=prefix[5:].strip()
            if county is None:raise ValueError((contest,ln,line))
            if prefix in ('Total',''):method='Total' if prefix=='Total' else 'Election Day'
            elif prefix.startswith('Election'):method='Election Day'
            elif prefix=='Absentee':method='Absentee'
            else:raise ValueError((contest,prefix,line))
            # 2020 statewide footer has no TOTAL marker and directly follows Wright.
            if spec['year']==2020 and method=='Total' and len([r for r in parsed if r['native_method']=='Total'])==99:county='STATE'
            assert sum(counts[:-1])==counts[-1],(contest,county,method)
            row={'contest':contest,'year':spec['year'],'county':county,'county_fips':counties.get(county,''),'native_method':method,'source_id':meta['id'],'source_page':page,'section_text_line':ln,'raw_line':line,'column_counts':counts}
            parsed.append(row)
            for col,(label,v) in enumerate(zip(labels,counts),1):
                metric='candidate_votes' if col<=len(spec['labels']) else ['undervotes','overvotes','reported_total'][col-len(spec['labels'])-1]
                party=spec['parties'][col-1] if col<=len(spec['labels']) else ''
                long.append({k:v for k,v in row.items() if k!='column_counts'}|{'source_column':col,'candidate_or_metric_label':label,'party_header':party,'metric':metric,'votes':v})
        totals=[r for r in parsed if r['native_method']=='Total' and r['county']!='STATE']
        assert len(totals)==len({r['county'] for r in totals})==99,(contest,len(totals))
        for r in totals:
            for col in range(width):
                methods=[p['column_counts'][col] for p in parsed if p['county']==r['county'] and p['native_method']!='Total']
                assert len(methods)==2 and sum(methods)==r['column_counts'][col],(contest,r['county'],col,methods)
            vals=r['column_counts'];d=vals[spec['d']];rr=vals[spec['r']];a=sum(vals[:-3]);pair=d+rr
            wide.append({k:v for k,v in r.items() if k not in ('column_counts','raw_line','native_method')}|{'d':d,'r':rr,'named_nonmajor_votes':sum(vals[:len(spec['labels'])-1])-pair,'generic_writein_votes':vals[-4],'named_candidate_votes':sum(vals[:-4]),'candidate_writein_votes':a,'under_votes':vals[-3],'over_votes':vals[-2],'reported_contest_total':vals[-1],'pair_votes':pair,'pair_participation':pair/a,'d_pair_share':d/pair,'d_minus_r_net':d-rr,'d_minus_r_pair_margin':(d-rr)/pair,'d_minus_r_allcandidate_margin':(d-rr)/a,'historical_pair_winner':'D' if d>rr else 'R' if rr>d else 'tie','ballots_cast':'','registered_voters':'','ballots_registration_scope':'not present as distinct measures in county contest table'})
        for method in ['Election Day','Absentee','Total']:
            state=[r for r in parsed if r['county']=='STATE' and r['native_method']==method]
            sums=[sum(r['column_counts'][i] for r in parsed if r['county']!='STATE' and r['native_method']==method) for i in range(width)]
            for i,label in enumerate(labels):
                control=state[0]['column_counts'][i] if state else None
                controls.append({'contest':contest,'native_method':method,'source_column':i+1,'candidate_or_metric_label':label,'county_sum':sums[i],'primary_state_control':control,'difference':sums[i]-control if control is not None else None,'status':'match' if control==sums[i] else 'state method control not published' if control is None else 'disagreement','source_id':meta['id']})
    csvout('canvass-candidate-method.csv',long);csvout('county-contests.csv',wide);csvout('state-controls.csv',controls);dump('candidate-headers.json',headers)
    rank=sorted([r for r in wide if r['contest']=='2024-president'],key=lambda r:(-r['candidate_writein_votes'],r['county_fips']))
    den=sum(r['candidate_writein_votes'] for r in rank);running=0;pr=[]
    for i,r in enumerate(rank,1):
        before=running;running+=r['candidate_writein_votes'];pr.append({'rank':i,'county':r['county'],'county_fips':r['county_fips'],'candidate_writein_votes':r['candidate_writein_votes'],'cumulative_votes':running,'priority80':before*5<den*4})
    csvout('priority-order.csv',pr)
    n=sum(r['priority80'] for r in pr)
    dump('priority.json',{'status':'independently extracted; peer/coordinator review pending','denominator_scope':'all named candidate columns plus generic Write-in; no under/over; named-valid write-in classification unavailable','denominator':den,'generic_writein_votes':sum(r['generic_writein_votes'] for r in rank),'named_candidate_votes':sum(r['named_candidate_votes'] for r in rank),'top15_votes':sum(r['candidate_writein_votes'] for r in rank[:15]),'minimum_count':n,'priority_votes':pr[n-1]['cumulative_votes'],'preceding_votes':pr[n-2]['cumulative_votes'],'ordered_fips':[r['county_fips'] for r in pr],'priority_names':[r['county'] for r in pr[:n]]})
    print('Independent canvasses:',len(wide),'county-contests;',len(long),'candidate/metric rows; priority',n,den)
if __name__=='__main__':canvasses()
