#!/usr/bin/env python3
"""Offline controls independent of generated ranking constants and source edits."""
import collections,csv,gzip,hashlib,io,json,re,subprocess,sys
from pathlib import Path
sys.dont_write_bytecode=True
from finalize_artifacts import ROOT,STATE,ledger,manifest,sha

def csvread(p):
    op=gzip.open if str(p).endswith('.gz') else open
    with op(p,'rt',newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def payload(meta,base):
    if 'stored_parts' in meta:
        chunks=[]
        for r in meta['stored_parts']:
            b=(base/r['path']).read_bytes();assert len(b)==r['bytes'] and sha(b)==r['sha256'];chunks.append(b)
        stored=b''.join(chunks)
    else:stored=(base/meta.get('stored_path',meta.get('asset'))).read_bytes()
    assert sha(stored)==meta.get('stored_sha256');raw=gzip.decompress(stored);assert sha(raw)==meta.get('original_sha256',meta.get('raw_sha256'));return raw

def run():
    (ROOT/'validation.json').write_text(json.dumps({'status':'running','scope':'offline validation in progress'})+'\n')
    ledger();manifest();sources=json.load(open(ROOT/'source-ledger.json'));verified={};raw={}
    for m in sources['sources']:
        base=ROOT/m.get('dependency_root','');body=payload(m,base);raw[m['id']]=body;verified[m['id']]={'status':m['status'],'original_bytes':len(body),'original_sha256':sha(body)}
    c=csvread(STATE/'data/county-turnout.csv');assert len(c)==254;assert len({r['county_fips'] for r in c})==254;assert {r['county_fips'] for r in c}=={'48'+f'{n:03d}' for n in range(1,508,2)}
    allcand=csvread(ROOT/'county-candidates-2024.csv')+csvread(ROOT/'county-candidates-comparators.csv');assert len(allcand)==6604
    assert len({(r['contest'],r['county_fips'],r['source_candidate_name']) for r in allcand})==len(allcand)
    specs=[('senate','sos-2024-canvass-archive','U. S. SENATOR','senate_2024'),('president','sos-2024-canvass-archive','PRESIDENT/VICE-PRESIDENT','president_2024'),('senate_2020','sos2020-state-20210510','U. S. SENATOR','senate_2020'),('governor_2022','sos2022-state-20230627','GOVERNOR','governor_2022')];controls={}
    for contest,source,heading,prefix in specs:
        txt=subprocess.run(['pdftotext','-layout','-','-'],input=raw[source],capture_output=True,check=True).stdout.decode();start=re.search(r'^'+re.escape(heading)+r'\s+',txt,re.M).start();section=txt[start:];stop=re.search(r'Total Votes\s+([\d,]+)',section);assert stop;section=section[:stop.end()]
        state=[(m[1].strip(),m[2],int(m[3].replace(',',''))) for m in re.finditer(r'^\s*(.+?)\s+(REP|DEM|LIB|GRE|WRI)\s+([\d,]+)\s+[0-9.]+\s*%',section,re.M)]
        rows=[r for r in allcand if r['contest']==contest];names=list(dict.fromkeys(r['source_candidate_name'] for r in rows));assert len(state)==len(names),(contest,state,names)
        state_total=int(stop[1].replace(',',''));assert sum(r[2] for r in state)==state_total
        for name,(_,party,count) in zip(names,state):
            selected=[r for r in rows if r['source_candidate_name']==name];assert len(selected)==254;assert sum(int(r['votes']) for r in selected)==count;assert all(r['source_party']==party for r in selected)
        for county in c:
            rr=[r for r in rows if r['county_fips']==county['county_fips']];total=sum(int(r['votes']) for r in rr);assert total==int(county[prefix+'_total']);assert {r['source_county_name'] for r in rr}=={county['source_county_name']};assert {r['source_county_total'] for r in rr}=={str(total)}
            d=sum(int(r['votes']) for r in rr if r['source_party']=='DEM');r=sum(int(r['votes']) for r in rr if r['source_party']=='REP');assert (d,r,total-d-r)==tuple(int(county[prefix+'_'+f]) for f in ['d','r','other'])
        controls[contest]={'source_id':source,'candidates':len(state),'candidate_votes':state_total,'all_county_candidate_control':'pass'}
    # Independent published Clerk table, no second download.
    clerk=STATE.parent/'ohio/data/baselines/house-2024.txt';cl=clerk.read_text();tex=cl[cl.index('\n                                                                                                  TEXAS\n'):];tex=tex[:tex.index('FOR UNITED STATES REPRESENTATIVE')]
    for name,count in [('Ted Cruz',sum(int(r['senate_2024_r']) for r in c)),('Colin Z. Allred',sum(int(r['senate_2024_d']) for r in c)),('Ted Brown',sum(int(r['senate_2024_brown']) for r in c)),('Tracy Andrus',sum(int(r['senate_2024_andrus_writein']) for r in c)),('Analisa Roche',sum(int(r['senate_2024_roche_writein']) for r in c))]:
        line=next(x for x in tex.splitlines() if name in x);assert int(re.search(r'([\d,]+)\s*$',line)[1].replace(',',''))==count
    ordered=sorted(c,key=lambda r:(-int(r['senate_2024_total']),r['county_fips']));assert c==ordered;p=json.load(open(ROOT/'priority-set.json'));den=controls['senate']['candidate_votes'];assert p['source_denominator']==den;cum=0;cross=None
    for i,r in enumerate(c,1):
        cum+=int(r['senate_2024_total']);assert int(r['rank'])==i and int(r['cumulative_senate_2024'])==cum;assert abs(float(r['share_state_senate_2024'])-int(r['senate_2024_total'])/den)<1e-14;assert abs(float(r['cumulative_share_state_senate_2024'])-cum/den)<1e-14;assert r['dispatch_key']=='TX:'+r['county_fips']
        if cross is None and 5*cum>=4*den:cross=i
    assert cum==den;assert p['full_order']==[r['dispatch_key'] for r in c];assert p['priority_keys']==p['full_order'][:cross];assert p['remainder_keys']==p['full_order'][cross:];assert p['minimum80_count']==cross
    nums=[int(r['senate_2024_total']) for r in c];assert p['top15_votes']==sum(nums[:15]);assert p['preceding_set_votes']==sum(nums[:cross-1]);assert p['minimum80_votes']==sum(nums[:cross]);assert 5*p['preceding_set_votes']<4*den<=5*p['minimum80_votes'];assert p['remainder_votes']==sum(nums[cross:]);assert p['crossing_county']==p['full_order'][cross-1]
    for i,r in enumerate(c,1):assert int(r['top15'])==int(i<=15) and int(r['priority80'])==int(i<=cross)
    keyfile=STATE/'data/coordinator-priority-keys.txt'
    if keyfile.exists():assert keyfile.read_text().splitlines()==p['priority_keys']
    # Replay all pinned native source rows and units. Repeated headers retained as explicit nondata evidence.
    native_checks={};roster=csvread(ROOT/'native-reporting-units.csv.gz');inventory={(r['source_id'],r['source_county_name'],r['native_unit_id']):r for r in roster};assert len(inventory)==len(roster)
    for year in ['2024','2022','2020']:
        records=csvread(ROOT/('native-records-'+year+'.csv.gz'));by=collections.defaultdict(dict)
        for r in records:assert int(r['source_row']) not in by[r['source_id']];by[r['source_id']][int(r['source_row'])]=r
        total=0;unique=set()
        for source,body in raw.items():
            if not ((year=='2024' and source.startswith('oe2024-')) or (source=='oe-tx'+year)):continue
            rows=csv.DictReader(io.StringIO(body.decode('utf-8-sig')));selected=0;counts=collections.Counter()
            for rn,r in enumerate(rows,2):
                if r.get('county')=='county' and r.get('office')=='office':continue
                key=(source,r.get('county',''),r.get('precinct',''));counts[key]+=1;unique.add(key)
                office=re.sub('[^A-Z0-9]','',r.get('office','').upper());ss={'USSENATE','USSENATOR','UNITEDSTATESSENATOR'};pp={'PRESIDENT','PRESIDENTANDVICEPRESIDENT','PRESIDENTVICEPRESIDENT'};gg={'GOVERNOR','GOVERNORWRITEIN','GOVERNOR1'}
                wanted=office in ((ss|pp) if year=='2024' else gg if year=='2022' else ss) or office in {'REGISTEREDVOTERS','BALLOTSCAST','BALLOTSCASTTOTAL','BALLOTSCASTBLANK','VOTERSCAST','VOTERTURNOUT'}
                if wanted:
                    rec=by[source][rn];assert json.loads(rec['source_fields_json'])==r;assert rec['votes']==r.get('votes','') and rec['native_unit_id']==r.get('precinct','');selected+=1
            assert selected==len(by[source]);total+=selected
            for key,n in counts.items():assert int(inventory[key]['source_rows'])==n
        assert total==len(records);native_checks[year]={'selected_rows':total,'inventory_keys':len(unique),'source_row_replay':'pass'}
    assert sum(r['inventory_keys'] for r in native_checks.values())==len(roster)
    originals=csvread(ROOT/'primary-native-units.csv.gz');assert len({(r['source_id'],r['native_unit_id']) for r in originals})==len(originals);assert {'Precinct 11B','Precinct 17B'}<=set(r['native_unit_id'] for r in originals if r['source_id']=='original-angelina-2024')
    # The priority contract must contain every inventory identity in its own source layer.
    constituents={(x.get('source_id'),x.get('native_id')) for g in p['groups'] for x in g['native_constituents'] if x['layer']=='Original county precinct/vendor report'};assert constituents=={(r['source_id'],r['native_unit_id']) for r in originals}
    nc={(x.get('source_id'),x.get('native_unit_key')) for g in p['groups'] for x in g['native_constituents'] if x['layer']=='OpenElections county-source derivative'};assert nc=={(r['source_id'],r['native_unit_key']) for r in roster}
    hc=csvread(ROOT/'primary-harris-senate-units.csv.gz');assert len(hc)==len({r['native_unit_id'] for r in hc})
    for r in hc:
        v=json.loads(r['source_values_json']);assert sum(v[k] for k in ['TED CRUZ','COLIN ALLRED','TED BROWN','Analisa Roche (W)','Tracy Andrus (W)'])==v['Cast Votes'];assert v['Cast Votes']+v['Undervotes']+v['Overvotes']==v['Total Ballots Cast'];assert sum(v[k] for k in ['Ballot by Mail Ballots Cast','Early Voting Ballots Cast','Election Day Ballots Cast','EV Provisional Ballots Cast','ED Provisional Ballots Cast'])==v['Total Ballots Cast']
    vendorrows=csvread(ROOT/'primary-native-records.csv.gz')
    for r in vendorrows:
        labels=json.loads(r['column_header_json']);values=json.loads(r['source_values_json']);assert len(labels)==len(values)
        if 'Total Votes' in labels:
            start=2;blocks=[]
            for i,label in enumerate(labels):
                if label=='Total Votes':
                    assert sum(int(v) for v in values[start:i])==int(values[i]),(r['source_id'],r['source_row'],label)
                    blocks.append(int(values[i]));start=i+1
            assert sum(blocks)==int(values[-1])
        else:
            bi=labels.index('Ballots Cast');assert sum(int(v) for v in values[2:bi])==int(values[bi])
    vt=csvread(ROOT/'tlc-derived-vtd-units.csv.gz');vby=collections.defaultdict(list)
    for r in vt:vby[r['source_id']].append(r)
    recon=csvread(ROOT/'tlc-county-reconciliation.csv');rmap={(r['source_id'],r['county_fips'],r['source_candidate_or_measure']):r for r in recon}
    for source,rows in vby.items():
        original=list(csv.DictReader(io.StringIO(raw[source].decode('utf-8-sig'))));assert len(rows)==len(original)
        assert len({(r['CNTYVTD'],r['VTDKEY']) for r in rows})==len(rows)
        assert {r['county_fips'] for r in rows}=={r['county_fips'] for r in c};ag=collections.Counter()
        for saved,native in zip(rows,original):
            assert json.loads(saved['source_fields_json'])==native;assert saved['county_fips']=='48'+native['CNTYVTD'][:3]
            for field,value in native.items():
                if field in ['CNTYVTD','VTDKEY'] or ('voterdata' in source and field not in ['Voter_Registration','Turnout']):continue
                ag[(saved['county_fips'],field)]+=int(value)
        for (fips,field),value in ag.items():
            rr=rmap[(source,fips,field)];assert int(rr['derived_count'])==value
            if rr['primary_count']:assert int(rr['derived_minus_primary'])==value-int(rr['primary_count'])
    # Unknown controls remain blank except explicitly sourced observed counties.
    for r in c:
        for key in ['governor_2022_total','senate_2020_total']:assert int(r[key])>0
        if not r['ballots_source_id_2024']:assert r['ballots_cast_2024']==r['registered_voters_2024']==''
        assert r['registered_voters_2020']==r['registered_voters_2022']==r['ballots_cast_2020']==r['ballots_cast_2022']==''
    peer=json.load(open(ROOT/'peer-reconciliation.json'));assert peer['status']=='pass';assert peer['input_sha256']['county-turnout.csv']==sha((STATE/'data/county-turnout.csv').read_bytes())
    text=(STATE/'turnout.md').read_text();links=re.findall(r'\[[^\]]*\]\(([^)]+)\)',text);checkedlinks=[]
    for link in links:
        if '://' in link or link.startswith('#'):continue
        target=STATE/link.split('#')[0];assert target.exists(),link;checkedlinks.append(link)
    result={'status':'pass','source_payloads_and_hashes_verified':len(verified),'primary_contests':controls,'county_rows':len(c),'candidate_county_cells':len(allcand),'primary_county_native_labels':254,'full_rank_and_exact_integer_minimum80':'pass','top15_votes':p['top15_votes'],'minimum80_count':cross,'minimum80_votes':p['minimum80_votes'],'preceding_set_votes':p['preceding_set_votes'],'remainder_votes':p['remainder_votes'],'native_raw_replay':native_checks,'primary_native_units':len(originals),'harris_all_unit_candidate_ballot_method_controls':'pass','original_vendor_rows_checked':len(vendorrows),'original_vendor_candidate_and_ballot_method_controls':'pass','tlc_source_rows_replayed':len(vt),'tlc_source_county_sums':'pass','peer_shared_fields':peer['field_checks'],'relative_report_links_checked':checkedlinks,'qualification':'Validation proves exact selected county controls and faithful source-scoped finer extracts, not correctness of conflicting native source counts, complete native statewide geography, boundary matches or2026 approval.'}
    (ROOT/'validation.json').write_text(json.dumps(result,indent=2)+'\n');assets=manifest()
    for r in assets:
        b=(STATE/r['path']).read_bytes();assert len(b)==r['bytes']<40000000 and sha(b)==r['sha256']
    print('PASS:',len(c),'counties',len(allcand),'primary candidate cells;',sum(r['selected_rows'] for r in native_checks.values()),'native rows replayed;',len(originals),'primary native units;',len(assets),'owned assets all<40000000 bytes')
if __name__=='__main__':run()
