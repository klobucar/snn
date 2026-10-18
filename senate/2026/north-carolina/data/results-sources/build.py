#!/usr/bin/env python3
"""Offline source/reconciliation build. Writes only this assignment's paths.

Inputs in ../turnout are READ ONLY independent certified extracts and original
ZIPs. Dashboard/media samples are original decoded HTTP bodies in *.body.gz.
Missing candidate PDF rows contribute no votes; that does not invent source rows.
"""
from collections import Counter, defaultdict
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parent
DATA=ROOT.parent
FIELDS={'vct':'total_votes','evc':'election_day','ovc':'early_voting','avc':'absentee_by_mail','pvc':'provisional'}
METHODS=list(FIELDS.values())
TURNOUT=DATA/'turnout'

def body(k): return gzip.decompress((ROOT/meta(k)['saved_file']).read_bytes())
def obj(k): return json.loads(body(k).decode('utf-8-sig'))
def meta(k): return json.loads((ROOT/(k+'.meta.json')).read_text())
def save(k,x): (ROOT/k).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def writecsv(path,rows):
    assert rows
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def zipped(k):
    with zipfile.ZipFile(io.BytesIO(body(k))) as z:
        assert len(z.namelist())==1
        return z.namelist()[0],z.read(z.namelist()[0]).decode('utf-8-sig')
def ziprows(path):
    with zipfile.ZipFile(path) as z:
        return list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig')),delimiter='\t'))

