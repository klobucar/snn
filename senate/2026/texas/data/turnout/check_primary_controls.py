#!/usr/bin/env python3
"""Reconcile original Harris precinct counts and Dallas/Travis vendor columns."""
import csv,gzip,json,re,collections
from build_turnout import ROOT,STATE,writecsv,dump

def check():
    county=list(csv.DictReader(open(STATE/'data/county-turnout.csv')));cm={r['county_fips']:r for r in county};records=[];sums=collections.Counter();units=set()
    text=gzip.decompress((ROOT/'original-harris-2024.txt.gz').read_bytes()).decode()
    labels=['TED CRUZ','COLIN ALLRED','TED BROWN','Analisa Roche (W)','Tracy Andrus (W)','Cast Votes','Undervotes','Overvotes','Ballot by Mail Ballots Cast','Early Voting Ballots Cast','Election Day Ballots Cast','EV Provisional Ballots Cast','ED Provisional Ballots Cast','Total Ballots Cast','Registered Voters']
    for pi,page in enumerate(text.split('\f'),1):
        if 'TED CRUZ' not in page or 'COLIN ALLRED' not in page:continue
        for line in page.splitlines():
            m=re.match(r'^(\d{4} - \d+)\s{2,}(.*)$',line)
            if not m:continue
            vals=m[2].split();assert len(vals) in [15,16];counts=[int(v.replace(',','')) for v in vals[:15]];assert m[1] not in units;units.add(m[1]);r=dict(zip(labels,counts))
            assert sum(counts[:5])==r['Cast Votes'],(m[1],'candidate cast')
            assert r['Cast Votes']+r['Undervotes']+r['Overvotes']==r['Total Ballots Cast'],(m[1],'ballot control')
            assert sum(counts[8:13])==r['Total Ballots Cast'],(m[1],'method control')
            sums.update(r);records.append({'source_id':'original-harris-2024','county_fips':'48201','native_unit_id':m[1],'source_pdf_page':pi,'source_values_json':json.dumps(r,separators=(',',':')),'source_turnout_percentage':vals[15] if len(vals)==16 else ''})
    assert len(units)==1584
    h=cm['48201'];assert sums['TED CRUZ']==int(h['senate_2024_r']);assert sums['COLIN ALLRED']==int(h['senate_2024_d']);assert sums['TED BROWN']==int(h['senate_2024_brown']);assert sums['Tracy Andrus (W)']==int(h['senate_2024_andrus_writein']);assert sums['Analisa Roche (W)']==int(h['senate_2024_roche_writein']);assert sums['Cast Votes']==int(h['senate_2024_total'])
    h.update(ballots_cast_2024=sums['Total Ballots Cast'],registered_voters_2024=sums['Registered Voters'],registration_status_2024='Source Registered Voters; active/suspense split not established',senate_2024_undervotes=sums['Undervotes'],senate_2024_overvotes=sums['Overvotes'])
    for r in county:r.update(ballots_source_id_2024='original-harris-2024' if r['county_fips']=='48201' else '',registration_source_id_2024='original-harris-2024' if r['county_fips']=='48201' else '')
    comparisons=[];diagnostics=json.load(open(ROOT/'primary-native-diagnostics.json'))
    for code,source in [('48113','original-dallas-2024'),('48453','original-travis-2024')]:
        d=next(r for r in diagnostics if r['source_id']==source);reg=d['selected_contest_controls'][0];vals=reg['source_total_values'];c=cm[code];c['registered_voters_2024']=vals[0];c['ballots_cast_2024']=vals[-1];c['registration_status_2024']='Source Registered Voters; active/suspense split not established';c['ballots_source_id_2024']=source;c['registration_source_id_2024']=source
        assert sum(vals[1:-1])==vals[-1]
        for control in d['selected_contest_controls'][1:]:
            labels2=control['native_column_labels'];values=control['source_total_values'];totals=[values[i-1] for i,s in enumerate(labels2) if s=='Total Votes'];assert sum(totals)==values[-1]
            contest='senate_2024' if 'Senator' in control['title'] else 'president_2024';mapped=[('r',totals[0]),('d',totals[1])];other=sum(totals[2:]);mapped.append(('other',other))
            for field,value in mapped:comparisons.append({'source_id':source,'county_fips':code,'contest':contest,'source_candidate_or_group':field,'source_count':value,'selected_primary_count':int(c[contest+'_'+field]),'source_minus_primary':value-int(c[contest+'_'+field])})
            if contest=='senate_2024':
                for field,value in [('brown',totals[2]),('named_or_generic_writein',totals[3])]:
                    primary=int(c['senate_2024_brown']) if field=='brown' else int(c['senate_2024_andrus_writein'])+int(c['senate_2024_roche_writein']);comparisons.append({'source_id':source,'county_fips':code,'contest':contest,'source_candidate_or_group':field,'source_count':value,'selected_primary_count':primary,'source_minus_primary':value-primary})
            comparisons.append({'source_id':source,'county_fips':code,'contest':contest,'source_candidate_or_group':'total','source_count':values[-1],'selected_primary_count':int(c[contest+'_total']),'source_minus_primary':values[-1]-int(c[contest+'_total'])})
    writecsv(STATE/'data/county-turnout.csv',county);writecsv(ROOT/'primary-harris-senate-units.csv.gz',records);writecsv(ROOT/'original-vendor-county-comparison.csv',comparisons)
    dump('primary-unit-controls.json',{'status':'pass','harris_source_id':'original-harris-2024','harris_units':len(units),'harris_source_totals':dict(sums),'scope':'Every Harris Senate candidate, cast/under/over/ballot/method unit control reconciles; Dallas/Travis every selected original vendor column reconciles to its own Total row. Vendor candidate universe differences retained, not repaired. Other original PDF rosters are identities only.'})
    print('Harris complete primary precinct candidate/ballot/method controls pass;',dict(sums))
if __name__=='__main__':check()
