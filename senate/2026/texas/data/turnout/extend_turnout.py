#!/usr/bin/env python3
"""Independent primary comparator extraction and lossless finer-source inventory."""
import csv,gzip,hashlib,io,json,re,collections,html
from pathlib import Path
from build_turnout import ROOT,STATE,RAW,writecsv,dump,readraw,csvraw
BASE=ROOT.parent/'baselines'

def primary_comparator(source,heading,n):
    text=(BASE/(source+'.txt')).read_text();pages=text.split('\f');start=next(i for i,p in enumerate(pages) if re.search(r'^'+re.escape(heading)+r'\s*$',p,re.M));out=[];control=None
    for pi in range(start,len(pages)):
        for line in pages[pi].splitlines():
            m=re.fullmatch(r'\s*([A-Z][A-Z .\'-]*?)\s{2,}([0-9,]+(?:\s+[0-9,]+)+)\s*',line)
            if not m:continue
            vals=[int(x.replace(',','')) for x in m[2].split()]
            if len(vals)!=n:continue
            row={'source_county_name':m[1].strip(),'values':vals,'source_pdf_page':pi+1,'source_line':line,'source_id':source}
            if row['source_county_name']=='TOTAL VOTES':control=row;break
            out.append(row)
        if control:break
    assert len(out)==254 and len({r['source_county_name'] for r in out})==254,(source,len(out))
    for r in out:assert sum(r['values'][:-1])==r['values'][-1],r
    assert [sum(r['values'][i] for r in out) for i in range(n)]==control['values']
    return out,control

