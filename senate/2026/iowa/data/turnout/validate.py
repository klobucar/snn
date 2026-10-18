#!/usr/bin/env python3
"""Offline audit: all counties/candidates, native controls, source differences, hashes and bounds."""
import csv,gzip,hashlib,json,re,os,subprocess
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import build as b

def read(name):
    p=b.ROOT/name
    with (gzip.open(p,'rt',newline='') if name.endswith('.gz') else p.open(newline='')) as f:return list(csv.DictReader(f))
def digfile(p):return dict(path=str(p.relative_to(b.ROOT)),sha256=b.sha(p.read_bytes()),bytes=p.stat().st_size)
def num(s):return None if s in [None,''] else int(s)
def peer_reconcile():
    peer=b.ROOT.parent/'baselines';a=read('canvass-candidate-method.csv')
    if not (peer/'canvass-candidate-method.csv').exists():return dict(status='pending')
    with (peer/'canvass-candidate-method.csv').open() as f:c=list(csv.DictReader(f))
    key=lambda r:(r['year'],r['county_fips'] or '19',r['native_method'],r['source_id'],r['source_column'])
    aa={key(r):r for r in a};cc={key(r):r for r in c};assert len(aa)==len(a)==len(cc)==len(c)==7484
    assert aa.keys()==cc.keys()
    differences=[]
    for k,x in aa.items():
        y=cc[k];label=y['candidate_or_metric_label']+(', '+y['party_header'] if y['party_header'] else '')
        for field,xv,yv in [('votes',x['votes'],y['votes']),('candidate_or_metric_label',x['candidate_or_metric_label'],label)]:
            if xv!=yv:differences.append(dict(key=list(k),field=field,turnout=xv,partisanship=yv))
    ours=read('../county-turnout.csv')
    with (peer/'priority-order.csv').open() as f:order=list(csv.DictReader(f))
    assert len(order)==len(ours)==99
    for x,y in zip(ours,order):
        for field,xv,yv in [('county',x['county'],y['county']),('FIPS',x['county_fips'],y['county_fips']),('rank',x['rank_2024'],y['rank']),('votes',x['pres2024_candidate_generic_writein_votes'],y['candidate_writein_votes']),('cumulative',x['cumulative_candidate_generic_writein_votes'],y['cumulative_votes']),('priority',x['in_minimum80'],y['priority80'])]:
            if xv!=yv:differences.append(dict(county=x['county'],field=field,turnout=xv,partisanship=yv))
    result=dict(status='pass' if not differences else 'differences',rows_compared=7484,county_numeric_cells=7425,state_numeric_cells=59,county_order_rows=99,explicit_aliases={'state_FIPS':'Turnout state code19 maps to peer blank only for original statewide footer rows','candidate_label':'Peer name + comma + printed party header compared to turnout full label'},differences=differences,peer_inputs=[dict(path=os.path.relpath(p,b.ROOT),sha256=b.sha(p.read_bytes()),bytes=p.stat().st_size) for p in [peer/'canvass-candidate-method.csv',peer/'priority-order.csv',peer/'priority.json',peer/'state-controls.csv',peer/'county-contests.csv']])
    b.dump('peer-reconciliation.json',result);return result

