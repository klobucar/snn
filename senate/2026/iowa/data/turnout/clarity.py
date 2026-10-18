#!/usr/bin/env python3
"""Acquire observed 2024 county report links from the actual state app configuration."""
import concurrent.futures,gzip,io,json,re,zipfile
import xml.etree.ElementTree as E
import acquire as a
import build as b

def bootstrap():
    """Replay the inspected app chain. Existing pinned records are not overwritten."""
    rows=a.load()
    def get(key,url,parent,label):
        r=next((r for r in rows if r['id']==key),None)
        if r is None:
            r=a.fetch((key,url,parent,label));rows.append(r);a.MANIFEST.write_text(json.dumps(rows,indent=2)+'\n')
        assert r['status']==200,(key,r['status']);return r
    app='https://electionresults.iowa.gov/IA/122322/web.345435/'
    r=get('sos-2024-precinct-app-retry',app,'https://sos.iowa.gov/iowans/election-results-statistics','Actual linked historical precinct application retry')
    shell=a.raw(r).decode()
    for script in re.findall(r'<script[^>]+src="([^"]+)"',shell):get('sos-2024-app-'+script.replace('.','-'),app+script,app,'Actual script src')
    main=next(r for r in rows if r['id']=='sos-2024-app-main-js');js=a.raw(main).decode()
    assert 'FileName["WebConfig"] = "web.json"' in js and 'FileName["Version"] = "current_ver.txt"' in js
    r=get('sos-2024-app-web-config',app+'web.json',app+'main.js','ENRWebConfigService.get ./web.json');config=json.loads(a.raw(r))
    base=config['jsonUri'].rstrip('/')+'/'+config['State']+'/'+config['EID']
    r=get('sos-2024-app-version',base+'/current_ver.txt',app+'main.js','Actual getBaseUri + FileName.Version');version=a.raw(r).decode().strip()
    r=get('sos-2024-app-config-json',base+'/'+version+'/json/config.json',app+'main.js','Actual getUri + FileName.Config');cfg=json.loads(a.raw(r));lang=cfg['lang']
    for name in ['status.json','sum.json']:
        get('sos-2024-app-'+name.replace('.','-'),base+'/'+version+'/json/'+name,app+'main.js','Actual getUri + enum filename')
    for suffix in [f'json/{lang}/nav.json',f'json/{lang}/electionsettings.json','reports/detailxls.zip','reports/detailxml.zip']:
        get('sos-2024-state-'+suffix.replace('/','-').replace('.','-'),base+'/'+version+'/'+suffix,app+'main.js','Actual app URI template; observed configuration lang/version')

def acquire_counties():
    rows=a.load();r=next(r for r in rows if r['id']=='sos-2024-state-json-en-electionsettings-json')
    settings=json.loads(a.raw(r))
    def find(o,path=''):
        if isinstance(o,dict):
            for k,v in o.items():
                if k=='participatingcounties':return path+'/'+k,v
                found=find(v,path+'/'+k)
                if found:return found
        return None
    parts_path,parts=find(settings);tasks=[];roster=[]
    for literal in parts:
        native,eid,version,clock,template=literal.split('|');county=native.replace('_',' ');fips=b.COUNTIES[county]['county_fips']
        base=f'https://electionresults.iowa.gov/IA/{native}/{eid}/{version}/'
        roster.append(dict(county=county,county_fips=fips,native_county_path=native,election_id=eid,pinned_version=version,source_clock=clock,template=template,raw_participating_county=literal,parent_source_id=r['id'],parent_json_path=parts_path))
        for suffix,key in [('reports/detailxml.zip','xml'),('json/en/electionsettings.json','settings'),('json/status.json','status')]:
            tasks.append((f'sos-2024-county-{key}-{fips}',base+suffix,r['url'],'Actual participatingcounties EID/version; app getUriReports/getUri template, no guessed election IDs'))
    (a.ROOT/'clarity-county-roster.json').write_text(json.dumps(roster,indent=2)+'\n')
    ids={r['id'] for r in rows}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(a.fetch,[t for t in tasks if t[0] not in ids]):
            rows.append(r);a.MANIFEST.write_text(json.dumps(rows,indent=2)+'\n');print(r['id'],r.get('status'),r.get('original_bytes'),flush=True)