def extend():
    counties=list(csv.DictReader(open(STATE/'data/county-turnout.csv')));fips={r['source_county_name']:r['county_fips'] for r in counties};canonical={r['county'].upper():r['county_fips'] for r in counties}
    canonical.update({'LA SALLE':'48283','HILDALGO':'48215'})
    primaryrows=[];controls={}
    early,ec=primary_comparator('sos2020-county-20201216','U. S. SENATOR',6)
    later,lc=primary_comparator('sos2020-county-20241003','U. S. SENATOR',6)
    assert [(r['source_county_name'],r['values']) for r in early]==[(r['source_county_name'],r['values']) for r in later]
    assert ec['values']==lc['values']
    dump('senate2020-vintage-check.json',{'status':'pass','earlier_source':'sos2020-county-20201216','selected_source':'sos2020-county-20241003','county_candidate_cells_compared':1270,'different_cells':0,'basis':'actual original table equality; no release/certification chronology inferred'})
    specs=[('sos2020-county-20241003','U. S. SENATOR',6,'2020-11-03','senate_2020',['JOHN CORNYN (I)','MARY "MJ" HEGAR','KERRY DOUGLAS MCKENNON','DAVID B. COLLINS','RICARDO TURULLOLS-BONILLA'],['REP','DEM','LIB','GRE','WRI']),('sos2022-county-20241003','GOVERNOR',7,'2022-11-08','governor_2022',['GREG ABBOTT (I)',"BETO O'ROURKE",'MARK TIPPETTS','DELILAH BARRIOS','JACQUELINE ABERNATHY','MARK V GOLOBY'],['REP','DEM','LIB','GRE','WRI','WRI'])]
    for source,heading,n,date,contest,names,parties in specs:
        rows,control=primary_comparator(source,heading,n);controls[contest]=control
        for r in rows:
            for i,name in enumerate(names):primaryrows.append({'election_date':date,'contest':contest,'county_fips':fips[r['source_county_name']],'source_county_name':r['source_county_name'],'source_county_code':'','source_candidate_name':name,'source_party':parties[i],'write_in':int(parties[i]=='WRI'),'votes':r['values'][i],'source_county_total':r['values'][-1],'source_id':source,'source_pdf_page':r['source_pdf_page']})
        by={fips[r['source_county_name']]:r for r in rows}
        for c in counties:
            vals=by[c['county_fips']]['values'];c[contest+'_total']=vals[-1];c[contest+'_r']=vals[0];c[contest+'_d']=vals[1];c[contest+'_other']=sum(vals[2:-1])
    writecsv(ROOT/'county-candidates-comparators.csv',primaryrows)
    writecsv(STATE/'data/county-turnout.csv',counties)
    dump('comparator-controls.json',controls)
    # Precinct source strings are never altered, deduplicated, or promoted to polygons.
    # Preserve all original fields for all selected contest/control rows; roster spans all offices.
    sourcefiles=[(p.stem.replace('.body',''),p,'2024') for p in sorted(RAW.glob('oe2024-*.body.gz'))]+[('oe-tx2022',RAW/'oe-tx2022.body.gz','2022'),('oe-tx2020',RAW/'oe-tx2020.body.gz','2020')]
    nativelist=[];diag=[];unmapped=[];nondata=[]
    for year in ['2024','2022','2020']:
        outpath=ROOT/('native-records-'+year+'.csv.gz')
        with gzip.open(outpath,'wt',newline='') as fp:
            fields=['source_id','source_row','year','county_fips','source_county_name','native_unit_id','source_office','source_district','source_candidate','source_party','record_role','votes','method_fields_json','source_fields_json'];w=csv.DictWriter(fp,fieldnames=fields);w.writeheader()
            for source,path,y in sourcefiles:
                if y!=year:continue
                units={};selected=[];duplicates=collections.Counter();negatives=[];methoddiff=[];countynames=set();candcounts=collections.Counter()
                with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as src:
                    reader=csv.DictReader(src)
                    for rn,r in enumerate(reader,2):
                        cname=r.get('county','');norm=cname.upper().strip();code=canonical.get(norm,'');countynames.add(cname)
                        if not code and year=='2024':
                            filename_county=source.removeprefix('oe2024-').replace('_',' ').upper();code=canonical.get(filename_county,'')
                        if cname=='county' and r.get('office')=='office':
                            nondata.append({'source_id':source,'source_row':rn,'reason':'repeated CSV column header, retained original; not a reporting-unit identity','source_fields':r});continue
                        if not code:unmapped.append((source,cname))
                        unit=r.get('precinct','');u=(cname,unit)
                        if u not in units:units[u]={'source_id':source,'year':year,'county_fips':code,'source_county_name':cname,'native_unit_id':unit,'native_unit_key':json.dumps([source,cname,unit],separators=(',',':')),'first_source_row':rn,'source_rows':0,'classification':'source precinct/ballot-style/reporting identity; physical/central type unverified','county_mapping_basis':'explicit aliases Hildalgo=>Hidalgo, La Salle=>Lasalle; missingcounty Angelina=>source filename; otherwise exact canonical name','unit_type_evidence':'none; names preserved without inferred polygon','observed_contests':set()}
                        units[u]['source_rows']+=1;office=r.get('office','');units[u]['observed_contests'].add(office)
                        office_key=re.sub('[^A-Z0-9]','',office.upper())
                        senate_keys={'USSENATE','USSENATOR','UNITEDSTATESSENATOR'}
                        president_keys={'PRESIDENT','PRESIDENTANDVICEPRESIDENT','PRESIDENTVICEPRESIDENT'}
                        governor_keys={'GOVERNOR','GOVERNORWRITEIN','GOVERNOR1'}
                        wanted=(office_key in ((senate_keys|president_keys) if year=='2024' else governor_keys if year=='2022' else senate_keys)) or office_key in {'REGISTEREDVOTERS','BALLOTSCAST','BALLOTSCASTTOTAL','BALLOTSCASTBLANK','VOTERSCAST','VOTERTURNOUT'}
                        if not wanted:continue
                        cand=r.get('candidate','');vv=r.get('votes','');role='candidate'
                        cl=cand.lower().strip()
                        if office.lower()=='registered voters':role='registration'
                        elif office_key in ['BALLOTSCAST','BALLOTSCASTTOTAL','BALLOTSCASTBLANK','VOTERSCAST','VOTERTURNOUT']:role='ballots_or_participation_source_label'
                        elif any(x in cl for x in ['under','over','blank','no candidate']):role='noncandidate_control'
                        elif cl in ['total','total votes','totalvotes']:role='contest_total_control'
                        elif cl in ['write-in','write in','write-ins','write ins','write-in totals']:role='generic_writein_scope_unresolved'
                        elif cl in ['','na','n/a']:role='unresolved'
                        methods={k:v for k,v in r.items() if k not in ['county','precinct','office','district','party','candidate','votes','id']}
                        record={'source_id':source,'source_row':rn,'year':year,'county_fips':code,'source_county_name':cname,'native_unit_id':unit,'source_office':office,'source_district':r.get('district',''),'source_candidate':cand,'source_party':r.get('party',''),'record_role':role,'votes':vv,'method_fields_json':json.dumps(methods,separators=(',',':')),'source_fields_json':json.dumps(r,separators=(',',':'))};w.writerow(record);selected.append(record)
                        key=(cname,unit,office,r.get('district',''),r.get('party',''),cand);duplicates[key]+=1
                        try:num=int(vv)
                        except (ValueError,TypeError):continue
                        if num<0:negatives.append(rn)
                        if role in ['candidate','generic_writein_scope_unresolved']:candcounts[(cname,office,cand)]+=num
                        vals=[int(v) for v in methods.values() if str(v).lstrip('-').isdigit()]
                        if vals and sum(vals)!=num:methoddiff.append({'row':rn,'votes':num,'numeric_method_sum':sum(vals),'methods':methods})
                for unit in units.values():unit['observed_contests']=sorted(unit['observed_contests']);nativelist.append(unit)
                diag.append({'source_id':source,'year':year,'counties':sorted(countynames),'filename_county_conflict':year=='2024' and any(c and c!='county' and c.upper().replace(' ','_')!=source.removeprefix('oe2024-').upper() for c in countynames),'units':len(units),'selected_rows':len(selected),'duplicate_candidate_keys':[{'key':list(k),'occurrences':n} for k,n in duplicates.items() if n>1],'negative_rows':negatives,'method_nonadditive_rows':methoddiff,'candidate_county_totals':[{'county':c,'office':o,'candidate':name,'sum_raw_rows':v} for (c,o,name),v in sorted(candcounts.items())]})
    assert not unmapped,sorted(set(unmapped))
    writecsv(ROOT/'native-reporting-units.csv.gz',nativelist)
    dump('native-source-diagnostics.json',diag)
    dump('source-row-anomalies.json',nondata)
    priority=json.load(open(ROOT/'priority-set.json'))
    for group in priority['groups']:
        group['native_constituents']=[x for x in group['native_constituents'] if x['layer']=='SOS county canvass']
        group['native_constituents'] += [{'layer':'OpenElections county-source derivative','source_id':r['source_id'],'year':r['year'],'source_county_name':r['source_county_name'],'native_id':r['native_unit_id'],'native_unit_key':r['native_unit_key'],'unit_type':r['classification']} for r in nativelist if r['county_fips']==group['county_fips']]
        group['finer_layers_status']='All observed OpenElections source reporting identities retained separately; 2024 incomplete, duplicates/method gaps not repaired. Derived TLC VTD identities stored in tlc-derived-vtd-units.csv.gz; no precinct equivalence assumed.'
    dump('priority-set.json',priority)
    # Preserve all VTD units as their own geographic layer and compare exactly to primary county/candidate controls.
    primary=list(csv.DictReader(open(ROOT/'county-candidates-2024.csv')))+list(csv.DictReader(open(ROOT/'county-candidates-comparators.csv')))
    pmap={(r['contest'],r['county_fips'],r['source_candidate_name']):int(r['votes']) for r in primary}
    names={'AllredD_24G_U.S. Sen':'COLIN ALLRED','AndrusW_24G_U.S. Sen':'TRACY ANDRUS','BrownL_24G_U.S. Sen':'TED BROWN','CruzR_24G_U.S. Sen':'TED CRUZ (I)','RocheW_24G_U.S. Sen':'ANALISA ROCHE'}
    vtd=[];recon=[];vtdkeys={}
    for source,contest in [('tlc-2024-senate-vtd','senate'),('tlc-2024-president-vtd','president'),('tlc-2024-voterdata-vtd','voterdata_2024'),('tlc-2022-governor-vtd','governor_2022'),('tlc-2022-voterdata-vtd','voterdata_2022')]:
        with gzip.open(ROOT.parent/'news'/(source+'.html.gz'),'rt',encoding='utf-8-sig') as fp:rows=list(csv.DictReader(fp))
        keys=[(r['CNTYVTD'],r['VTDKEY']) for r in rows];assert len(keys)==len(set(keys))==9712;assert len({r['CNTYVTD'][:3] for r in rows})==254
        vtdkeys[source]=keys;ag=collections.defaultdict(collections.Counter)
        for r in rows:
            code='48'+r['CNTYVTD'][:3];vtd.append({'source_id':source,'geography_type':'TLC derived2024 election VTD; not native precinct','county_fips':code,'CNTYVTD':r['CNTYVTD'],'VTDKEY':r['VTDKEY'],'source_fields_json':json.dumps(r,separators=(',',':'))})
            for k,val in r.items():
                if k not in ['CNTYVTD','VTDKEY'] and ('voterdata' not in source or k in ['Voter_Registration','Turnout']) and str(val).lstrip('-').isdigit():ag[code][k]+=int(val)
        for code,cs in ag.items():
            for name,num in cs.items():
                mapped=names.get(name,'')
                if contest=='president':
                    mapped={'HarrisD_24G_President':'KAMALA D. HARRIS/TIM WALZ','OliverL_24G_President':'CHASE OLIVER/MIKE TER MAAT','SteinG_24G_President':'JILL STEIN/RUDOLPH WARE','TrumpR_24G_President':'DONALD J. TRUMP/JD VANCE'}.get(name,'')
                if contest=='governor_2022':
                    mapped={'AbbottR_22G_Governor':'GREG ABBOTT (I)',"O'RourkeD_22G_Governor":"BETO O'ROURKE",'TippettsL_22G_Governor':'MARK TIPPETTS','BarriosG_22G_Governor':'DELILAH BARRIOS'}.get(name,'')
                pri=pmap.get((contest,code,mapped))
                if name.startswith('Write-In') and contest in ['president','governor_2022']:pri=sum(int(r['votes']) for r in primary if r['contest']==contest and r['county_fips']==code and r['write_in']=='1')
                recon.append({'source_id':source,'county_fips':code,'source_candidate_or_measure':name,'derived_count':num,'primary_count':pri if pri is not None else '', 'derived_minus_primary':num-pri if pri is not None else '', 'scope':'VTD derivative; generic write-in universe may differ'})
    assert all(ks==next(iter(vtdkeys.values())) for ks in vtdkeys.values())
    writecsv(ROOT/'tlc-derived-vtd-units.csv.gz',vtd);writecsv(ROOT/'tlc-county-reconciliation.csv',recon)
    dump('native-coverage-summary.json',{'years':{y:{'sources':sum(d['year']==y for d in diag),'county_fips':sorted({r['county_fips'] for r in nativelist if r['year']==y}),'units':sum(r['year']==y for r in nativelist),'selected_records':sum(d['selected_rows'] for d in diag if d['year']==y),'sources_with_duplicate_candidate_keys':sum(bool(d['duplicate_candidate_keys']) for d in diag if d['year']==y),'sources_with_method_nonadditivity':sum(bool(d['method_nonadditive_rows']) for d in diag if d['year']==y)} for y in ['2024','2022','2020']},'tlc_each_source_vtds':9712,'tlc_counties':254,'scope':'Source-native identifiers through pinned derivative; no primary all-precinct validation, unit deduplication, method repair or geographic crosswalk.'})
    print('Comparators and all observed finer identities built:',len(nativelist),'units',len(primaryrows),'primary candidate comparator rows')
if __name__=='__main__':extend()