def main():
    checks={};sourcechecks=[]
    for r in b.SOURCES:
        assert 'path' in r,r
        raw=b.raw(r);assert len(raw)==r['original_bytes'];assert (b.ROOT/r['path']).stat().st_size==r['stored_bytes'];assert r['stored_bytes']<40000000
        sourcechecks.append(dict(source_id=r['id'],path=r['path'],status=r['status'],original_sha256=r['original_sha256'],stored_sha256=r['stored_sha256'],original_bytes=r['original_bytes'],stored_bytes=r['stored_bytes'],verified=True))
    checks['sources']=dict(count=len(sourcechecks),all_hashes_and_sizes_verified=True,http_status_counts=dict(Counter(str(r['status']) for r in b.SOURCES)))
    freshrequests=json.loads((b.ROOT/'reused-request-verification.json').read_text())
    for r in freshrequests:
        assert 'error' not in r,r
        stored=(b.ROOT/r['body_reference']).read_bytes();payload=gzip.decompress(stored)
        assert b.sha(payload)==r['original_sha256'] and len(payload)==r['original_bytes']
        if 'stored_sha256' in r:assert b.sha(stored)==r['stored_sha256'] and len(stored)==r['stored_bytes']
    checks['sources']['fresh_reused_request_payloads_verified']=len(freshrequests)
    textchecks=[]
    for p in sorted((b.ROOT/'text').glob('*.txt.gz')):
        source_id=p.name.removesuffix('.txt.gz');source=b.BYID[source_id]
        fresh=subprocess.run(['pdftotext','-layout','-','-'],input=b.raw(source),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        assert fresh.stdout==gzip.decompress(p.read_bytes()),source_id
        textchecks.append(dict(source_id=source_id,source_sha256=source['original_sha256'],text_sha256=b.sha(fresh.stdout),text_bytes=len(fresh.stdout),fresh_primary_PDF_extraction_matches=True))
    b.dump('pdf-text-verification.json',textchecks);checks['pdf_text_derivatives']=dict(fresh_primary_extractions_verified=len(textchecks),all_exact=True)
    # Run independent extractor assertions again, not merely a comparison of cached claims.
    wide,controls=b.canvasses();tr=b.turnout_reports()
    ranking=read('../county-turnout.csv');priority=json.loads((b.ROOT/'priority-set.json').read_text())
    assert len(ranking)==len({x['county_fips'] for x in ranking})==99
    expected=sorted(wide[2024],key=lambda c:(-sum(wide[2024][c][:-3]),b.COUNTIES[c]['county_fips']))
    assert [x['county'] for x in ranking]==expected
    den=controls['2024']['candidate_generic_writein_votes'];top=sum(sum(wide[2024][c][:-3]) for c in expected[:15]);running=0
    for i,c in enumerate(expected,1):
        prev=running;running+=sum(wide[2024][c][:-3])
        if running*5>=den*4:break
    assert i==priority['threshold']['minimum_count'] and prev==priority['threshold']['preceding_votes'] and running==priority['threshold']['votes']
    assert prev*5<den*4<=running*5 and sum(int(r['pres2024_candidate_generic_writein_votes']) for r in ranking)==den
    checks['county_controls']=dict(counties_per_election=99,county_contests=297,numeric_county_columns=2475,county_method_candidate_numeric_cells=7425,published_state_cells=59,all_county_candidate_column_sums_and_method_balances_exact=True)
    checks['priority']=dict(denominator=den,top15_votes=top,minimum_count=i,preceding_count=i-1,preceding_votes=prev,votes=running,crossing_county=c,crossing_county_fips=b.COUNTIES[c]['county_fips'],crossing_contribution=running-prev,integer_inequality=f'{5*prev} < {4*den} <= {5*running}')
    canv=read('canvass-candidate-method.csv');canvals={(r['year'],r['county_fips'],r['native_method'],r['candidate_or_metric_label']):int(r['votes']) for r in canv}
    methoddiff=[]
    for r in tr:
        for field,method in [('election_day_voters','Election Day'),('absentee_voters','Absentee'),('total_voters','Total')]:
            key=(str(r['year']),r['county_fips'],method,'Total')
            if key in canvals:
                other=canvals[key]
                if r[field]!=other:methoddiff.append(dict(year=r['year'],county=r['county'],county_fips=r['county_fips'],method=method,turnout_report_voters=r[field],canvass_reported_contest_total=other,difference=r[field]-other,cause='not inferred'))
    b.dump('turnout-canvass-method-differences.json',methoddiff)
    units=read('native-units.csv');native=read('native-unit-candidate-method.csv');assert len({r['unit_key'] for r in units})==len(units)
    assert len({(r['source_id'],r['source_sheet'],r['source_row'],r['source_column']) for r in native})==len(native)
    byunit=defaultdict(dict);bycounty=defaultdict(list)
    for r in native:
        method='Total' if r['native_method']=='Total Votes' else r['native_method'];byunit[r['unit_key'],r['native_candidate_label']][method]=num(r['votes'])
        bycounty[r['year'],r['county_fips'],r['native_candidate_label'],method,r['unit_kind']=='source_county_total'].append(num(r['votes']))
    unitimbal=[]
    for k,v in byunit.items():
        if all(m in v and v[m] is not None for m in ['Election Day','Absentee','Total']) and v['Election Day']+v['Absentee']!=v['Total']:unitimbal.append(dict(key=k,counts=v))
    comparisons=[]
    for year in ['2022','2020']:
        for county,co in b.COUNTIES.items():
            assert any(r['year']==year and r['county_fips']==co['county_fips'] and r['unit_kind']=='source_county_total' for r in units),(year,county)
            for clabel in b.LABELS[int(year)]:
                native_label=clabel.rsplit(', ',1)[0] if clabel.rsplit(', ',1)[-1] in ['REP','DEM','LIB'] else clabel
                if native_label=='Under Votes':native_label='Undervotes'
                if native_label=='Over Votes':native_label='Overvotes'
                # Workbook exports provide candidates/Write-in; only Scott PDF also has under/over/Total.
                for method in ['Election Day','Absentee','Total']:
                    a=bycounty.get((year,co['county_fips'],native_label,method,False));ct=bycounty.get((year,co['county_fips'],native_label,method,True));control=canvals[year,co['county_fips'],method,clabel]
                    agg=sum(a) if a and all(v is not None for v in a) else None
                    total=ct[0] if ct and len(ct)==1 else None
                    comparisons.append(dict(year=year,county=county,county_fips=co['county_fips'],native_candidate_or_metric=native_label,canvass_label=clabel,method=method,constituent_rows=len(a) if a else 0,constituent_sum=agg,native_county_control=total,canvass_control=control,constituent_minus_native_control=agg-total if agg is not None and total is not None else None,constituent_minus_canvass=agg-control if agg is not None else None,status='unavailable_in_workbook' if agg is None else 'exact' if agg==control and (total is None or agg==total) else 'source_difference'))
    b.csvout('native-candidate-reconciliation.csv',comparisons);b.dump('native-unit-method-imbalances.json',unitimbal)
    diff=[r for r in comparisons if r['status']=='source_difference'];avail=[r for r in comparisons if r['constituent_sum'] is not None]
    checks['native_candidate_scope']=dict(unit_rows=len(units),candidate_metric_cells=len(native),constituents_by_year=dict(Counter(r['year'] for r in units if r['unit_kind']!='source_county_total')),administrative_total_rows=dict(Counter(r['year'] for r in units if r['unit_kind']=='source_county_total')),missing_vote_cells=sum(r['votes']=='' for r in native),unique_source_cell_keys=True,unique_unit_keys=True,per_unit_method_imbalances=len(unitimbal),available_county_candidate_method_comparisons=len(avail),source_differences=len(diff),unavailable_metric_comparisons=sum(r['status']=='unavailable_in_workbook' for r in comparisons),source_differences_retained=diff)
    # Statistics controls: every numeric age row, each precinct total -> county Grand Totals.
    stats=read('statistics-rows.csv.gz');su=read('statistics-units.csv');assert len({r['unit_key'] for r in su})==len(su)
    ages=['age17','age18_24','age25_34','age35_49','age50_64','age65_plus','age_unknown'];statimbal=[];st=defaultdict(list)
    for r in stats:
        if r['metric']=='TURNOUT':continue
        if sum(int(r[a]) for a in ages)!=int(r['total']):statimbal.append(dict(source_id=r['source_id'],page=r['source_page'],line=r['source_page_line'],age_sum=sum(int(r[a]) for a in ages),reported_total=int(r['total'])))
        if r['demographic_category'] in ['Total','Grand Totals']:st[r['year'],r['source_kind'],r['county_fips'],r['demographic_category'],r['metric']].append(r)
    statrec=[]
    for year in ['2024','2022','2020']:
        for county,co in b.COUNTIES.items():
            for metric in ['REGISTERED','TOTAL VOTED','ABSENTEE']:
                parts=st.get((year,'precinctstats',co['county_fips'],'Total',metric),[]);gr=st.get((year,'precinctstats',co['county_fips'],'Grand Totals',metric),[])
                for age in ages+['total']:
                    actual=sum(int(r[age]) for r in parts) if parts else None;control=int(gr[0][age]) if len(gr)==1 else None
                    statrec.append(dict(year=year,county=county,county_fips=co['county_fips'],metric=metric,age_scope=age,constituent_unit_count=len(parts),precinct_total_sum=actual,precinct_report_grand_total=control,difference=actual-control if actual is not None and control is not None else None,status='exact' if actual is not None and actual==control else 'missing_control' if control is None else 'source_difference'))
    b.csvout('statistics-unit-reconciliation.csv',statrec);b.dump('statistics-age-imbalances.json',statimbal)
    # Cross-source statistical totals never replace the report's own controls.
    statcross=[]
    for year in ['2024','2022','2020']:
        for fips in list(x['county_fips'] for x in b.COUNTIES.values())+['19']:
            for metric in ['REGISTERED','TOTAL VOTED','ABSENTEE']:
                values={}
                for kind in ['precinctstats','countystats','statestats']:
                    cats=['Grand Totals'] if kind in ['precinctstats','statestats'] or fips=='19' else ['Total']
                    found=[r for cat in cats for r in st.get((year,kind,fips,cat,metric),[])]
                    values[kind]=int(found[0]['total']) if len(found)==1 else None
                statcross.append(dict(year=year,county_fips=fips,metric=metric,**values))
    b.csvout('statistics-source-controls.csv',statcross)
    statestate=[]
    for year in ['2024','2022','2020']:
        for metric in ['REGISTERED','TOTAL VOTED','ABSENTEE']:
            for age in ages+['total']:
                pc=[r for (y,k,f,c,m),v in st.items() if y==year and k=='precinctstats' and f!='19' and c=='Grand Totals' and m==metric for r in v]
                cc=[r for (y,k,f,c,m),v in st.items() if y==year and k=='countystats' and f!='19' and c=='Total' and m==metric for r in v]
                cf=st.get((year,'countystats','19','Grand Totals',metric),[]);sf=st.get((year,'statestats','19','Grand Totals',metric),[])
                assert len(pc)==99
                p_sum=sum(int(r[age]) for r in pc);c_sum=sum(int(r[age]) for r in cc)
                statestate.append(dict(year=year,metric=metric,age_scope=age,precinct_county_coverage=len(pc),precinct_county_grand_total_sum=p_sum,county_report_coverage=len(cc),county_report_county_total_sum=c_sum,county_report_state_footer=int(cf[0][age]) if len(cf)==1 else None,state_report_footer=int(sf[0][age]) if len(sf)==1 else None,county_report_own_footer_difference=c_sum-int(cf[0][age]) if len(cf)==1 else None,precinct_sum_minus_state_report=p_sum-int(sf[0][age]) if len(sf)==1 else None))
    b.csvout('statistics-state-reconciliation.csv',statestate)
    checks['statistics']=dict(rows=len(stats),native_label_counts=dict(Counter(r['year'] for r in su)),unit_age_metric_comparisons=len(statrec),unit_control_status=dict(Counter(r['status'] for r in statrec)),age_row_imbalances=len(statimbal),unit_keys_unique=True,county_coverage_by_year={y:len({r['county_fips'] for r in su if r['year']==y}) for y in ['2024','2022','2020']})
    checks['statistics']['state_reconciliation_total_columns']=[r for r in statestate if r['age_scope']=='total']
    cass=json.loads((b.ROOT/'cass-summary-transcription.json').read_text())
    for label,v in cass['candidate_votes'].items():assert canvals['2024','19029','Total',label]==v
    assert sum(cass['candidate_votes'].values())==cass['presidential_candidate_generic_writein_votes']
    assert cass['presidential_candidate_generic_writein_votes']+cass['under_votes']+cass['over_votes']==cass['total_ballots']==canvals['2024','19029','Total','Total']
    checks['cass_summary']=dict(candidate_columns_and_under_over_total_match_state_canvass=True,source_status=cass['source_status'],source_clock=cass['source_clock_literal'],method_header_not_used_as_method_scope=True)
    peer=peer_reconcile();checks['peer']=peer
    fullpeer=json.loads((b.ROOT/'full-peer-reconciliation.json').read_text());assert fullpeer['status']=='pass';checks['full_peer_source_fields']=dict(status=fullpeer['status'],path='full-peer-reconciliation.json',groups={k:dict(rows=v['rows'],status=v['status']) for k,v in fullpeer.items() if isinstance(v,dict)})
    claritycheck=json.loads((b.ROOT/'clarity-2024-validation.json').read_text());checks['clarity_2024']={k:v for k,v in claritycheck.items() if k!='context_differences'}
    cunit=read('clarity-2024-native-units.csv');cstatus=read('clarity-2024-status-units.csv');roster=json.loads((b.ROOT/'clarity-county-roster.json').read_text())
    peer_native=b.ROOT.parent/'baselines/peer-reconciliation.json'
    if peer_native.exists():
        peercheck=json.loads(peer_native.read_text());checks['peer_native_reverse_audit']=dict(path='../baselines/peer-reconciliation.json',sha256=b.sha(peer_native.read_bytes()),status=peercheck.get('status'),scope=peercheck.get('scope'))
    # Attach complete source-scoped constituents without combining different objects.
    for row in priority['all_counties']:
        fips=row['county_fips'];row['native_constituents']={}
        for year in ['2024','2022','2020']:
            uu=[r for r in units if r['county_fips']==fips and r['year']==year];ss=[r for r in su if r['county_fips']==fips and r['year']==year]
            row['native_constituents'][year]=dict(candidate_reporting_units=[r for r in uu if r['unit_kind']!='source_county_total'],candidate_administrative_controls=[r for r in uu if r['unit_kind']=='source_county_total'],registration_statistics_units=ss,candidate_unit_status='available; reconciled source differences in native-candidate-reconciliation.csv' if uu else 'unavailable: actual linked2024 Clarity app403; county summary/method controls do not establish finer candidate allocation',physical_precinct_status='not established by reporting rows',split_ballot_style_status='not separately established',central_absentee_status='method columns preserved; no separate central-absentee unit/polygon inferred',polling_places_status='unavailable in these result/statistics sources',crosswalk_to_2026_status='unavailable/unapproved')
        cu=[r for r in cunit if r['county_fips']==fips];cs=[r for r in cstatus if r['county_fips']==fips];scope=row['native_constituents']['2024'];scope['candidate_reporting_units']=[r for r in cu if 'Contest_Precinct' in r['unit_kind']];scope['turnout_context_units']=[r for r in cu if 'Contest_Precinct' not in r['unit_kind']];scope['status_context_units']=cs;scope['candidate_unit_status']='available from actual historical county XMLs; all candidate/method controls match canvass; registration/ballot context differences retained';scope['native_source_roster']=next(r for r in roster if r['county_fips']==fips);scope['candidate_administrative_controls']=[dict(source_id=f'sos-2024-county-xml-{fips}',scope='county Choice totalVotes and VoteType votes',extract='clarity-2024-county-candidate-method.csv')];scope['under_over_unit_status']='unavailable in selected county XML; county canvass method values retained, no residual allocation'
    priority['threshold']['crossing_contribution']=running-prev
    priority['priority_county_fips']=[r['county_fips'] for r in ranking[:i]]
    priority['remainder_county_fips']=[r['county_fips'] for r in ranking[i:]]
    priority['native_constituents_status']='complete retained native source contexts:2024 candidate1653/turnout1651/status1653,2022 Senate1653,2020 Senate1661,plus4990registration-statistics labels; no cross-context/cross-year/2026 geography equivalence presumed'
    priority['acceptance_status']='county and source-scoped native research contract accepted by coordinator independent reviews; no spatial/current geography approval'
    coordinator=b.ROOT.parent/'coordinator-baseline-reconciliation.json'
    if coordinator.exists():priority['coordinator_county_review']=dict(path='../coordinator-baseline-reconciliation.json',scope='county priority only; never current/finer-unit geography approval; audit pins this contract, so this reference intentionally has no reverse hash')
    coordinator_native=b.ROOT.parent/'coordinator-native-contract-checks.json'
    if coordinator_native.exists():priority['coordinator_native_review']=dict(path='../coordinator-native-contract-checks.json',scope='exact13558 source-context objects and99rosters conserved; no spatial/current approval; audit pins this contract, so this reference intentionally has no reverse hash')
    b.dump('priority-set.json',priority)
    # Local Markdown references, including report, must resolve.
    linkerrors=[]
    for p in [b.ROOT/'SCHEMA.md',b.ROOT.parent.parent/'turnout.md']:
        if not p.exists():continue
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',p.read_text()):
            if '://' in target or target.startswith('#'):continue
            path=target.split('#',1)[0]
            if not (p.parent/path).exists():linkerrors.append(dict(file=str(p),target=target))
    assert not linkerrors,linkerrors
    # Reproducible manifests intentionally exclude themselves and the timestamped validation result.
    files=[digfile(p) for p in sorted(b.ROOT.rglob('*')) if p.is_file() and p.name not in ['asset-manifest.json','validation.json'] and '__pycache__' not in str(p)]
    countycsv=b.ROOT.parent/'county-turnout.csv';report=b.ROOT.parent.parent/'turnout.md'
    for p in [countycsv,report]:
        if p.exists():files.append(dict(path=os.path.relpath(p,b.ROOT),sha256=b.sha(p.read_bytes()),bytes=p.stat().st_size))
    assert all(r['bytes']<40000000 for r in files)
    b.dump('asset-manifest.json',dict(scope='owned turnout assets; manifest and validation excluded to avoid circular hashes',assets=files,reused_primary_assets=sourcechecks))
    checks['artifacts']=dict(count=len(files),max_stored_bytes=max(r['bytes'] for r in files),all_strictly_below_40000000=True,local_links_valid=True)
    checks['checked_utc']=datetime.now(timezone.utc).isoformat();checks['status']='pass_with_source_gaps' if not unitimbal and not statimbal and not diff and not any(r['status']!='exact' for r in statrec) and peer.get('status')=='pass' else 'completed_with_retained_discrepancies'
    checks['gaps']=['2024 actual app initial403 recovered via later200; both observations retained','generic write-in scope is not named-valid allocation','2024 Lucas turnoutXML omits2 candidate/statusunits; ballots gap1943 retained, not allocated','2024 county XML partylabels differ from state for Stodden in14counties; all numericvotesmatch','2024 93county registration unit sums differ from county controls; literalzero contexts not treated as meaningful registry completeness','report/source statistical snapshots differ from canvass/turnout scopes;2020state agebin+2 retained','no approved2026 physical/reporting/polling-place/cross-year crosswalk']
    b.dump('validation.json',checks)
    print(json.dumps({k:v for k,v in checks.items() if k not in ['peer','native_candidate_scope']},indent=2));print('native differences',len(diff),'unit imbalances',len(unitimbal),'peer',peer.get('status'),len(peer.get('differences',[])))
if __name__=='__main__':main()
