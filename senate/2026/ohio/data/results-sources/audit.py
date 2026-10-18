#!/usr/bin/env python3
"""Offline, reproducible Ohio results-source checks. No network and no shared-file edits."""
import collections, csv, datetime, gzip, hashlib, io, json, pathlib, re, tarfile, zipfile
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).resolve().parent
STATE=ROOT.parent.parent
DATA=ROOT.parent
ARCHIVE_CACHE={}
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(name,d): (ROOT/name).write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def csvout(name,rows):
    assert rows
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def csvread(p):
    op=gzip.open if str(p).endswith('.gz') else open
    with op(p,'rt',newline='') as f:return list(csv.DictReader(f))
def meta(k): return json.loads((ROOT/(k+'.meta.json')).read_text())
def body(k):
    m=meta(k)
    if m.get('archive_member'):
        if m['body'] not in ARCHIVE_CACHE:
            with tarfile.open(ROOT/m['body'],'r:xz') as t:ARCHIVE_CACHE[m['body']]={x.name:t.extractfile(x).read() for x in t.getmembers() if x.isfile()}
        return ARCHIVE_CACHE[m['body']][m['archive_member']]
    return gzip.decompress((ROOT/m['body']).read_bytes())
def obj(k):return json.loads(body(k))
def name(x):return x[0]['text'] if x else ''
def xlsx_cells(path,sheet,refs):
    """Independent OOXML scalar reader; never imports either baseline worker's parser."""
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            ss=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(x.itertext()) for x in ss.findall('s:si',ns)]
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sh=next(e for e in wb.findall('s:sheets/s:sheet',ns) if e.get('name')==sheet)
        rid=sh.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target=next(e.get('Target') for e in rel if e.get('Id')==rid)
        target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        out={}
        for _,e in ET.iterparse(io.BytesIO(z.read(target)),events=['end']):
            if e.tag.endswith('}c'):
                ref=e.get('r')
                if ref in refs:
                    v=e.find('s:v',ns)
                    text=v.text if v is not None else None
                    if e.get('t')=='s' and text is not None:text=strings[int(text)]
                    elif e.get('t')=='inlineStr':text=''.join(e.find('s:is',ns).itertext())
                    out[ref]=text
                e.clear()
        assert refs<=set(out),(path,len(refs-set(out)))
        return out
