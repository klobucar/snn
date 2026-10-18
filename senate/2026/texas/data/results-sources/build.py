#!/usr/bin/env python3
"""Build dated research indexes from pinned responses. Never polls or forecasts."""
import base64,collections,csv,gzip,hashlib,io,json,pathlib,re
from fetch import ROOT,read
from inspect_html import Page,page
from native_inventory import write_csv
from directories import derive
TX=ROOT.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(name,x): (ROOT/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def decoded(sid):
    x=json.loads(read(sid))
    if list(x)==['upload']:return json.loads(base64.b64decode(x['upload']))
    return {k:(v if k=='Version' else json.loads(base64.b64decode(v))) for k,v in x.items()}
def build():
    rows=list(csv.DictReader((TX/'data/county-turnout.csv').open()))
    discovery,peer_routes_raw=derive();dump('county-discovery.json',discovery);dump('peer-county-routes.json',peer_routes_raw)
    decisions=json.loads((ROOT/'county-decisions.json').read_text())
    data=decoded('sos-november-data');counties=decoded('sos-november-counties');lookups=data['Lookups']['County']
    # Complete jurisdiction-name equality. No MID/ID arithmetic for county FIPS.
    byname={r['county'].upper():r for r in rows}
    assert {z['CN'] for z in lookups}==set(byname)
    mapping={str(z['ID']):dict(z,county_fips=byname[z['CN']]['county_fips'],dispatch_key=byname[z['CN']]['dispatch_key'],mapping_basis='complete name equality') for z in lookups}
    dump('state-county-key-map.json',mapping)
    dump('sos-election-constants.decoded.json',decoded('sos-election-constants'))
    for sid in ['sos-november-data','sos-november-counties','sos-evr-election-index','sos-november-evr-sample']:
        dumpname=sid+'.decoded.json.gz';(ROOT/dumpname).write_bytes(gzip.compress(json.dumps(decoded(sid),ensure_ascii=False,indent=2).encode(),mtime=0))
    senate=next(x for x in data['Federal']['Races'] if x['N'].strip()=='U. S. SENATOR')
    dump('candidate-roster.json',dict(election_id=53815,contest_id=senate['id'],stage='2026 November general, initial source configuration',certification_date_literal='August 28, 2026',certification_source='sos-certification',writein_source='sos-writeins',sample_source='sos-sample-ballot',candidates=senate['Candidates'],exclusions='Only three printed nominees and four declared write-ins in retained current certifications. Primary candidates/winners, generic write-in buckets and prior-year contest IDs are not final roster evidence. No later correction/replacement notice was established in inspected November parent/advisory index; recheck before polls close.',future_status_unknown=True))
    certificate=[]
    for pi,p in enumerate((ROOT/'sos-certification.txt').read_text().split('\f'),1):
        if re.search(r'^\s+U\. S\. SENATOR\s*$',p,re.M):
            county=re.search(r'^County\s+(.+)$',p,re.M)[1].strip();sec=re.split(r'U\. S\. SENATOR\s*\n',p)[1].split('U. S. REPRESENTATIVE')[0]
            certificate.append(dict(page=pi,county=county,candidates=re.findall(r'^\s+(.+?)\s{2,}(REP|DEM|LIB|GRE|IND)\s*$',sec,re.M)))
    dump('certification-county-extraction.json',certificate)
    (ROOT/'priority').mkdir(exist_ok=True)
    metas={p.stem:json.loads(p.read_text()) for p in (ROOT/'raw').glob('*.json')}
    # Full link inventory preserves publication labels, including named method/location PDFs.
    links={}
    for sid,m in metas.items():
        if m.get('body_complete') and m.get('original_bytes',0):
            b=read(sid)
            if b.lstrip().lower().startswith((b'<!doctype html',b'<html')):
                links[sid]=Page(b,m['final_url']).links
    dump('publication-link-inventory.json',links)
    source_rows=[];coverage=[];priority=[]
    historical={}
    for fn in ['native-reporting-units.csv.gz','primary-native-units.csv.gz','tlc-derived-vtd-units.csv.gz']:
        p=TX/'data/turnout'/fn
        if p.exists():
            with gzip.open(p,'rt') as h:
                rs=list(csv.DictReader(h))
            historical[fn]=collections.Counter(r.get('county_fips','') for r in rs)
    with gzip.open(ROOT/'native-unit-identities.csv.gz','rt') as h: native=list(csv.DictReader(h))
    peer_routes={z['dispatch_key']:z for z in json.loads((ROOT/'peer-county-routes.json').read_text())}
    dmap={x['dispatch_key']:x for x in discovery}
    for r in rows:
        fips=r['county_fips'];key=r['dispatch_key'];d=dmap[key]
        lookup=next(z for z in mapping.values() if z['county_fips']==fips);cid=str(lookup['ID']);co=counties[cid];se=co['Races']['5075']
        evr=next(x for x in decoded('sos-november-evr-sample')['turnout_by_county'] if x['name']==r['county'].upper())
        det=decisions.get(fips);local_ids=det['result_sources'] if det else ([f'discovery-{fips}'] if f'discovery-{fips}' in metas else [])
        curr=[x for x in native if x['county_fips']==fips]
        c=dict(dispatch_key=key,county_fips=fips,county=r['county'],rank=r['rank'],priority=r['priority80'],state_county_id=cid,state_mid=lookup['MID'],native_roster_scope='source-specific observed identities; neither completeness of physical units nor November approval established',november_approved_native_unit_count=None,observed_native_identity_rows=len(curr) if curr else None,derivative_historical_units=historical.get('native-reporting-units.csv.gz',{}).get(fips),original_historical_units=historical.get('primary-native-units.csv.gz',{}).get(fips),tlc_vtd_rows=historical.get('tlc-derived-vtd-units.csv.gz',{}).get(fips),november_native_gap=det['gap'] if det else 'discovery only; county/vendor/native reporting units not inspected')
        coverage.append(c)
        local=[dict(source_id=sid,metadata_path='raw/'+sid+'.json',request_url=metas[sid]['request_url'],final_url=metas[sid].get('final_url'),status=metas[sid].get('status'),original_sha256=metas[sid].get('original_sha256'),body_scope=metas[sid]['body_scope'],parent_id=metas[sid].get('parent_id')) for sid in local_ids]
        route_urls=[metas[sid]['request_url'] for sid in local_ids if sid in metas]
        source_rows.append(dict(dispatch_key=key,county_fips=fips,county=r['county'],rank=r['rank'],priority=r['priority80'],research_scope='individual_priority_inspection' if det else 'discovery_inventory_only',authority_role=d['authority_role'],authority_name=d['authority_name'],authority_source='sos-county-officials',authority_evidence='raw/sos-county-officials.json',official_directory_url=d['official_directory_url'],directory_source='sos-county-links',historical_discovery_routes_json=json.dumps(peer_routes[key]['peer_directory_record'],separators=(',',':')),state_index_url=metas['sos-results-archive']['request_url'],state_app_url=metas['sos-current-results']['request_url'],state_county_data_url=metas['sos-november-counties']['request_url'],state_election_id=53815,state_contest_id=5075,state_county_id=cid,state_mid=lookup['MID'],county_mapping_basis='complete name equality; MID/ID are not FIPS',county_senate_field_pointer='/upload/'+cid+'/Races/5075',state_status_literal='O=N; initial zeros; no certified November counts',local_source_ids_json=json.dumps(local_ids),local_route_urls_json=json.dumps(route_urls),local_statuses_json=json.dumps([x['status'] for x in local]),evidence_path='priority/'+fips+'.json' if det else 'county-discovery.json',november_native_units=None,remaining_valid_senate_votes=None,measured_update_interval_seconds=None,count_timestamp_timezone=None,assessment=det['assessment'] if det else 'SOS official authority/contact and publication directory plus current state county configuration inventoried; local vendor untested',gap=c['november_native_gap']))
        if det:
            e=dict(dispatch_key=key,county_fips=fips,county=r['county'],rank=int(r['rank']),scope='individual priority inspection',authority_directory=d,local_route_evidence=local,assessment=det['assessment'],gaps=det['gap'],state_election_id=53815,state_contest_id=5075,state_lookup_verbatim=lookup,state_county_summary_verbatim=co['Summary'],state_senate_verbatim=se,source_pointers=dict(lookup='Lookups/County item with complete CN',county='/upload/'+cid,summary='/upload/'+cid+'/Summary',senate='/upload/'+cid+'/Races/5075'),state_sources=['sos-election-constants','sos-november-data','sos-november-counties'],source_original_hashes={s:metas[s]['original_sha256'] for s in ['sos-election-constants','sos-november-data','sos-november-counties']},evr_verbatim=evr,evr_source='sos-november-evr-sample',native_coverage=c,unsupported=dict(remaining_valid_senate_votes=None,measured_vote_arrival_seconds=None,approved_november_crosswalk=None,actual_canvass_meeting_utc=None,source_clock_timezone=None))
            (ROOT/'priority'/(fips+'.json')).write_text(json.dumps(e,indent=2)+'\n');priority.append(e)
    write_csv(TX/'data/official-results-sources.csv',source_rows,list(source_rows[0]))
    write_csv(ROOT/'county-native-coverage.csv',coverage,list(coverage[0]))
    dump('priority-index.json',[dict(dispatch_key=e['dispatch_key'],county=e['county'],rank=e['rank'],path='priority/'+e['county_fips']+'.json') for e in priority])
    # Shared evidence is pinned in place, not copied. Full original metadata retained.
    ledger=json.loads((TX/'data/turnout/source-ledger.json').read_text())
    shared_sources=[z for z in ledger['sources'] if z['id'].startswith('original-') or re.search(r'sos.*(county|state|canvass)',z['id'])]
    refs=[]
    for p in [TX/'data/county-turnout.csv',TX/'data/coordinator-priority-keys.txt',TX/'data/coordinator-baseline-reconciliation.json',TX/'data/turnout/priority-set.json',TX/'data/turnout/source-ledger.json',TX/'data/turnout/SCHEMA.md',TX/'data/turnout/county-source-links.json',TX/'data/turnout/native-reporting-units.csv.gz',TX/'data/turnout/primary-native-units.csv.gz',TX/'data/turnout/tlc-derived-vtd-units.csv.gz',TX/'data/turnout/primary-harris-senate-units.csv.gz',TX/'data/baselines/county-candidates.csv',TX/'data/baselines/state-candidate-controls.csv',TX/'data/baselines/SCHEMA.md']:
        if p.exists():refs.append(dict(path=str(p.relative_to(TX)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
    news=json.loads((TX/'data/news/manifest.json').read_text());news_refs=[x for x in news if x['id'] in ['tarrant-november','tarrant-november-download','sos-historical-results','sos-results-app','sos-results-archive']]
    dump('shared-evidence.json',dict(path_base='Texas directory',file_references=refs,turnout_source_base='data/turnout',primary_sources=shared_sources,coordinator_news_base='data/news',coordinator_news_references=news_refs,limits='Original/finer source universes differ. No derivative allocation, filename reassignment, geographic approval or November crosswalk inferred. Harris large original reconstructed from ordered gzip byte parts; do not duplicate.'))
    # Identical original entities share one retained gzip; all request metadata remains.
    canonical={}
    for sid,m in sorted(metas.items()):
        h=m.get('original_sha256')
        if h and h in canonical:
            old=m['stored_parts'];m['stored_parts']=canonical[h]['stored_parts'];m['body_storage_shared_with']=canonical[h]['id']
            (ROOT/'raw'/(sid+'.json')).write_text(json.dumps(m,indent=2)+'\n')
        elif h:canonical[h]=m
    referenced={p['path'] for m in metas.values() for p in m.get('stored_parts',[])}
    for p in (ROOT/'raw').glob('*.body.gz'):
        if str(p.relative_to(ROOT)) not in referenced:p.unlink()
    dump('source-ledger.json',dict(scope='All complete public HTTP entities, including errors, test/old/initial states. Headers/retrieval clocks do not measure vote arrival.',sources=list(metas.values())))
    # Initial setup controls retain incompatible scopes instead of repairing them.
    ev=decoded('sos-november-evr-sample')
    dump('setup-inspection.json',dict(counties=len(counties),lookups=len(lookups),candidate_count=len(senate['Candidates']),candidate_county_cells=sum(len(c['Races']['5075']['C']) for c in counties.values()),county_senate_TP_sum=sum(c['Races']['5075']['TP'] for c in counties.values()),county_senate_TPR_sum=sum(c['Races']['5075']['TPR'] for c in counties.values()),home=data['Home'],report_list=data['ReportList'],MID_equals_48000_plus_ID=all(z['MID']==48000+z['ID'] for z in lookups),MID_equals_actual_FIPS_count=sum(z['MID']==int(byname[z['CN']]['county_fips']) for z in lookups),source_last_updated_timezone=None,evr_date_updated=ev['date_updated'],evr_counties=len(ev['turnout_by_county']),evr_total_in_person=sum(x['total_in_person_votes_for_election'] for x in ev['turnout_by_county']),evr_total_mail=sum(x['total_mail_votes_for_election'] for x in ev['turnout_by_county']),remaining_valid_senate_votes=None,observed_cadence=None))
    repeats=[]
    for sid in ['sos-november-data','sos-november-counties','harris-ballot','clarity-48439-version']:
        a=metas[sid];b=metas[sid+'-repeat'];repeats.append(dict(source_id=sid,first_utc=a['retrieval_finished_utc'],second_utc=b['retrieval_finished_utc'],same_entity=a['original_sha256']==b['original_sha256'],measured_vote_arrival_cadence=None))
    dump('bounded-observations.json',repeats)
    return dict(counties=len(rows),priorities=len(priority),sources=len(metas),native_identities=len(native))
if __name__=='__main__':print(json.dumps(build()))
