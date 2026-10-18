#!/usr/bin/env python3
"""Offline Texas turnout extraction. Never adjusts primary integers to fit controls."""
import csv,gzip,hashlib,io,json,re,subprocess,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent.parent
RAW=ROOT/'raw'
VINTAGES=['20241215150002','20241215142552','20250422200023']
SEN=['TED CRUZ (I)','COLIN ALLRED','TED BROWN','TRACY ANDRUS','ANALISA ROCHE']
PRES=['DONALD J. TRUMP/JD VANCE','KAMALA D. HARRIS/TIM WALZ','CHASE OLIVER/MIKE TER MAAT','JILL STEIN/RUDOLPH WARE','SHIVA AYYADURAI/CRYSTAL ELLIS','JESSIE CUELLAR/WESLEY LASLEY','CLAUDIA DE LA CRUZ/KARINA GARCIA','CHERUNDA FOX/HARLAN MCVAY','PETER SONSKI/LAUREN ONAK','CORNEL WEST/MELINA ABDULLAH']

def readraw(key):
    meta=json.loads((RAW/(key+'.meta.json')).read_text())
    stored=b''.join((ROOT/r['path']).read_bytes() for r in meta['stored_parts']) if 'stored_parts' in meta else (RAW/(key+'.body.gz')).read_bytes()
    return gzip.decompress(stored)
def csvraw(key):return list(csv.DictReader(io.StringIO(readraw(key).decode('utf-8-sig'))))
def dump(name,obj): (ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def writecsv(path,rows,fields=None):
    rows=list(rows);fields=fields or list(rows[0])
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'wt',newline='',encoding='utf-8') as fp:
        w=csv.DictWriter(fp,fieldnames=fields);w.writeheader();w.writerows(rows)

def pdftext(key):
    pdf=RAW/(key+'.pdf');pdf.write_bytes(readraw(key));out=ROOT/(key+'.txt')
    subprocess.run(['pdftotext','-layout',str(pdf),str(out)],check=True)
    return out.read_text()

def parse2024(key):
    text=pdftext(key);pages=text.split('\f');sen_start=next(i for i,p in enumerate(pages) if re.search(r'^U\. S\. SENATOR\s*$',p,re.M));end=next(i for i in range(sen_start+1,len(pages)) if re.search(r'^U\. S\. REPRESENTATIVE',pages[i],re.M))
    pat=re.compile(r'^\s*([A-Z][A-Z .\'-]*?)\s{2,}([0-9,]+(?:\s+[0-9,]+)+)\s*$')
    def named(ps,n):
        rows=[]
        for pi in ps:
            for line in pages[pi].splitlines():
                m=pat.match(line)
                if m:
                    nums=[int(x.replace(',','')) for x in m[2].split()]
                    if len(nums)==n:rows.append({'county':m[1].strip(),'values':nums,'page':pi+1,'source_line':line})
        return rows
    senate=named(range(sen_start,end),6);scontrol=[r for r in senate if r['county']=='TOTAL VOTES'];senate=[r for r in senate if r['county']!='TOTAL VOTES']
    president=named(range(sen_start),8);pcontrol=[r for r in president if r['county']=='TOTAL VOTES'];president=[r for r in president if r['county']!='TOTAL VOTES']
    tail=[]
    for pi in range(sen_start):
        if 'SONSKI/LAURE' not in pages[pi]:continue
        for line in pages[pi].splitlines():
            if re.fullmatch(r'\s*\d[\d,]*\s+\d[\d,]*\s+\d[\d,]*\s*',line):tail.append({'values':[int(x.replace(',','')) for x in line.split()],'page':pi+1,'source_line':line})
    assert len(senate)==254 and len(president)==254 and len(tail)==255,(key,len(senate),len(president),len(tail))
    assert len(scontrol)==len(pcontrol)==1
    for r,t in zip(president,tail):r['values']+=t['values'];r['tail_page']=t['page'];r['tail_source_line']=t['source_line'];assert sum(r['values'][:-1])==r['values'][-1],r
    for r in senate:assert sum(r['values'][:-1])==r['values'][-1],r
    assert len({r['county'] for r in senate})==254
    assert [r['county'] for r in senate]==[r['county'] for r in president]
    assert [sum(r['values'][i] for r in senate) for i in range(6)]==scontrol[0]['values']
    assert [sum(r['values'][i] for r in president) for i in range(11)]==pcontrol[0]['values']+tail[-1]['values']
    return {'source_id':key,'senate':senate,'president':president,'senate_state_control':scontrol[0]['values'],'president_state_control':pcontrol[0]['values']+tail[-1]['values'],'footer_labels':sorted(set(re.findall(r'\d\d/\d\d/\d{4} \d\d[.:]\d\d [AP]M',text)))}