def main():
    counties=list(csv.DictReader((DATA/'county-turnout.csv').open()))
    directory=json.loads((ROOT/'directory-counties.json').read_text())
    bynative={r['county_native']:r for r in counties}
    assert len(counties)==len(directory)==100
    assert len({r['county_fips'] for r in counties})==100
    assert {(str(r['ID']),r['Name']) for r in directory}=={(r['ncsbe_county_id'],r['county_native']) for r in counties}
    priority=[r for r in counties if r['research_priority']=='1']
    assert len(priority)==38 and sum(int(r['president_2024_total']) for r in priority)==4576486
    certified=list(csv.DictReader((TURNOUT/'certified-candidate-extract.csv').open()))
    cert={(r['year'],r['county_native'],r['candidate']):r for r in certified}
    normalized=[]; statewide=[]; differences=[]; zipdiff=[]; county_totals={}; candidate_checks=[]
    for year,group in [('2024','1393'),('2022','1378')]:
        totals=defaultdict(Counter)
        for c in counties:
            sid='results-'+year+'-'+c['ncsbe_county_id'].zfill(3)
            rows=[r for r in obj(sid) if r['gid']==group]
            assert rows and len({r['bnm'] for r in rows})==len(rows)
            assert {r['cid'] for r in rows}=={c['ncsbe_county_id']}
            county_totals[year,c['county_native']]=sum(int(r['vct']) for r in rows)
            for r in rows:
                vals={v:int(r[k]) for k,v in FIELDS.items()}
                assert vals['total_votes']==sum(vals[k] for k in METHODS[1:])
                totals[r['bnm']].update(vals)
                normalized.append(dict(year=year,county=c['county'],county_native=c['county_native'],county_fips=c['county_fips'],
                    ncsbe_county_id=c['ncsbe_county_id'],group_id=r['gid'],local_contest_id=r['lid'],candidate=r['bnm'],party=r['pty'],
                    **vals,source_id=sid,source_retrieved_utc=meta(sid)['retrieved_utc']))
                other=cert.get((year,c['county_native'],r['bnm']),{})
                for field in METHODS:
                    cv=int(other.get(field,0));dv=vals[field]
                    if cv!=dv:differences.append(dict(year=year,county=c['county'],candidate=r['bnm'],field=field,dashboard=dv,certified=cv,dashboard_minus_certified=dv-cv))
        state=[r for r in obj('results-'+year+'-state') if r['gid']==group]
        assert set(totals)=={r['bnm'] for r in state}
        assert {r['candidate'] for r in certified if r['year']==year}==set(totals)
        for r in state:
            for k,v in FIELDS.items():
                dv=int(r[k]);cs=sum(int(x[v]) for x in certified if x['year']==year and x['county_native']!='STATE' and x['candidate']==r['bnm'])
                assert totals[r['bnm']][v]==dv
                candidate_checks.append(dict(year=year,candidate=r['bnm'],field=v,county_dashboard_sum=totals[r['bnm']][v],state_dashboard=dv,certified_county_sum=cs,dashboard_minus_certified=dv-cs))
            statewide.append(dict(year=year,group_id=group,candidate=r['bnm'],party=r['pty'],**{v:int(r[k]) for k,v in FIELDS.items()}))
        # Independently compare every candidate/method against the saved ordinary
        # Election Results ZIP. Never read the distinct Precinct Sorted product.
        zr=ziprows(TURNOUT/f'results_pct_{year}{"1105" if year=="2024" else "1108"}.zip')
        ztot=defaultdict(Counter)
        zfields={'total_votes':'Total Votes','election_day':'Election Day','early_voting':'Early Voting','absentee_by_mail':'Absentee by Mail','provisional':'Provisional'}
        if year=='2022':zfields['early_voting']='One Stop'
        for r in zr:
            if r['Contest Group ID']!=group:continue
            ztot[r['County'],r['Choice']].update({k:int(r[v]) for k,v in zfields.items()})
        for r in [x for x in normalized if x['year']==year]:
            for k in METHODS:
                if ztot[r['county_native'],r['candidate']][k]!=r[k]:zipdiff.append((year,r['county'],r['candidate'],k))
    assert not zipdiff
    assert len(differences)==10 # four candidate totals and six method differences
    assert {r['county'] for r in differences}=={'Mitchell','Rowan'}
    assert all(r['year']=='2024' for r in differences)
    assert sum(r['total_votes'] for r in statewide if r['year']=='2022')==3773924
    assert sum(r['total_votes'] for r in statewide if r['year']=='2024')==5699141
    writecsv(ROOT/'dashboard-candidates.csv',normalized)
    writecsv(ROOT/'dashboard-state-candidates.csv',statewide)
    writecsv(ROOT/'historical-candidate-checks.csv',candidate_checks)
    writecsv(ROOT/'dashboard-certified-differences.csv',differences)

    # Exact complete historical detailed sample: all methods and all 237 units.
    pr=[r for r in obj('precinct-2024-wake') if r['lid']=='1393']
    w=[r for r in normalized if r['year']=='2024' and r['ncsbe_county_id']=='92']
    assert len({r['aid'] for r in pr})==237
    assert len({(r['aid'],r['bnm']) for r in pr})==len(pr)
    aliases={'Claudia De la Cruz':'Claudia De la Cruz (Write-In)','Shiva Ayyadurai':'Shiva Ayyadurai (Write-In)'}
    assert {aliases.get(r['bnm'],r['bnm']) for r in pr}=={c['candidate'] for c in w}
    for c in w:
        for k,v in FIELDS.items():assert sum(int(r[k]) for r in pr if aliases.get(r['bnm'],r['bnm'])==c['candidate'])==c[v]
    for r in pr:assert int(r['vct'])==sum(int(r[k]) for k in ['evc','ovc','avc','pvc'])
    writecsv(ROOT/'wake-2024-president-units.csv',[dict(ncsbe_county_id='92',group_id='1393',canonical_candidate=aliases.get(r['bnm'],r['bnm']),**r) for r in pr])

    # Current catalog, state rows and ordinary media download are setup evidence.
    assert '11/03/2026' in {r['edt'] for r in obj('elections')}
    current=obj('county-2026'); assert len(current)==101
    assert {r['cid'] for r in current}=={str(i) for i in range(101)}
    assert all(int(r['bct'])==int(r['prt'])==0 for r in current)
    senate=[r for r in obj('results-2026-state') if r['gid']=='1383']
    assert {(r['bnm'],r['pty']) for r in senate}=={('Roy Cooper','DEM'),('Michael Whatley','REP'),('Michael Dublin','GRE'),('Shannon W. Bray','LIB')}
    assert all(int(r[k])==0 for r in obj('results-2026-state') for k in FIELDS)
    for c in priority:
        rows=obj('results-2026-'+c['ncsbe_county_id'].zfill(3))
        assert all(int(r[k])==0 for r in rows for k in FIELDS)
        assert {(r['bnm'],r['gid']) for r in rows if r['gid']=='1383'}=={(r['bnm'],'1383') for r in senate}
    zn,zt=zipped('media-2026');media=list(csv.DictReader(io.StringIO(zt),delimiter='\t'))
    assert {r['County'] for r in media}==set(bynative)
    assert {r['Election Date'] for r in media}=={'11/03/2026'}
    assert all(int(r[k])==0 for r in media for k in ['Election Day','Early Voting','Absentee by Mail','Provisional','Total Votes'])
    ms=[r for r in media if r['Contest Group ID']=='1383']
    assert {r['County'] for r in ms}==set(bynative)
    mu=defaultdict(dict)
    for r in ms:mu[r['County']][r['Precinct']]=r['Real Precinct']
    assert all(list(mu[r['cnm']].values()).count('Y')==int(r['ptl']) for r in current if r['cid']!='0')
    cp=obj('precinct-2026-wilson')
    assert all(r['sta']=='Not Reported' and int(r['vct'])==0 for r in cp)
    save('current-setup-checks.json',dict(media_member=zn,media_rows=len(media),senate_rows=len(ms),media_senate_units=sum(len(x) for x in mu.values()),
        real_senate_units=sum(list(x.values()).count('Y') for x in mu.values()),administrative_senate_units=sum(list(x.values()).count('N') for x in mu.values()),
        senate_candidates=senate,state_county_record=current[0],all_100_counties=True,priority_county_json=38,
        voting_fields_all_zero=True,wilson_precinct_rows=len(cp),wilson_units=len({r['aid'] for r in cp}),classification='zero setup scaffold; no explicit test flag observed; not votes counted'))
    writecsv(ROOT/'current-senate-county-units.csv',[dict(county=bynative[k]['county'],county_fips=bynative[k]['county_fips'],ncsbe_county_id=bynative[k]['ncsbe_county_id'],
        reporting_units=len(mu[k]),real_units=list(mu[k].values()).count('Y'),administrative_units=list(mu[k].values()).count('N'),
        reported=next(r['prt'] for r in current if r['cnm']==k),dashboard_total=next(r['ptl'] for r in current if r['cnm']==k)) for k in bynative])

    # Actually inspect the current aggregate outstanding file, without voter PII.
    _,ot=zipped('outstanding-2026');outstanding=list(csv.DictReader(io.StringIO(ot)))
    assert len(outstanding)==100 and {r['county_name'] for r in outstanding}==set(bynative)
    nums=['abs_sent','abs_accepted','abs_spoiled_EV','abs_received_not_counted','abs_outstanding']
    outstanding_checks={k:sum(int(r[k]) for r in outstanding) for k in nums}
    outstanding_checks.update(counties=100,election_dates=sorted({r['election_date'] for r in outstanding}),
       spoiled_greater_than_received_not_counted=[r['county_name'] for r in outstanding if int(r['abs_spoiled_EV'])>int(r['abs_received_not_counted'])],
       sent_balance_exceptions=[r['county_name'] for r in outstanding if int(r['abs_sent'])!=sum(int(r[k]) for k in ['abs_accepted','abs_received_not_counted','abs_outstanding'])],
       warning='Documentation says Spoiled - EV is in both columns; observed subset inequality fails in listed counties. Do not repair, add both columns, or equate outstanding absentee with remaining candidate votes.')
    stats=list(csv.DictReader(io.StringIO(body('absentee-counts-state').decode('utf-8-sig'))))
    outstanding_checks['counts_state_header']=list(stats[0]);outstanding_checks['counts_state_rows']=len(stats)
    outstanding_checks['counts_state_last_column_sum']=sum(int(list(r.values())[-1]) for r in stats)
    save('outstanding-checks.json',outstanding_checks)
    writecsv(ROOT/'outstanding-2026-counties.csv',outstanding)

    comparisons=[]
    for key in ['county-2026','results-2026-state','media-2026','outstanding-2026']:
        a,b=meta(key),meta(key+'-repeat')
        comparisons.append(dict(source_id=key,first_utc=a['retrieved_utc'],second_utc=b['retrieved_utc'],
            elapsed_seconds=(datetime.datetime.fromisoformat(b['retrieved_utc'])-datetime.datetime.fromisoformat(a['retrieved_utc'])).total_seconds(),
            unchanged_body=a['sha256']==b['sha256'],first_sha256=a['sha256'],second_sha256=b['sha256']))
    save('observed-stability.json',comparisons)

    # Discovery is exhaustive for saved anchor/iframe URLs, not an assertion that
    # every link or dynamically generated resource on every local site was tested.
    discovery={}
    for c in counties:
        sid='county-'+c['ncsbe_county_id'].zfill(3);links=[]
        for f in sorted(ROOT.glob(sid+'*.page.json')):
            d=json.loads(f.read_text())
            for r in d['links']:
                if r['tag'] in ('a','iframe') and any(k in (r['label']+' '+r['url']).lower() for k in ['result','canvass','er.ncsbe']):
                    if 'search/results' in r['url'].lower():continue
                    links.append(dict(source_id=f.name.replace('.page.json',''),**r))
        discovery[c['county']]=links
    save('county-discovery.json',discovery)
    notes=json.loads((ROOT/'priority-notes.json').read_text())
    assert set(notes)=={r['county'] for r in priority}
    inventory=[]; coverage=[]
    for c in counties:
        sid='county-'+c['ncsbe_county_id'].zfill(3);m=meta(sid);n=notes.get(c['county'],{})
        cur=next(r for r in current if r['cid']==c['ncsbe_county_id'])
        resultlinks=list(dict.fromkeys(r['url'] for r in discovery[c['county']]))
        inventory.append(dict(source_id='nc-county-'+c['county_fips'],scope='county',county=c['county'],county_fips=c['county_fips'],ncsbe_county_id=c['ncsbe_county_id'],
            rank_2024=c['rank_2024'],priority=c['research_priority'],publisher=next(x['OfficeName'] for x in directory if str(x['ID'])==c['ncsbe_county_id']),
            authority_url=meta('directory')['url'],directory_website_url=next(x['WebsiteAddr'] for x in directory if str(x['ID'])==c['ncsbe_county_id']),
            landing_final_url=m['final_url'],landing_http_status=m['http_status'],landing_curl_exit=m['curl_exit'],landing_retrieved_utc=m['retrieved_utc'],
            landing_evidence=sid+'.meta.json',discovered_local_results_urls=json.dumps(resultlinks),
            local_inspection=n.get('finding','Directory landing and extracted links inspected; deeper local publication untested.'),
            local_gap=n.get('gap','November local channel and any independently published detailed data not deeply tested.'),
            local_followup_sources=';'.join(n.get('sources',[])),
            shared_state_results_url=meta('state-results')['url'],current_media_url=meta('media-2026')['url'],current_media_evidence='media-2026.meta.json',
            current_media_county_coverage='inspected; zero setup',current_senate_group_id='1383',
            current_county_json_source='results-2026-'+c['ncsbe_county_id'].zfill(3) if c['research_priority']=='1' else '',
            current_source_upload_literal=cur['imp'],current_source_submit_literal=cur['sub'],source_timestamp_timezone='not stated in downloaded JSON',
            current_precincts_reported=cur['prt'],current_precincts_total=cur['ptl'],
            historical_json_sources='results-2024-'+c['ncsbe_county_id'].zfill(3)+';results-2022-'+c['ncsbe_county_id'].zfill(3),
            methods='Election Day;Early Voting/One Stop;Absentee by Mail;Provisional',
            overlap='State dashboard/media and local state links overlap; county/precinct/PDF are replacement observations, never additions.',
            precedence='Certified abstracts for historical baseline; coherent state county snapshot for proposed live counts; verified newer county correction only with explicit provenance.',
            outstanding_source='outstanding-2026; aggregate administrative absentee only; candidate-vote remainder unknown',
            measured_live_cadence='untested',completion_semantics='native precinct/unit counts; not percent of votes counted'))
        coverage.append(dict(county=c['county'],county_fips=c['county_fips'],ncsbe_county_id=c['ncsbe_county_id'],priority=c['research_priority'],
            local_landing_http_status=m['http_status'],local_landing_curl_exit=m['curl_exit'],
            historical_dashboard_2024_president=county_totals['2024',c['county_native']],certified_2024_president=int(c['president_2024_total']),
            historical_dashboard_2022_senate=county_totals['2022',c['county_native']],certified_2022_senate=int(c['senate_2022_total']),
            current_media_senate_units=len(mu[c['county_native']]),current_county_json_tested=c['research_priority'],
            outstanding_aggregate_row_present='1',local_gap=inventory[-1]['local_gap'],live_updates_and_outstanding_candidate_votes='unverified'))
    for source_id,key,description in [
        ('nc-state-dashboard','dashboard','Public election catalog, county/contest summaries and method/unit details; November is zero setup.'),
        ('nc-state-media','media-2026','Downloads app generates Election Night Media Results and Precinct Election Results links to the SAME ordinary results ZIP.'),
        ('nc-state-certified-history','state-history','Certified county/state abstracts govern historical baselines; distinct Precinct Sorted datasets carry statistical noise.'),
        ('nc-state-outstanding','outstanding-2026','Actually downloaded 100-county aggregate absentee administrative file; documentation/field conflict remains; not exact remaining candidate votes.')]:
        m=meta(key);row={k:'' for k in inventory[0]};row.update(source_id=source_id,scope='statewide',publisher='North Carolina State Board of Elections',
            authority_url=meta('state-results')['url'] if key!='outstanding-2026' else meta('outstanding-summary')['url'],
            landing_final_url=m['final_url'],landing_http_status=m['http_status'],landing_curl_exit=m['curl_exit'],landing_retrieved_utc=m['retrieved_utc'],
            landing_evidence=key+'.meta.json',local_inspection=description,methods='Election Day;Early Voting/One Stop;Absentee by Mail;Provisional' if key!='outstanding-2026' else '',
            measured_live_cadence='untested; dashboard publisher expectation 5–10 minutes',overlap='All 100 counties; do not add state observations to county observations.',
            completion_semantics='Reporting units do not equal votes complete',local_gap='Genuine election-night update sequence/corrections not observed.')
        inventory.append(row)
    writecsv(DATA/'official-results-sources.csv',inventory)
    writecsv(ROOT/'coverage.csv',coverage)

    dependencies={str(x.relative_to(DATA)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [DATA/'county-turnout.csv',TURNOUT/'certified-candidate-extract.csv',
        TURNOUT/'results_pct_20241105.zip',TURNOUT/'results_pct_20221108.zip',TURNOUT/'input-manifest.json']}
    sources={}
    for f in ROOT.glob('*.meta.json'):
        m=json.loads(f.read_text());assert hashlib.sha256(body(m['source_id'])).hexdigest()==m['sha256'];sources[m['source_id']]=m
    save('source-manifest.json',dict(sources=sources,read_only_dependencies=dependencies,parser='build.py v1',python=__import__('sys').version))
    save('validation.json',dict(validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),counties=100,priority_counties=38,
        priority_votes=4576486,statewide_certified_president_votes=5699145,historical_dashboard_county_candidate_rows=len(normalized),
        historical_state_candidate_method_checks=len(candidate_checks),historical_dashboard_vs_ordinary_zip_differences=len(zipdiff),
        historical_certified_differing_fields=len(differences),wake_precinct_candidate_rows=len(pr),wake_units=237,
        current_media_counties=100,current_priority_summary_json=38,source_responses=len(sources),
        original_directory_http_statuses=dict(Counter(str(meta('county-'+c['ncsbe_county_id'].zfill(3))['http_status']) for c in counties)),
        passed=True,limits='Historical and zero-setup checks; no genuine election-night change sequence, measured live cadence, current boundary approval, exact remaining candidate votes or calibrated model.'))
    print(json.dumps(json.loads((ROOT/'validation.json').read_text()),indent=2))

if __name__=='__main__':main()