def extract():
    sources=a.load();roster=json.loads((a.ROOT/'clarity-county-roster.json').read_text());rs={r['id']:r for r in sources}
    units=[];votes=[];controls=[];turnout=[];context=[];checks=[];statusrows=[]
    for c in roster:
        r=rs[f"sos-2024-county-xml-{c['county_fips']}"]
        if r['status']!=200:checks.append(dict(**c,status='download_gap',http_status=r['status']));continue
        z=zipfile.ZipFile(io.BytesIO(a.raw(r)));members=z.namelist();assert members==['detail.xml'],members
        data=z.read('detail.xml');root=E.fromstring(data);assert root.findtext('ElectionDate')=='11/5/2024'
        contest=next(x for x in root.findall('Contest') if x.get('text')=='President and Vice President')
        tv=root.find('VoterTurnout');stamp=root.findtext('Timestamp');region=root.findtext('Region');assert region==c['county']
        # Keep contest, turnout, status precinct contexts distinct. Lucas actually omits
        # two candidate reporting units from VoterTurnout/status; never allocate them.
        canonical=contest.find('Choice/VoteType').findall('Precinct');candidate_labels=[p.get('name') for p in canonical]
        assert len(candidate_labels)==len(set(candidate_labels)),c
        name_uid={name:f"{r['id']}|Contest[{contest.get('key')}]/Precinct[{i}]" for i,name in enumerate(candidate_labels,1)}
        for ordinal,p in enumerate(canonical,1):
            units.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],unit_key=name_uid[p.get('name')],native_unit_label=p.get('name'),native_unit_id=p.get('key'),source_xml_path=f"Contest[@key='{contest.get('key')}']/Choice[1]/VoteType[1]/Precinct[{ordinal}]",source_ordinal=ordinal,source_contest_key=contest.get('key'),native_election_id=c['election_id'],native_version=c['pinned_version'],unit_kind='native_XML_Contest_Precinct; physical/split/style identity unestablished',source_clock=stamp,source_reporting_flag=None))
        sr=rs[f"sos-2024-county-status-{c['county_fips']}"];st=json.loads(a.raw(sr))
        for i,name in enumerate(st['P']):
            statusrows.append(dict(county=c['county'],county_fips=c['county_fips'],source_id=sr['id'],source_index=i,native_unit_label=name,unit_key=f"{sr['id']}|P[{i}]",**{key:st[key][i] if isinstance(st.get(key),list) else st.get(key) for key in ['S','R','B','C','CONTEST','PT','U']}))
        # Native XML has ordinal/name precinct identities; no separate ID invented.
        precs=tv.find('Precincts').findall('Precinct')
        for ordinal,p in enumerate(precs,1):
            uid=f"{r['id']}|VoterTurnout/Precincts/Precinct[{ordinal}]"
            units.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],unit_key=uid,native_unit_label=p.get('name'),native_unit_id=p.get('key'),source_xml_path=f'VoterTurnout/Precincts/Precinct[{ordinal}]',source_ordinal=ordinal,source_contest_key=None,native_election_id=c['election_id'],native_version=c['pinned_version'],unit_kind='native_XML_Precinct; physical/split/style identity unestablished',source_clock=stamp,source_reporting_flag=p.get('percentReporting')))
            turnout.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],unit_key=uid,native_unit_label=p.get('name'),source_scope='native_precinct',source_xml_path=f'VoterTurnout/Precincts/Precinct[{ordinal}]',totalVoters=p.get('totalVoters'),ballotsCast=p.get('ballotsCast'),voterTurnout=p.get('voterTurnout'),percentReporting=p.get('percentReporting'),source_clock=stamp))
        turnout.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],unit_key=None,native_unit_label=None,source_scope='county_administrative_control',source_xml_path='VoterTurnout',totalVoters=tv.get('totalVoters'),ballotsCast=tv.get('ballotsCast'),voterTurnout=tv.get('voterTurnout'),percentReporting=None,source_clock=stamp))
        labels=[p.get('name') for p in precs];assert len(labels)==len(set(labels)),c
        for choice in contest.findall('Choice'):
            label=choice.get('text');party=choice.get('party');ck=choice.get('key');method_sum=0
            controls.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],source_contest_key=contest.get('key'),native_choice_key=ck,native_candidate_label=label,party_header=party,native_method='Total',votes=int(choice.get('totalVotes')),source_clock=stamp))
            for vt in choice.findall('VoteType'):
                method=vt.get('name');value=int(vt.get('votes'));method_sum+=value;parts=vt.findall('Precinct');assert [p.get('name') for p in parts]==candidate_labels,(c,label,method)
                assert sum(int(p.get('votes')) for p in parts)==value,(c,label,method)
                controls.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],source_contest_key=contest.get('key'),native_choice_key=ck,native_candidate_label=label,party_header=party,native_method=method,votes=value,source_clock=stamp))
                for ordinal,p in enumerate(parts,1):votes.append(dict(year=2024,county=c['county'],county_fips=c['county_fips'],source_id=r['id'],source_xml_path=f"Contest[@key='{contest.get('key')}']/Choice[@key='{ck}']/VoteType[@name='{method}']/Precinct[{ordinal}]",unit_key=name_uid[p.get('name')],native_unit_label=p.get('name'),source_unit_ordinal=ordinal,native_contest_key=contest.get('key'),native_choice_key=ck,native_candidate_label=label,party_header=party,native_method=method,votes=int(p.get('votes')),source_clock=stamp))
            assert method_sum==int(choice.get('totalVotes'))
        for vt in contest.findall('VoteType'):
            context.append(dict(county=c['county'],county_fips=c['county_fips'],source_id=r['id'],source_contest_key=contest.get('key'),source_scope='contest_administrative_control',native_metric=vt.get('name'),native_unit_label=None,value=vt.get('votes')))
            for p in vt.findall('Precinct'):context.append(dict(county=c['county'],county_fips=c['county_fips'],source_id=r['id'],source_contest_key=contest.get('key'),source_scope='contest_precinct_context',native_metric=vt.get('name'),native_unit_label=p.get('name'),value=p.get('votes')))
        checks.append(dict(**c,status='extracted',native_candidate_units=len(candidate_labels),native_turnout_units=len(precs),native_status_units=len(st['P']),candidate_units_not_in_turnout=[n for n in candidate_labels if n not in labels],turnout_units_not_in_candidate=[n for n in labels if n not in candidate_labels],source_contest_attributes=dict(contest.attrib),original_xml_member_sha256=a.sha(data),original_xml_member_bytes=len(data),xml_clock=stamp,all_candidate_unit_method_sums_exact=True))
    b.csvout('clarity-2024-native-units.csv',units);b.csvout('clarity-2024-native-candidate-method.csv',votes);b.csvout('clarity-2024-county-candidate-method.csv',controls);b.csvout('clarity-2024-registration-ballots.csv',turnout);b.csvout('clarity-2024-contest-context.csv',context);b.dump('clarity-2024-extraction.json',checks)
    b.csvout('clarity-2024-status-units.csv',statusrows)
    print('XMLCOUNTIES',len(checks),'UNITS',len(units),'CANDIDATECELLS',len(votes),'CONTROLS',len(controls))
if __name__=='__main__':
    import sys
    if '--extract' in sys.argv:extract()
    else:bootstrap();acquire_counties()