def main():
    med=[r for r in csvraw('medsl-senate-county') if r['state_po']=='TX'];fips={r['county_name']:r['county_fips'] for r in med};assert len(fips)==254 and len(set(fips.values()))==254
    fips.update({'COLLINGSWOR':fips['COLLINGSWORTH'],'THROCKMORT':fips['THROCKMORTON']})
    canonical={v:k for k,v in fips.items() if k not in ['COLLINGSWOR','THROCKMORT']}
    writecsv(ROOT/'medsl-2024-senate-county.csv',med)
    sources={v:parse2024('sos2024-county-archive-'+v) for v in VINTAGES};dump('primary-county-extraction.json',sources)
    selected=sources[VINTAGES[-1]];candidate_rows=[]
    for contest,names,party in [('senate',SEN,['REP','DEM','LIB','WRI','WRI']),('president',PRES,['REP','DEM','LIB','GRE']+['WRI']*6)]:
        for r in selected[contest]:
            for i,name in enumerate(names):candidate_rows.append({'election_date':'2024-11-05','contest':contest,'senate_class':'I' if contest=='senate' else '', 'county_fips':fips[r['county']],'source_county_name':r['county'],'source_county_code':'','source_candidate_name':name,'source_party':party[i],'write_in':int(party[i]=='WRI'),'votes':r['values'][i],'source_county_total':r['values'][-1],'source_id':selected['source_id'],'source_pdf_page':r['page'] if i<8 else r['tail_page'],'native_row_order':[x['county'] for x in selected[contest]].index(r['county'])+1})
    writecsv(ROOT/'county-candidates-2024.csv',candidate_rows)
    # All 1,270 independent MEDSL county/candidate integers must equal the actual SOS original.
    mednames={'TED CRUZ':'TED CRUZ (I)','COLIN ALLRED':'COLIN ALLRED','TED BROWN':'TED BROWN','TRACY ANDRUS':'TRACY ANDRUS','ANALISA ROCHE':'ANALISA ROCHE'}
    primary={(r['county_fips'],r['source_candidate_name']):r['votes'] for r in candidate_rows if r['contest']=='senate'}
    assert len(med)==len(primary)==1270
    for r in med:assert primary[(r['county_fips'],mednames[r['candidate']])]==int(r['votes']),r
    bypres={r['county']:r for r in selected['president']};ordered=sorted(selected['senate'],key=lambda r:(-r['values'][-1],fips[r['county']]));den=selected['senate_state_control'][-1];cum=0;counties=[]
    fields=['rank','county','county_fips','source_county_name','source_county_code','dispatch_key','senate_2024_total','senate_2024_d','senate_2024_r','senate_2024_other','senate_2024_brown','senate_2024_andrus_writein','senate_2024_roche_writein','share_state_senate_2024','cumulative_senate_2024','cumulative_share_state_senate_2024','top15','priority80','president_2024_total','president_2024_d','president_2024_r','president_2024_other','governor_2022_total','senate_2020_total','ballots_cast_2024','registered_voters_2024','registration_date_2024','registration_status_2024','senate_2024_undervotes','senate_2024_overvotes','ballots_cast_2022','registered_voters_2022','ballots_cast_2020','registered_voters_2020','source_id','geography_vintage','status']
    crossing=None
    for i,r in enumerate(ordered,1):
        prev=cum;cum+=r['values'][-1]
        if crossing is None and 5*cum>=4*den:crossing=i
        vals=r['values'];p=bypres[r['county']]['values'];row=dict.fromkeys(fields,'');row.update(rank=i,county=canonical[fips[r['county']]].title(),county_fips=fips[r['county']],source_county_name=r['county'],dispatch_key='TX:'+fips[r['county']],senate_2024_total=vals[-1],senate_2024_d=vals[1],senate_2024_r=vals[0],senate_2024_other=sum(vals[2:5]),senate_2024_brown=vals[2],senate_2024_andrus_writein=vals[3],senate_2024_roche_writein=vals[4],share_state_senate_2024=format(vals[-1]/den,'.15f'),cumulative_senate_2024=cum,cumulative_share_state_senate_2024=format(cum/den,'.15f'),top15=int(i<=15),priority80=int(crossing is None or i<=crossing),president_2024_total=p[-1],president_2024_d=p[1],president_2024_r=p[0],president_2024_other=sum(p[2:10]),source_id=selected['source_id'],geography_vintage='2024 county names; FIPS mapped from pinned MEDSL',status='SOS official county canvass, archived capture; footer 07/01/2025 10.42 AM')
        counties.append(row)
    writecsv(STATE/'data/county-turnout.csv',counties,fields)
    k=crossing;top=sum(r['senate_2024_total'] for r in counties[:15]);s80=sum(r['senate_2024_total'] for r in counties[:k]);prev=sum(r['senate_2024_total'] for r in counties[:k-1]);assert 5*prev<4*den<=5*s80
    priority={'state':'TX','contest':'2024-11-05 U. S. SENATOR (Class I, OTHER seat from2026 Class II)','source_id':selected['source_id'],'source_original_sha256':json.loads((RAW/(selected['source_id']+'.meta.json')).read_text())['original_sha256'],'source_denominator':den,'candidate_universe':SEN,'ranking':'descending all valid candidate votes; county FIPS ascending breaks exact ties','county_group_key_format':'TX:<five-digit county FIPS>','top15_votes':top,'top15_share_exact':f'{top}/{den}','minimum80_count':k,'minimum80_votes':s80,'preceding_set_votes':prev,'crossing_county':counties[k-1]['dispatch_key'],'remainder_votes':den-s80,'priority_keys':[r['dispatch_key'] for r in counties[:k]],'full_order':[r['dispatch_key'] for r in counties],'remainder_keys':[r['dispatch_key'] for r in counties[k:]],'groups':[{'dispatch_key':r['dispatch_key'],'county_fips':r['county_fips'],'native_county_identity':r['source_county_name'],'rank':r['rank'],'votes':r['senate_2024_total'],'priority80':bool(r['priority80']),'native_constituents':[{'layer':'SOS county canvass','native_id':r['source_county_name'],'unit_type':'county total','votes':r['senate_2024_total']}],'finer_layers_status':'separate source-native identity extracts in development; VTDs are not native precincts'} for r in counties],'acceptance_status':'County counts and exact34-key priority accepted by coordinator; finer units source-scoped and not approved2026 geography'}
    dump('priority-set.json',priority)
    dump('county-build-controls.json',{'state_denominator':den,'senate_primary':dict(zip(SEN,selected['senate_state_control'][:-1])),'president_primary':dict(zip(PRES,selected['president_state_control'][:-1])),'medsl_county_candidate_cells_compared':len(primary),'vintage_candidate_differences':{v:{c:[(r['county'],r['values'],selected[c][i]['values']) for i,r in enumerate(src[c]) if r['values']!=selected[c][i]['values']] for c in ['senate','president']} for v,src in sources.items()},'top15_votes':top,'minimum80_count':k,'minimum80_votes':s80,'preceding_set_votes':prev,'crossing_county':counties[k-1]['county'],'remainder_votes':den-s80})
    print('Primary county build:',len(counties),'counties',len(candidate_rows),'candidate rows; denominator',den,'top15',top,'minimum80',k,s80,'preceding',prev)
if __name__=='__main__':
    main()
    from extend_turnout import extend
    extend()
    from inspect_primary_units import inspect
    inspect()
    from check_primary_controls import check
    check()