def main():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    pr=json.loads((DATA/'turnout/priority-set.json').read_text())
    counties=pr['county_records'];assert len(counties)==88
    priority=counties[:32];assert [c['county_fips'] for c in priority]==pr['ordered_priority_county_keys']
    half='Allen,Ashtabula,Athens,Belmont,Butler,Clark,Clermont,Columbiana,Cuyahoga,Delaware,Erie,Fairfield,Franklin,Geauga,Greene,Hamilton,Hancock,Jefferson,Knox,Lake,Lawrence,Licking,Lorain,Lucas,Mahoning,Marion,Medina,Miami,Montgomery,Muskingum,Portage,Richland,Ross,Sandusky,Scioto,Stark,Summit,Trumbull,Tuscarawas,Union,Warren,Washington,Wayne,Wood'.split(',')
    top='Ashland,Auglaize,Brown,Champaign,Clinton,Crawford,Darke,Defiance,Fulton,Guernsey,Highland,Huron,Logan,Madison,Mercer,Morrow,Ottawa,Pickaway,Preble,Seneca,Shelby,Williams'.split(',')
    bottom='Adams,Carroll,Coshocton,Fayette,Gallia,Hardin,Harrison,Henry,Hocking,Holmes,Jackson,Meigs,Monroe,Morgan,Noble,Paulding,Perry,Pike,Putnam,Van Wert,Vinton,Wyandot'.split(',')
    assert (len(half),len(top),len(bottom))==(44,22,22)
    assert len(set(half+top+bottom))==88 and set(half+top+bottom)=={x['county_native_id'] for x in counties}
    assert {x['county_native_id'] for x in priority}<=set(half)
    schedule={**dict.fromkeys(half,'half-hour: 20:15,20:45,21:15,...'),**dict.fromkeys(top,'hourly top: 20:00,21:00,...'),**dict.fromkeys(bottom,'initial20:00; hourly bottom20:30,21:30,...')}
    dump('published-submission-schedule.json',{'source':'https://www.ohiosos.gov/assets/dir2026-48-canvass-and-certification-of-the-november-3-2026-general-election.pdf','source_date':'2026-10-02','source_pages':'printed3-5','evidence':'law-canvass-browser.json','scope':'Future county CSS submissions to state, not independently measured vendor publication cadence','initial':'CSS login by19:45; initial absentee upload by20:00 with directive allowances; zero precincts reporting for absentee upload','timezone':'Ohio local Eastern Standard Time on2026-11-03','county_schedule':schedule,'half_hour_count':44,'top_hour_count':22,'bottom_hour_count':22,'all_priority_half_hour':True,'final':'Final summary may be submitted without waiting for assigned interval.'})
    assert pr['statewide_votes']==5704620 and pr['top15_votes']==3525320
    assert sum(c['senate_2024_votes'] for c in priority)==4581738
    assert 5*4581738>=4*5704620 and 5*4542798<4*5704620
    assert sha((DATA/'county-turnout.csv').read_bytes())=='d9133f7f88eca91b8bef8f3987b3e1abfb30b19e61d1d824a1e270dde4049a90'
    deps=['data/county-turnout.csv','data/county-baselines.csv','data/turnout/priority-set.json','data/turnout/county-candidate-votes.csv','data/turnout/reporting-units-2024.csv.gz','data/turnout/reporting-units-2022.csv.gz','data/turnout/precinct-candidates-2024.csv.gz','data/turnout/raw/2024-summary-archive.xlsx','data/turnout/raw/2022-statewide-races-summary.xlsx','data/turnout/source-manifest.json','data/coordinator-baseline-reconciliation.json','data/baselines/turnout-worker-reconciliation.json']
    locked={f:sha((STATE/f).read_bytes()) for f in deps}
    lock=ROOT/'dependency-hashes.json'
    if lock.exists():assert json.loads(lock.read_text())['sha256']==locked,'Read-only baseline changed; review rather than repin silently'
    else:dump('dependency-hashes.json',{'pinned_utc':now,'note':'Coordinator checked timestamps intentionally remain stable when the checked result is unchanged. Pins are exact bytes/hashes and comparison counts, not progress notes. Archived publisher/capture/retrieval provenance remains in the original manifest.','sha256':locked})
    base=csvread(DATA/'turnout/county-candidate-votes.csv')
    # Reparse all 2,464 certified county candidate cells and 28 statewide controls.
    cellchecks=[];statechecks=[]
    bysource=collections.defaultdict(list)
    for x in base:bysource[x['source_path']].append(x)
    for src,rows in bysource.items():
        refs={x['candidate_native_column']+x['source_row'] for x in rows}
        refs|={x['candidate_native_column']+'3' for x in rows}
        vals=xlsx_cells(DATA/'turnout'/src,'Master',refs)
        for x in rows:
            ref=x['candidate_native_column']+x['source_row'];v=int(vals[ref] or 0)
            assert v==int(x['votes'])
            cellchecks.append({'election_date':x['election_date'],'contest':x['contest_key'],'county_fips':x['county_fips'],'candidate':x['candidate_native_label'],'source':src,'cell':ref,'independent_votes':v,'baseline_votes':int(x['votes']),'difference':0})
        groups=collections.defaultdict(list)
        for x in rows:groups[(x['election_date'],x['contest_key'],x['candidate_native_label'],x['candidate_native_column'])].append(x)
        for (date,contest,candidate,col),g in groups.items():
            assert len(g)==88
            total=sum(int(x['votes']) for x in g);control=int(vals[col+'3']);assert total==control
            statechecks.append({'election_date':date,'contest':contest,'candidate':candidate,'county_count':88,'county_sum':total,'source_state_row':control,'difference':0})
    assert len(cellchecks)==2464 and len(statechecks)==28
    csvout('historical-certified-cell-checks.csv',cellchecks);csvout('historical-state-checks.csv',statechecks)
    historical=collections.defaultdict(dict)
    for x in base:
        if x['election_date']=='2024-11-05' and x['contest_key']=='senate':historical[x['county_native_id']][x['candidate_native_label']]=int(x['votes'])
    units=csvread(DATA/'turnout/reporting-units-2024.csv.gz');assert len(units)==8878
    byunit={x['unit_key']:x for x in units};assert len(byunit)==len(units)
    pcts=csvread(DATA/'turnout/precinct-candidates-2024.csv.gz')
    pctvotes={(x['unit_key'],x['candidate_native_label']):int(x['votes_observed']) for x in pcts if x['contest_key']=='senate' and x['votes_observed']!=''}
    # Independently fetched Delaware official numbered-key canvass: all 170 units,
    # all seven candidate sums; 510 available printed-candidate precinct cells.
    text=(ROOT/'delaware-2024-key.txt').read_text();tail=text[text.index('U.S. Senator'):];tail=tail[:tail.index('Representative to Congress')]
    local=[]
    for line in tail.splitlines():
        m=re.match(r'^(\d{5}) (\d{3}) (.+?)\s{2,}((?:\d+\s+){9}\d+)\s*$',line)
        if m:local.append((m.group(1),m.group(2),m.group(3),list(map(int,m.group(4).split()))))
    assert len(local)==170 and len({x[0] for x in local})==170
    norm=lambda s:re.sub(r'^PRECINCT ','',s.upper())
    um={norm(x['precinct_name_native']):x for x in units if x['county_fips']=='39041'};assert len(um)==170
    candidate_order=['Sherrod Brown (D)','Don Kissick (L)','Bernie Moreno (R)','David Allen Pastorius (WI)*','Nathan Russell (WI)*','Stephen Faris (WI)*','Tariq K. Shabazz (WI)*']
    delchecks=[]
    for native,num,nm,vs in local:
        u=um[norm(nm)]
        for i,candidate in enumerate(candidate_order[:3]):
            v=pctvotes[u['unit_key'],candidate];assert v==vs[i]
            delchecks.append({'local_numeric_id':native,'local_number':num,'local_name':nm,'state_unit_key':u['unit_key'],'state_native_name':u['precinct_name_native'],'name_rule':'uppercase local name; remove literal PRECINCT prefix from state name; unique within Delaware 2024 only','candidate':candidate,'local_votes':vs[i],'state_votes':v,'difference':0})
    sums=[sum(x[3][i] for x in local) for i in range(10)]
    assert sums==[63697,3562,65715,0,0,4,16,125,7,2347]
    for i,c in enumerate(candidate_order):assert sums[i]==historical['Delaware'][c]
    assert sum(sums)==135473
    csvout('delaware-2024-precinct-checks.csv',delchecks)
    dump('delaware-2024-coverage.json',{'units':170,'printed_candidate_cells_matched':510,'all_seven_candidate_sums':dict(zip(candidate_order,sums[:7])),'separate_source_WRITE_IN':125,'overvotes':7,'undervotes':2347,'ballots':135473,'warning':'The separate generic WRITE-IN count is excluded from the seven named certified candidates. This local numbered-key report has no public vote-method columns. Numeric local IDs differ from state three-letter IDs; this one-vintage name crosswalk is not 2026 approval.'})
    # Local 2024 county summaries: explicit candidate labels, invalid totals separate.
    aliases={'Sherrod Brown (D)':'Sherrod Brown','Don Kissick (L)':'Don Kissick','Bernie Moreno (R)':'Bernie Moreno','Stephen Faris (WI)*':'Stephen Faris','David Allen Pastorius (WI)*':'David Allen Pastorius','Nathan Russell (WI)*':'Nathan Russell','Tariq K. Shabazz (WI)*':'Tariq Shabazz'}
    countychecks=[]
    for county,key in [('Franklin','franklin-2024-summary'),('Lorain','lorain-2024-summary'),('Clermont','clermont-2024-summary'),('Wood','wood-2024-summary'),('Delaware','delaware-2024-summary')]:
        text=(ROOT/(key+'.txt')).read_text();j=text.index('U.S. Senator');seg=text[j:]
        for stop in ['Representative to Congress','Rep. to Congress']:
            if stop in seg:seg=seg[:seg.index(stop)]
        for cand,label in aliases.items():
            matches=[l for l in seg.splitlines() if label in l]
            if not matches:
                assert county=='Clermont' and historical[county][cand]==0
                value=None;status='not separately printed; certified zero retained only from state source'
            else:
                # First integer after the exact candidate label; party suffix is text.
                m=re.search(r'\b\d[\d,]*\b',matches[0].split(label,1)[1]);assert m,(county,cand,matches)
                value=int(m.group().replace(',',''));assert value==historical[county][cand],(county,cand,value,historical[county][cand]);status='exact named candidate match'
            countychecks.append({'county':county,'candidate':cand,'local_votes':value,'certified_baseline':historical[county][cand],'difference':0 if value is not None else None,'status':status,'source':key})
    csvout('local-county-candidate-checks.csv',countychecks)
    trtext=(ROOT/'trumbull-2024-labelled.txt').read_text()
    assert 'NOVEMBER 5, 2024' in trtext and 'UNOFFICIAL RESULTS' in trtext and '11/05/2024 10:11PM' in trtext
    seg=trtext[trtext.index('U.S. Senator'):];seg=seg[:seg.index('Representative to Congress')]
    trchecks=[]
    for cand,label in [('Sherrod Brown (D)','Sherrod Brown'),('Don Kissick (L)','Don Kissick'),('Bernie Moreno (R)','Bernie Moreno')]:
        line=next(x for x in seg.splitlines() if label in x)
        value=int(re.search(r'\d[\d,]*',line.split(label,1)[1]).group().replace(',',''))
        trchecks.append({'county':'Trumbull','candidate':cand,'election_night_unofficial_votes':value,'original_certified_votes':historical['Trumbull'][cand],'certified_minus_election_night':historical['Trumbull'][cand]-value,'reported_precincts':'158 of158','source':'trumbull-2024-labelled','warning':'Different counting stages; neither the difference nor generic Write-In75 is an exact remaining eligible-vote inventory.'})
    assert [x['certified_minus_election_night'] for x in trchecks]==[977,79,1225]
    csvout('trumbull-2024-stage-comparison.csv',trchecks)
    lake=(ROOT/'lake-current-summary.txt').read_text()
    assert '2026 Primary Special Election' in lake and 'May 5, 2026' in lake and '163 of 163' in lake
    assert '35,349' in lake and '43,662' in lake and sum([35349,18,4717,3428,150])==43662
    dump('additional-local-sample-checks.json',{'Lake':{'source':'lake-current-summary','observed_stage':'Official May5,2026 primary/special; not November','pages':72,'precincts_reported':163,'ballots_total':43662,'ballot_method_counts':{'Election Day':35349,'Election Day Paper':18,'Early Vote':4717,'Regular ABS By Mail':3428,'Provisional':150},'method_sum':43662,'November_Senate_candidate_counts':None},'Trumbull':{'source':'trumbull-2024-labelled','link_label':'November5,2024','filename':'ElectionResults110525.pdf','body_election_date':'2024-11-05','stage':'UNOFFICIAL RESULTS','publisher_clock':'11/05/2024 10:11PM; timezone not stated','native_unit_completion':'158 of158','separate_generic_write_in':75,'local_total_votes_cast':93443,'comparison_file':'trumbull-2024-stage-comparison.csv'}})
    # Genuine linked Enhanced Voting public API; all routes discovered from app code.
    evchecks=[];evschema=[]
    for label in ['cuyahoga-2024','cuyahoga-primary','montgomery-primary']:
        d=obj('enhanced-'+label+'-data');e=d['election'];ps=d['precincts']
        assert len(ps)==len({x['id'] for x in ps}) and all(x['id'] for x in ps)
        evschema.append({'source':label,'election_date':e['electionDate'],'is_primary':e['isPrimary'],'is_production':e['isProduction'],'is_official':e['isOfficialResults'],'asOf':e['asOf'],'lastUpdated':e['lastUpdated'],'nextUpdateAt':e['nextUpdateAt'],'native_precincts':len(ps),'virtual_precincts':sum(bool(x['isVirtual']) for x in ps),'blank_precinct_ids':sum(not x['id'] for x in ps),'actual_ballot_items':len(d['ballotItems']),'metadata_ballotItemCount':e['ballotItemCount'],'senate_contests':[{'id':b['id'],'name':name(b['name']),'voteTotal':b['voteTotal'],'options':[{'id':o['id'],'nativeId':o['nativeId'],'name':name(o['name']),'votes':o['voteCount'],'groups':o['groupResults']} for o in b['summaryResults']['ballotOptions']]} for b in d['ballotItems'] if 'SENAT' in name(b['name']).upper() and not 'STATE SEN' in name(b['name']).upper()]})
        for b in d['ballotItems']:
            opts=b.get('summaryResults',{}).get('ballotOptions',[])
            for o in opts:
                if o['groupResults']:
                    assert sum(g['voteCount'] for g in o['groupResults'])==o['voteCount'],(label,name(b['name']),name(o['name']))
    dump('enhanced-schema-checks.json',evschema)
    d=obj('enhanced-cuyahoga-2024-senate-detail');b=d['ballotItemWithBreakdown'];br=b['breakdownResults']
    assert len(br)==b['breakdownResultCount']==967 and len({x['precinct']['id'] for x in br})==967
    # Preserve all UUIDs; normalize only interstitial whitespace for a unique 2024 join.
    norm2=lambda s:re.sub(r'\s+','',s.upper())
    um={norm2(x['precinct_name_native']):x for x in units if x['county_fips']=='39035'};assert len(um)==967
    for row in br:
        u=um[norm2(name(row['precinct']['name']))]
        assert sum(o['voteCount'] for o in row['ballotOptions'])==row['voteTotal']
        for o in row['ballotOptions']:
            if name(o['name'])=='Write-In':continue
            cand=next(c for c,a in aliases.items() if a==name(o['name']))
            baseline=pctvotes[u['unit_key'],cand]
            assert sum(g['voteCount'] for g in o['groupResults'])==o['voteCount']
            evchecks.append({'vendor_precinct_id':row['precinct']['id'],'vendor_precinct_name':name(row['precinct']['name']),'state_unit_key':u['unit_key'],'state_native_name':u['precinct_name_native'],'candidate':cand,'vendor_votes':o['voteCount'],'state_votes':baseline,'difference':o['voteCount']-baseline})
    assert len(evchecks)==2901
    evdiff=[x for x in evchecks if x['difference']]
    assert len(evdiff)==1 and evdiff[0]['state_unit_key']=='2024-11-05|39035|CDT' and evdiff[0]['candidate']=='Sherrod Brown (D)' and evdiff[0]['difference']==1
    csvout('cuyahoga-2024-source-differences.csv',evdiff)
    for o in b['summaryResults']['ballotOptions']:
        total=sum(next(x['voteCount'] for x in row['ballotOptions'] if x['id']==o['id']) for row in br)
        assert total==o['voteCount']
    csvout('cuyahoga-2024-precinct-checks.csv',evchecks)
    wi=next(o['voteCount'] for o in b['summaryResults']['ballotOptions'] if name(o['name'])=='Write-In')
    residual=b['voteTotal']-sum(historical['Cuyahoga'].values());assert wi==530 and residual==418
    dump('cuyahoga-2024-count-scope.json',{'vendor_units':967,'baseline_units':967,'printed_candidate_cells_compared':2901,'exact_matches':2900,'source_candidate_differences':evdiff,'candidate_method_sums_match_internal_vendor':True,'vendor_generic_write_in':wi,'certified_named_write_ins':sum(v for c,v in historical['Cuyahoga'].items() if '(WI)' in c),'vendor_vote_total':b['voteTotal'],'baseline_seven_candidate_total':sum(historical['Cuyahoga'].values()),'vendor_minus_baseline_total':residual,'aggregate_writein_residual_not_automatically_candidate_votes':417,'normalization':'remove whitespace only, within county and 2024; 967 unique names on each side; no UUID to three-letter code equivalence across elections asserted'})
    # State mock XML and JSON deliberately rejected from counted-vote ingestion.
    r=ET.fromstring(body('live-xml'));ns={'n':r.tag.split('}')[0][1:]};assert r.get('IsTest')=='true'
    assert r.find('n:Election',ns).get('Date')=='2026-11-03'
    gp={e.get('ObjectId'):e for e in r.findall('n:GpUnitCollection/n:GpUnit',ns)}
    assert len(gp)==320
    cl=obj('live-counties');assert len(cl)==88 and len({x['value'] for x in cl})==88
    cname={x['value']:x['name'] for x in cl};assert set(cname.values())=={c['county_native_id'] for c in counties}
    # Another 88 County-typed GpUnits are jurisdictional scopes with County suffix,
    # without report stats. They are not another set of county reporting totals.
    cands={e.get('ObjectId'):e for e in r.findall('.//n:Candidate',ns)}
    sen=next(e for e in r.findall('.//n:Contest',ns) if e.get('Name')=='U.S. Senator')
    stateid=sen.findtext('n:JurisdictionalScopeId',namespaces=ns)
    xmlchoices=[];xmlcounts=[]
    for sel in sen.findall('n:BallotSelection',ns):
        ci=sel.findtext('n:CandidateId',namespaces=ns);ca=cands[ci]
        vs=sel.findall('.//n:VoteCounts',ns);assert len(vs)==89
        assert {v.findtext('n:GpUnitId',namespaces=ns) for v in vs}==set(cname)|{stateid}
        assert all(v.get('Count')=='0' and v.get('Type')=='Total' for v in vs)
        xmlchoices.append({'candidate_id':ci,'selection_id':sel.get('ObjectId'),'xml_label':ca.findtext('.//n:LanguageString',namespaces=ns),'is_write_in':sel.get('IsWriteIn'),'party_id':ca.findtext('n:PartyId',namespaces=ns)})
        for v in vs:xmlcounts.append({'county_or_state_id':v.findtext('n:GpUnitId',namespaces=ns),'candidate_id':ci,'count':int(v.get('Count')),'method':v.get('Type'),'is_test':True})
    assert len(xmlchoices)==7 and len(xmlcounts)==623
    csvout('mock-xml-candidate-identities.csv',xmlchoices);csvout('mock-xml-senate-counts.csv',xmlcounts)
    ballots=obj('live-ballots');assert len(ballots)==90
    tots=ballots[0];assert tots['name']=='Totals' and tots['objectId'] is None
    county_ballots=[x for x in ballots if x['objectId'] in cname]
    null_rows=[(i,x) for i,x in enumerate(ballots) if x['objectId'] is None]
    assert len(county_ballots)==88 and len({x['objectId'] for x in county_ballots})==88
    assert len(null_rows)==2 and null_rows[-1][0]==89 and null_rows[-1][1]['name']=='Totals' and null_rows[-1][1]['totalNumPrecincts']==0
    assert int(tots['totalNumPrecincts'])==8834==sum(int(x['totalNumPrecincts']) for x in county_ballots)
    csvout('mock-ballot-rows.csv',[{'source_row_zero_based':i,**x} for i,x in enumerate(ballots)])
    csvrows=list(csv.DictReader(io.StringIO(body('live-ballots-csv').decode())))
    assert len(csvrows)==90 and csvrows[0]['County']=='Totals' and csvrows[-1]['County']=='Totals'
    assert {x['County'] for x in csvrows[1:-1]}==set(cname.values())
    with zipfile.ZipFile(io.BytesIO(body('live-xls'))) as z:
        xn={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',xn)]
        assert 'November 3, 2026 General Unofficial Canvass' in strings[0]
        wb=ET.fromstring(z.read('xl/workbook.xml'));sheets=wb.findall('s:sheets/s:sheet',xn)
        assert [x.get('name') for x in sheets]==['Contents','Master','Statewide Offices','Supreme Court','U.S. Congress','Court of Appeals','General Assembly']
        cells={}
        for cell in ET.fromstring(z.read('xl/worksheets/sheet2.xml')).findall('.//s:c',xn):
            value=cell.find('s:v',xn)
            if value is not None:cells[cell.get('r')]=strings[int(value.text)] if cell.get('t')=='s' else value.text
        cols=['AB','AC','AD','AE','AF','AG','AH']
        headers=[cells[c+'2'] for c in cols]
        assert headers==['Sherrod Brown (D)','Stephen Faris (WI)*','Anthony Holliman (WI)*','Jon Husted (R)','Greg Levy','William B. Redpath (L)','Timothy Telymonde (WI)*']
        assert {cells['A'+str(i)] for i in range(5,93)}==set(cname.values())
        assert all(cells[c+str(i)]=='0' for c in cols for i in [3]+list(range(5,93)))
        dump('mock-workbook-checks.json',{'sheets':[x.get('name') for x in sheets],'election_header':strings[0],'senate_header':cells['AB1'],'candidate_headers':headers,'candidate_columns':cols,'county_rows':'Master5:92','statewide_row':3,'county_count':88,'zero_senate_candidate_cells':623,'explicit_writein_notice':next(s for s in strings if 'Results for write-in' in s),'classification':'November setup linked contemporaneously to explicit mock marquee/XML; workbook itself has no tested boolean IsTest cell. Not counted votes.','numeric_contest_candidate_ids':None,'voting_method_columns_in_selected_senate_block':None})
    assert all(x['balCast']==x['outAbsenteeNum']==x['outProvisionalsNum']==0 for x in ballots)
    live=obj('live-senate');assert live['contestId'] is None and live['isElectionOfficial'] is True
    novchoices=live['contestList'][0]['candidatesRunning'];assert len(novchoices)==7
    live_names={x['primaryCandidate'] for x in novchoices};assert 'William B. Redpath' in live_names
    localnotes=json.loads((ROOT/'local-observations.json').read_text())
    pc=[]
    for c in priority:
        key=c['county_native_id'].lower();v=obj('state-county-'+key)
        b=next(x for x in v['contestList'] if x['name']=='U.S. Senator')
        assert b['objectId']==sen.get('ObjectId')
        assert {x['primaryCandidate'] for x in b['candidatesRunning']}==live_names
        assert all(x['totalVotes']==0 for x in b['candidatesRunning'])
        ps=next(x for x in county_ballots if x['name']==c['county_native_id'])
        assert b['totalPrecincts']==int(ps['totalNumPrecincts'])
        pc.append({'rank':c['rank'],'county':c['county_native_id'],'county_fips':c['county_fips'],'baseline_senate_votes':c['senate_2024_votes'],'historical_2024_units':sum(x['county_fips']==c['county_fips'] for x in units),'mock_2026_total_precincts':b['totalPrecincts'],'mock_candidates':len(b['candidatesRunning']),'test_status':'explicit statewide mock; all seven zero','county_native_id':v['contestId'],'source':'state-county-'+key,'local_observation':localnotes[c['county_native_id']]['observation']})
    csvout('priority-inspection.csv',pc)
    dump('mock-state-schema-checks.json',{'retrieved_utc':meta('live-xml')['retrieved_utc'],'root_attributes':r.attrib,'election_attributes':r.find('n:Election',ns).attrib,'xml_gpunit_types':dict(collections.Counter(e.get('Type') for e in gp.values())),'reporting_counties':88,'ballots_rows':90,'null_objectId_Totals_rows':[{'source_row_zero_based':i,**x} for i,x in null_rows],'senate_summary_top_contestId':live['contestId'],'isElectionOfficial_in_mock':live['isElectionOfficial'],'county_total_precincts':8834,'senate_candidate_count':7,'state_and_county_candidate_total_cells':623,'individually_tested_county_json':32,'priority_candidate_cells':224,'precinct_records_in_state_xml':0,'method_counts_in_senate_xml':['Total'],'blank_candidate_IDs':sum(not x['candidate_id'] for x in xmlchoices),'warning':'Test IsTest overrides isElectionOfficial=true and familiar date/name/ID. GpUnit County scopes are not duplicate reporting counties. TWO Totals rows have null IDs: leading8834-precinct total and trailing zero-precinct total; both retained and excluded from county rows. No November exact outstanding count inferred.'})
    repeat=ET.fromstring(body('live-xml-repeat'))
    def stripclock(x):
        x=ET.fromstring(ET.tostring(x));x.attrib.pop('GeneratedDate',None);return ET.tostring(x)
    dump('repeat-observation.json',{'first_fetch_utc':meta('live-xml')['retrieved_utc'],'repeat_fetch_utc':meta('live-xml-repeat')['retrieved_utc'],'first_generated':r.get('GeneratedDate'),'repeat_generated':repeat.get('GeneratedDate'),'byte_identical':body('live-xml')==body('live-xml-repeat'),'identical_after_removing_generated_date':stripclock(r)==stripclock(repeat),'first_sequence':r.get('Sequence'),'repeat_sequence':repeat.get('Sequence'),'note':'One repeat of test setup does not measure election-night publication cadence or a correction event.'})
    # All 88 official county authority URIs plus state, keeping observed outcomes.
    auth=json.loads((ROOT/'state-county-authorities.json').read_text());assert len(auth)==88
    amap={x['county']:x for x in auth};ids={x['name']:x['value'] for x in cl}
    inventory=[]
    for c in sorted(counties,key=lambda c:c['county_fips']):
        county=c['county_native_id'];key='county-'+county.lower().replace(' ','');m=meta(key);note=localnotes.get(county,{})
        if (ROOT/('repair-'+key+'.meta.json')).exists():key='repair-'+key;m=meta(key)
        inventory.append({'authority':county+' County Board of Elections','county_fips':c['county_fips'],'priority_rank':c['rank'] if c['rank']<=32 else '', 'official_directory':'https://www.ohiosos.gov/directories/local-election-results','state_published_uri':amap[county]['url'],'observed_effective_uri':m['transport'].get('url_effective',''),'native_state_mock_county_id':ids[county],'http_status':m['transport'].get('http_code',0),'curl_exit':m['curl_exit'],'retrieved_utc':m['retrieved_utc'],'original_sha256':m['original_sha256'],'evidence':key+'.meta.json','local_followed_sources':';'.join(note.get('sources',[])),'observation':note.get('observation','Official state-linked authority route requested; bounded landing inventory only. November local dataset/vendor/schema not independently established.'),'methods_observed':note.get('methods',''),'prescribed_state_submission_schedule':schedule[county]+' EST; Directive2026-48; future requirement, not observed cadence','outstanding_eligible_senate_votes':None,'local_cadence_measured':False,'overlap':'County-only view overlaps state aggregate. Do not sum sources/snapshots.'})
    sm=meta('live-xml')
    inventory.insert(0,{'authority':'Ohio Secretary of State','county_fips':'','priority_rank':'','official_directory':'https://data.ohiosos.gov/portal/election-dashboards','state_published_uri':'https://liveresults.ohiosos.gov/','observed_effective_uri':sm['transport'].get('url_effective',''),'native_state_mock_county_id':stateid,'http_status':sm['transport'].get('http_code'),'curl_exit':sm['curl_exit'],'retrieved_utc':sm['retrieved_utc'],'original_sha256':sm['original_sha256'],'evidence':'live-xml.meta.json','local_followed_sources':'live-bundle;live-senate;live-ballots;live-xls;live-marquee','observation':'Actual November setup explicitly MOCK/IsTest true. 88 reporting counties, statewide overlap, no precinct-level Senate feed. Not counted votes.','methods_observed':'Senate XML Total only; separate county ballot statistics','outstanding_eligible_senate_votes':None,'local_cadence_measured':False,'overlap':'Statewide view contains the same 88 county populations.'})
    inventory[0]['prescribed_state_submission_schedule']='Advertised XML/client refresh180seconds; no measured November count cadence'
    with (DATA/'official-results-sources.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(inventory)
    # Transport, lossless bytes, archive/snapshot bounds, source-hash inventory.
    manifest=[];failed=[];total_raw=0
    for f in sorted(ROOT.glob('*.meta.json')):
        m=json.loads(f.read_text());b=body(m['id']);assert len(b)==m['original_bytes'] and sha(b)==m['original_sha256'],m['id']
        assert sha((ROOT/m['body']).read_bytes())==m['stored_sha256'],m['id']
        hd=(ROOT/m['headers']).read_text(errors='replace');low=hd.lower()
        assert not ('content truncated by length' in low or 'wayback content truncated' in low),m['id']
        total_raw+=len(b)
        manifest.append({'id':m['id'],'url':m['requested_url'],'discovered_from':m['discovered_from'],'retrieved_utc':m['retrieved_utc'],'effective_url':m['transport'].get('url_effective'),'http_status':m['transport'].get('http_code',0),'curl_exit':m['curl_exit'],'original_bytes':len(b),'original_sha256':m['original_sha256'],'body':m['body'],'archive_member':m.get('archive_member'),'stored_sha256':m['stored_sha256'],'headers':m['headers'],'headers_sha256':sha((ROOT/m['headers']).read_bytes())})
        if m['transport'].get('http_code',0)!=200 or m['curl_exit']!=0:failed.append(m['id'])
    dump('source-manifest.json',manifest)
    assert len(inventory)==89 and len(pc)==32
    when=datetime.datetime(2026,11,3,19,30,tzinfo=ZoneInfo('America/New_York'))
    assert when.astimezone(datetime.timezone.utc).isoformat()=='2026-11-04T00:30:00+00:00'
    # All report-relative links must resolve, including sibling read-only evidence.
    report=STATE/'official-results.md'
    links=[]
    if report.exists():
        for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
            if '://' in target or target.startswith('#'):continue
            target=target.split('#')[0];assert (report.parent/target).exists(),target;links.append(target)
    files=[f for f in ROOT.rglob('*') if f.is_file()];assert all(f.stat().st_size<40*1024*1024 for f in files)
    summary={'validated_utc':now,'status':'PASS_WITH_EXPLICIT_SOURCE_GAPS','authorities':89,'counties':88,'priority_counties_deep_inspected':32,'reparsed_certified_county_candidate_cells':2464,'state_candidate_controls':28,'local_summary_candidate_rows':len(countychecks),'local_summary_observed_candidate_matches':sum(x['local_votes'] is not None for x in countychecks),'Delaware_precinct_candidate_matches':len(delchecks),'Cuyahoga_precinct_candidate_comparisons':len(evchecks),'Cuyahoga_precinct_candidate_matches':2900,'Cuyahoga_precinct_source_differences':1,'priority_mock_candidate_cells':224,'mock_XML_cells':623,'mock_county_precinct_controls':8834,'source_requests':len(manifest),'failed_or_non200_requests':len(failed),'failed_or_non200_ids':failed,'original_response_bytes':total_raw,'source_files':len(files),'max_file_bytes':max(f.stat().st_size for f in files),'report_relative_links':len(links),'november_close_utc':when.astimezone(datetime.timezone.utc).isoformat(),'known_material_limits':['State dataset is test; false isElectionOfficial interpretation rejected','Cuyahoga Brown one vote higher at NORTH OLMSTED-02-A; generic Write-In 530 versus 113 named certified write-ins leaves417 scope residual; total418 difference','Franklin post-audit amendment decreases Brown/Moreno one each from original baseline; both vintages preserved','Wayne 2024-labelled summary actually 2022 scanned report; excluded from 2024','Shared BOE host raw403; browser rendering used where available','No genuine November live returns, method/unit crosswalk, measured election-night release/correction history or accepted-unprocessed Senate ballot ledger']}
    dump('validation.json',summary)
    summary['report_sha256']=sha(report.read_bytes()) if report.exists() else None
    summary['inventory_sha256']=sha((DATA/'official-results-sources.csv').read_bytes())
    dump('validation.json',summary)
    artifact=[{'path':str(f.relative_to(ROOT)),'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())} for f in sorted(ROOT.rglob('*')) if f.is_file() and f.name!='artifact-manifest.json' and '__pycache__' not in f.parts]
    dump('artifact-manifest.json',artifact)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['failed_or_non200_ids','known_material_limits']},indent=2))
if __name__=='__main__':main()
