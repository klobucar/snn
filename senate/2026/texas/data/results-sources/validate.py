#!/usr/bin/env python3
"""Standard-library offline audit. --verify-assets is entirely read-only."""
import base64,collections,csv,datetime,gzip,hashlib,io,json,pathlib,re,sys,zlib
from fetch import ROOT,read
from inspect_html import Page
from build import decoded
from directories import derive
TX=ROOT.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def csvrows(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as h:return list(csv.DictReader(h))
def validate(assets=False):
    checks={};limitations=[]
    rows=csvrows(TX/'data/county-turnout.csv');keys=[r['dispatch_key'] for r in rows]
    inventory=csvrows(TX/'data/official-results-sources.csv')
    directory,peer=derive();assert directory==json.loads((ROOT/'county-discovery.json').read_text())
    assert peer==json.loads((ROOT/'peer-county-routes.json').read_text())
    for a,b in zip(directory,inventory):
        assert a['authority_role']==b['authority_role'] and a['authority_name']==b['authority_name'] and (a['official_directory_url'] or '')==b['official_directory_url']
    assert len(rows)==len(inventory)==254 and len(set(keys))==254
    assert [r['dispatch_key'] for r in inventory]==keys
    priorities=json.loads((ROOT/'priority-index.json').read_text());pkeys=[z['dispatch_key'] for z in priorities]
    kb=(TX/'data/coordinator-priority-keys.txt').read_bytes()
    assert sha(kb)=='a5d39344328ab3c0f76809439c6af42c09a59d81f76b9b756e5b538a63ac5be5'
    assert pkeys==kb.decode().splitlines()==keys[:34]
    assert sum(int(r['senate_2024_total']) for r in rows)==11291854
    assert sum(int(r['senate_2024_total']) for r in rows[:15])==7369697
    assert sum(int(r['senate_2024_total']) for r in rows[:33])==9018686
    assert sum(int(r['senate_2024_total']) for r in rows[:34])==9076868
    assert 5*9018686<4*11291854<=5*9076868
    assert sha((TX/'data/county-turnout.csv').read_bytes())=='1da814cfbdc254063fa3bd60a35fed870b5825a89f3267303e3cff3656144140'
    assert sha((TX/'data/turnout/priority-set.json').read_bytes())=='8c30e57da8010aeb34c539611a41740ec199caa2bc8f2a0285f45e5a84d56ff5'
    checks['county_contract']=dict(counties=254,priority_count=34,priority_order_hash=sha(kb),all_candidate_denominator=11291854)
    candidates=csvrows(TX/'data/baselines/county-candidates.csv');controls=csvrows(TX/'data/baselines/state-candidate-controls.csv')
    sums=collections.Counter();counties=collections.defaultdict(set);county_votes=collections.Counter();cellkeys=set()
    for r in candidates:
        k=(r['contest'],r['county_fips'],r['candidate_order']);assert k not in cellkeys;cellkeys.add(k)
        sums[(r['contest'],r['native_candidate_name'])]+=int(r['votes']);counties[r['contest']].add(r['county_fips']);county_votes[(r['contest'],r['county_fips'])]+=int(r['votes'])
    assert len(candidates)==6604 and len(controls)==26 and all(len(v)==254 for v in counties.values()) and len(counties)==4
    for r in controls:assert sums[(r['contest'],r['native_candidate_name'])]==int(r['votes'])==int(r['county_sum']) and int(r['difference'])==0
    for r in rows:assert county_votes[('2024-senate',r['county_fips'])]==int(r['senate_2024_total'])
    checks['primary_historical_controls']=dict(candidate_county_cells=6604,state_controls=26,county_contest_totals=1016,source_scope='read-only accepted originals; not finer-unit certification')
    ledger=json.loads((ROOT/'source-ledger.json').read_text())['sources'];meta={p.stem:json.loads(p.read_text()) for p in (ROOT/'raw').glob('*.json')}
    assert {m['id'] for m in ledger}==set(meta)
    failures=[];hashes=0;referenced=set()
    for m in ledger:
        assert m==meta[m['id']] and m['request_url'].startswith(('http://','https://'))
        assert m['retrieval_started_utc']<=m['retrieval_finished_utc']
        if not m['body_complete']:
            assert m.get('error') and m['status'] is None;failures.append(m['id']);continue
        stream=b''
        for part in m['stored_parts']:
            p=ROOT/part['path'];b=p.read_bytes();assert len(b)==part['bytes']<40000000 and sha(b)==part['sha256'];stream+=b;referenced.add(part['path'])
        assert sha(stream)==m['stored_stream_sha256'] and len(stream)==m['stored_stream_bytes']
        b=gzip.decompress(stream);assert len(b)==m['original_bytes'] and sha(b)==m['original_sha256'];hashes+=1
        if m['status']!=200 or not b:failures.append(m['id'])
    assert {str(p.relative_to(ROOT)) for p in (ROOT/'raw').glob('*.body.gz')}<=referenced
    checks['http_entities']=dict(requests=len(ledger),complete_entities_hashed=hashes,failed_empty_or_non200=failures,partial_truncated_entities=0)
    data=decoded('sos-november-data');co=decoded('sos-november-counties');lk=data['Lookups']['County'];byname={r['county'].upper():r for r in rows}
    assert len(lk)==len(co)==254 and {x['CN'] for x in lk}==set(byname)
    assert all(x['MID']==48000+x['ID'] for x in lk)
    assert sum(x['MID']==int(byname[x['CN']]['county_fips']) for x in lk)==1
    sen=next(x for x in data['Federal']['Races'] if x['N'].strip()=='U. S. SENATOR');assert sen['id']==5075
    ids={x['ID'] for x in sen['Candidates']};assert ids=={42424,41261,33528,44430,44432,44434,44534}
    for x in lk:
        c=co[str(x['ID'])];assert c['N']==x['CN'];s=c['Races']['5075'];assert s['OID']==5075 and set(map(int,s['C']))==ids
        assert s['T']==sum(z['V'] for z in s['C'].values())==0
        assert all(z['V']==z['EV']==0 for z in s['C'].values())
    assert all(x['V']==x['EV']==0 for x in sen['Candidates'])
    assert sum(x['Races']['5075']['TP'] for x in co.values())==sum(x['Races']['5075']['TPR'] for x in co.values())==9900
    assert data['Home']['PrecinctsReporting']['PT']==5 and data['Home']['PollingReporting']['PLT']==5299
    assert all(not x['view'] and x['fileTypes']==[] for x in data['ReportList'].values())
    assert read('sos-november-history')==b''
    checks['november_setup']=dict(counties=254,named_candidates=7,candidate_county_cells=1778,initial_candidate_sum=0,MID_is_not_FIPS=True,home_PT=5,county_Senate_TP_sum=9900,polling_PLT=5299,RSS_history='empty response',live_votes_verified=False)
    # All 254 printed Senate sections independently extracted from the original certification text.
    text=(ROOT/'sos-certification.txt').read_text();cert=[]
    for pi,p in enumerate(text.split('\f'),1):
        if re.search(r'^\s+U\. S\. SENATOR\s*$',p,re.M):
            name=re.search(r'^County\s+(.+)$',p,re.M)[1].strip();sec=re.split(r'U\. S\. SENATOR\s*\n',p)[1].split('U. S. REPRESENTATIVE')[0]
            roster=re.findall(r'^\s+(.+?)\s{2,}(REP|DEM|LIB|GRE|IND)\s*$',sec,re.M)
            assert roster==[('KEN PAXTON','REP'),('JAMES TALARICO','DEM'),('TED BROWN','LIB')];cert.append(name)
    assert len(cert)==254 and set(cert)==set(byname)
    wi=re.findall(r'^U\.S\. Senator\s+(.+)$',(ROOT/'sos-writeins.txt').read_text(),re.M)
    assert wi==['Avery Ayers','Bradford "Brad" Hall','Zul Mohamed','Jade Simmons']
    assert {x['N'] for x in sen['Candidates']}=={'KEN PAXTON','JAMES TALARICO','TED BROWN',*(x.upper() for x in wi)}
    checks['ballot_certification']=dict(printed_county_sections=254,printed_candidates=3,declared_writeins=4,current_app_roster_matches=True,certification_date='2026-08-28',later_changes='not established; preclose recheck remains')
    coverage=csvrows(ROOT/'county-native-coverage.csv');assert [r['dispatch_key'] for r in coverage]==keys
    for r in inventory:
        assert r['authority_role'] and r['authority_name']
        for f in ['november_native_units','remaining_valid_senate_votes','measured_update_interval_seconds','count_timestamp_timezone']:assert r[f]==''
        if r['priority']=='1':
            e=json.loads((ROOT/r['evidence_path']).read_text());assert e['dispatch_key']==r['dispatch_key'] and e['state_senate_verbatim']==co[r['state_county_id']]['Races']['5075']
            assert e['local_route_evidence'] and e['assessment'] and e['gaps'] and all(v is None for v in e['unsupported'].values())
            assert all(z['source_id'] in meta for z in e['local_route_evidence'])
        else:assert r['research_scope']=='discovery_inventory_only'
    for r in coverage:assert not r['november_approved_native_unit_count']
    checks['priority_and_native_coverage']=dict(individual_records=34,discovery_only=220,county_gap_records=254,current_approved_counts='all unknown')
    # Validate every indexed native source pointer and aligned raw row against originals.
    native=csvrows(ROOT/'native-unit-observations.csv.gz');unit=csvrows(ROOT/'native-unit-identities.csv.gz');cache={};cnt=collections.Counter();seen=set()
    for r in native:
        sid=r['source_id'];pointer=r['source_pointer'];assert (sid,pointer) not in seen;seen.add((sid,pointer))
        if sid not in cache:
            cache[sid]=gzip.decompress((ROOT/(sid+'.txt.gz')).read_bytes()).decode().split('\f') if r['unit_kind']=='pdf_precinct_label' else list(csv.reader(io.StringIO(read(sid).decode('utf-8-sig')))) if sid.endswith('-sample') else json.loads(read(sid))
        x=cache[sid]
        if pointer.startswith('/pdf-page/'):
            parts=pointer.split('/');pi=int(parts[2]);li=int(parts[4]);line=x[pi-1].splitlines()[li-1]
            assert line=='Precinct '+r['native_id'];expected=dict(page=pi,line_number=li,source_line=line)
        elif pointer.startswith('/csv-row/'):
            z=x[int(r['source_ordinal'])-1];assert z[1]==r['native_id'];expected=dict(header_rows=x[:2],cells=z)
        elif r['unit_kind']=='vote_center':
            z=x[int(r['source_ordinal'])];assert str(z['voteCenter']['idVoteCenter'])==r['native_id'];expected=z
        else:
            parts=pointer.split('/');z=x['Contests'][int(parts[2])] if parts[1]=='Contests' else x
            pkey='p' if 'p' in z else 'P';i=int(r['source_ordinal']);assert str(z[pkey][i])==r['native_id']
            expected={k:v[i] for k,v in z.items() if isinstance(v,list) and len(v)==len(z[pkey])}
            if parts[1]=='Contests':expected['K']=z['K']
        assert json.loads(r['raw_row_json'])==expected
        cnt[(sid,r['county_fips'],r['election_id'],r['observation_class'],r['unit_kind'],r['native_id'])]+=1
    assert len(unit)==len(cnt)==12701 and len(native)==170013
    for r in unit:assert cnt[(r['source_id'],r['county_fips'],r['election_id'],r['observation_class'],r['unit_kind'],r['native_id'])]==int(r['occurrences'])
    expected={'48439':('11/3/2026','1'),'48029':('11/3/2026','0'),'48141':('11/3/2026','1'),'48157':('11/3/2026','1'),'48027':('5/26/2026','0'),'48367':('3/3/2026','0')}
    for f,(date,test) in expected.items():
        d=json.loads(read('clarity-'+f+'-electionsettings'))['settings']['electiondetails'];assert d['electiondate']==date and d['istestmode']==test
    assert len(json.loads(read('harris-reporting'))['p'])==len(json.loads(read('harris-senate-precinct'))['p'])==1224
    checks['native_source_positions']=dict(observations=170013,source_scoped_identities=12701,every_pointer_and_row_checked=True,test_and_old_exclusions_checked=True,Grayson_PDF_labels=42,Grayson_PDF_page_appearances=546)
    # Genuine bounded repeats; no timer/HTTP clock is interpreted as vote arrival.
    for a in json.loads((ROOT/'bounded-observations.json').read_text()):
        assert a['first_utc']<a['second_utc'] and a['same_entity'] and a['measured_vote_arrival_cadence'] is None
    ev=decoded('sos-november-evr-sample');assert len(ev['turnout_by_county'])==254
    assert {x['name'] for x in ev['turnout_by_county']}==set(byname)
    assert sum(x['total_mail_votes_for_election'] for x in ev['turnout_by_county'])==46998
    checks['outstanding_and_clocks']=dict(bounded_unchanged_repeats=4,EVR_counties=254,EVR_mail_statistic=46998,remaining_valid_Senate_votes=None,measured_vote_arrival_cadence=None)
    # Primary current source-parent chain is checked against actual retained anchors and code.
    for child,parent in [('sos-results-archive','sos-results-index'),('sos-current-results','sos-results-archive'),('sos-current-results-main','sos-current-results'),('sos-certification','sos-november'),('sos-writeins','sos-november')]:
        assert meta[child]['request_url'] in [x['url'] for x in Page(read(parent),meta[parent]['final_url']).links]
    main=read('sos-current-results-main').decode();assert 'urlAPIIvisSystem:"/api-ivis-system/api"' in main
    for s in ['/s3/enr/electionConstants','/s3/enr/election/','/s3/enr/election/countyInfo/','/s3/enr/electionRss/']:assert s in main
    assert decoded('sos-election-constants')['electionInfo']['2026']['GE']['53815']['N']=='2026 NOVEMBER GENERAL ELECTION'
    assert '/Data/' in read('harris-live').decode() and "var electionCode = '1126'" in read('harris-live').decode()
    for fips,parent,eid in [('48439','county-48439','127297'),('48029','county-48029','127291'),('48141','county-48141','127348'),('48157','county-48157-result2','127480')]:
        assert any('/'+eid+'/' in x['url'] for x in Page(read(parent),meta[parent]['final_url']).links)
    checks['public_parent_provenance']=dict(state_index_and_roster_links=True,actual_current_bundle_routes=True,November_ID_from_constants=True,county_vendor_links_checked=4,other_discovery_routes='honestly labeled, not automatically official-parent proof')
    # Verify shared bodies in place, including exact ordered split gzip bytes.
    shared=json.loads((ROOT/'shared-evidence.json').read_text());shared_n=0
    for x in shared['file_references']:
        p=TX/x['path'];b=p.read_bytes();assert len(b)==x['bytes'] and sha(b)==x['sha256']
    for x in shared['primary_sources']:
        source_base=TX/'data/turnout'/x.get('dependency_root','.')
        if x.get('stored_path'):
            b=(source_base/x['stored_path']).read_bytes();assert sha(b)==x['stored_sha256'];raw=gzip.decompress(b)
        elif x.get('stored_parts'):
            parts=[]
            for z in x['stored_parts']:
                b=(source_base/z['path']).read_bytes();assert len(b)==z['bytes']<40000000 and sha(b)==z['sha256'];parts.append(b)
            b=b''.join(parts);assert sha(b)==x['stored_sha256'];raw=gzip.decompress(b)
        else:continue
        assert len(raw)==x['original_bytes'] and sha(raw)==x['original_sha256'];shared_n+=1
    for x in shared['coordinator_news_references']:
        b=(TX/'data/news'/x['asset']).read_bytes();assert sha(b)==x['stored_sha256'] and sha(gzip.decompress(b))==x['raw_sha256']
    checks['shared_originals']=dict(originals_hashed_in_place=shared_n,files_pinned=len(shared['file_references']),news_references_hashed=len(shared['coordinator_news_references']),no_duplicate_large_PDF=True)
    # Current legal text, delayed-law condition and dated 2026 calendar are distinct.
    for sid,term in [('law-text-2','PLURALITY VOTE REQUIRED'),('law-text-41','VOTING HOURS'),('law-text-67','TIME FOR CANVASS BY GOVERNOR'),('law-text-212','TIME FOR SUBMITTING PETITION')]:assert term in read(sid).decode()
    assert 'This summary does not serve as the report' in read('sos-sb2753-advisory').decode()
    assert b'SB 2753' not in read('sos-calendar')
    checks['legal_sources']=dict(primary_current_text=True,calendar='SOS2026-21 July14,2026',SB2753_implementation_report_applicability='not established; current dated calendar retained',actual_November_canvass_meetings='unknown')
    # Local Markdown links in owned documents must exist.
    md=[TX/'official-results.md',ROOT/'README.md',ROOT/'SCHEMA.md']
    for p in md:
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if target.startswith(('http:','https:','#')):continue
            q=(p.parent/target.split('#')[0]).resolve()
            if not assets and q in [ROOT/'validation.json',ROOT/'asset-manifest.json']:continue
            assert q.exists(),(p,target)
    files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]+[TX/'official-results.md',TX/'data/official-results-sources.csv']
    assert all(p.stat().st_size<40000000 for p in files)
    checks['stored_object_bounds']=dict(strict_limit=40000000,largest_bytes=max(p.stat().st_size for p in files))
    if assets:
        m=json.loads((ROOT/'asset-manifest.json').read_text());expected={str(p.relative_to(TX)) for p in files if p.name!='asset-manifest.json'}
        assert {x['path'] for x in m['assets']}==expected
        for x in m['assets']:
            p=TX/x['path'];b=p.read_bytes();assert sha(b)==x['sha256'] and len(b)==x['bytes']<40000000
        checks['owned_asset_manifest']=dict(assets=len(expected),all_hashes_match=True)
    limitations=['No verified changing November vote snapshots or measured vote-arrival cadence.','Initial/test/old source states and differing native denominators are explicitly retained.','220 local channels remain discovery/inventory scope; blocked priority county channels require manual access.','No current geographic crosswalk, legal unit-count approval, valid outstanding Senate count, deployed collector or calibrated probability.','SB2753 final implementation report/procedure applicability not established; dated November2026 calendar governs this research assumption.']
    return dict(status='pass',checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),checks=checks,limitations=limitations)
if __name__=='__main__':
    verify='--verify-assets' in sys.argv;x=validate(verify)
    if not verify:(ROOT/'validation.json').write_text(json.dumps(x,indent=2)+'\n')
    print(json.dumps(dict(status=x['status'],checks=list(x['checks']),limitations=x['limitations']),indent=2))
