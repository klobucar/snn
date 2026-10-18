#!/usr/bin/env python3
"""Offline assertions against retained source evidence and delivered tables.

Run extract_pdf_evidence.py after refreshing PDF sources. No network calls,
imports from the builder, installed Python packages, or mutations of inputs.
"""
import collections,csv,gzip,hashlib,io,json,re
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent.parent
def rows(path):return list(csv.DictReader(path.open()))
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
    results={}
    manifest=json.loads((ROOT/'manifest.json').read_text())
    for m in manifest:
        saved=(ROOT/m['saved_path']).read_bytes();original=gzip.decompress(saved)
        assert digest(saved)==m['saved_sha256'],m['source_id']
        assert digest(original)==m['original_sha256'],m['source_id']
        assert len(original)==m['original_bytes']
        assert m['retrieved_utc'].endswith('+00:00')
        assert len(saved)<40*1024*1024
    results['source_hashes_verified']=len(manifest)
    ranked=rows(STATE/'data/county-turnout.csv');assert len(ranked)==512
    assert len({r['native_key'] for r in ranked})==512
    assert sorted(ranked,key=lambda r:(-int(r['senate_votes_2024']),r['county_code'],r['unit_name'].strip()))==ranked
    assert sum(Fraction(r['weight_exact']) for r in ranked)==1
    assert sum(int(r['senate_votes_2024']) for r in ranked)==821072
    assert sum(int(r['blank_senate_2024']) for r in ranked)==21375
    assert sum(int(r['ballots_cast_2024']) for r in ranked)==842447
    cumul=0
    for i,r in enumerate(ranked,1):
        v=int(r['senate_votes_2024']);cumul+=v
        assert int(r['rank'])==i
        assert int(r['cumulative_votes'])==cumul
        assert Fraction(r['weight_exact'])==Fraction(v,821072)
        assert Fraction(r['cumulative_share_exact'])==Fraction(cumul,821072)
        assert int(r['top15'])==int(i<=15)
        assert int(r['minimum80'])==int(i<=164)
        assert int(r['priority'])==int(i<=164)
        assert v==sum(int(r[k]) for k in ['cherry_independent_2024','costello_democratic_2024','king_independent_2024','kouzounas_republican_2024'])
        assert v+int(r['blank_senate_2024'])==int(r['ballots_cast_2024'])
        assert (ROOT/r['source_path']).exists()
    assert sum(int(r['senate_votes_2024']) for r in ranked[:15])==215627
    first163=sum(int(r['senate_votes_2024']) for r in ranked[:163]);first164=first163+int(ranked[163]['senate_votes_2024'])
    assert first163==656778 and first164==658029
    assert 5*first163<4*821072<=5*first164
    assert ranked[163]['unit_name']=='Pownal'
    priority=json.loads((ROOT/'priority-set.json').read_text())
    keys=('\n'.join(r['native_key'] for r in ranked[:164])+'\n').encode()
    assert keys==(ROOT/'priority-keys.txt').read_bytes()
    assert digest(keys)==priority['ordered_priority_keys_sha256']=='086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'
    assert [r['native_key'] for r in priority['priority']]==[r['native_key'] for r in ranked[:164]]
    assert [r['native_key'] for r in priority['nonpriority_remainder']]==[r['native_key'] for r in ranked[164:]]
    assert [r['native_key'] for r in priority['all_unit_coverage']]==[r['native_key'] for r in ranked]
    uocava=[r for r in ranked if r['unit_name']=='STATE UOCAVA'];assert len(uocava)==1
    assert uocava[0]['county_code']==uocava[0]['county_fips']=='' and uocava[0]['rank']=='22'
    results['senate_units']=512;results['priority']=164;results['nonpriority']=348;results['exact_weights_sum']='1'
    # Every candidate, blank and ballot control in every selected election.
    expected={
      'senate-2024':[('Cherry, Jason S.',20193),('Costello, David Allen',88875),('King, Angus S. Jr.',427570),('Kouzounas, Demi',284434),('BLANK',21375),('TBC',842447)],
      'president-2024':[('Harris, Kamala D.',435652),('Oliver, Chase',5286),('Stein, Jill',8967),('Trump, Donald J.',377977),('West, Cornel',2912),('Others',581),('BLANK',11072),('TBC',842447)],
      'governor-2022':[('Hunkler, Sam',12581),('LePage, Paul R.',287304),('Mills, Janet T.',376934),('BLANK',4090),('TBC',680909)]}
    all_raw={}
    for name,control in expected.items():
        raw=rows(ROOT/(name+'-source-rows.csv'));all_raw[name]=raw
        totals=collections.Counter();byunit=collections.defaultdict(list)
        for r in raw:totals[r['candidate_or_category']]+=int(r['votes']);byunit[r['source_row_key']].append(r)
        assert dict(totals)==dict(control),(name,totals)
        for unit,part in byunit.items():
            assert len(part)==len(control) and len({x['candidate_or_category'] for x in part})==len(control)
            assert sum(int(x['votes']) for x in part if x['category']!='ballots')==next(int(x['votes']) for x in part if x['category']=='ballots')
        summary=json.loads((ROOT/'checks.json').read_text())['elections'][name]
        assert len(byunit)==summary['raw_unit_rows']
        assert len(summary['controls'])==17 and all(all(v==0 for v in c['difference']) for c in summary['controls'])
        comp=rows(ROOT/(name+'-ranked.csv'))
        assert len(comp)==summary['research_units']
        assert len({r['native_key'] for r in comp})==len(comp)
        assert sum(int(r['candidate_votes']) for r in comp)==summary['candidate_total']
        assert sum(int(r['ballots']) for r in comp)==summary['ballots']
        assert sum(Fraction(r['candidate_weight_exact']) for r in comp)==1
        assert sum(Fraction(r['ballot_weight_exact']) for r in comp)==1
        assert sorted(comp,key=lambda r:(-int(r['candidate_votes']),r['county_code'],r['unit_name'].strip()))==comp
        cc=0;cutoff=next(i for i,r in enumerate(comp,1) if 5*int(r['candidate_cumulative_votes'])>=4*summary['candidate_total'])
        for i,r in enumerate(comp,1):
            cc+=int(r['candidate_votes'])
            assert int(r['candidate_rank'])==i and int(r['candidate_cumulative_votes'])==cc
            assert Fraction(r['candidate_weight_exact'])==Fraction(int(r['candidate_votes']),summary['candidate_total'])
            assert Fraction(r['candidate_cumulative_weight_exact'])==Fraction(cc,summary['candidate_total'])
            assert (r['candidate_top15']=='True')==(i<=15)
            assert (r['candidate_minimum80']=='True')==(i<=cutoff)
        assert sum(int(r['candidate_votes']) for r in comp[:15])==summary['top15']
        assert cutoff==summary['minimum80_count']
        assert sum(int(r['candidate_votes']) for r in comp[:cutoff-1])==summary['previous_votes']
        assert 5*summary['previous_votes']<4*summary['candidate_total']<=5*summary['minimum80_votes']
        ballotseq=sorted(comp,key=lambda r:(-int(r['ballots']),r['county_code'],r['unit_name'].strip()))
        bc=0;bcutoff=next(i for i,r in enumerate(ballotseq,1) if 5*int(r['ballot_cumulative'])>=4*summary['ballots'])
        for i,r in enumerate(ballotseq,1):
            bc+=int(r['ballots']);assert int(r['ballot_rank'])==i and int(r['ballot_cumulative'])==bc
            assert Fraction(r['ballot_cumulative_weight_exact'])==Fraction(bc,summary['ballots'])
            assert (r['ballot_top15']=='True')==(i<=15)
            assert (r['ballot_minimum80']=='True')==(i<=bcutoff)
        assert bcutoff==summary['ballot_minimum80_count']
        results[name]=dict(raw_units=len(byunit),research_units=len(comp),all_categories=dict(totals),county_section_controls=16,statewide_controls=1)
    # Independent official 19-page LLDC historical PDF: all 510 raw 2022 rows,
    # including both Cranberry Isles occurrences and the county-code defect.
    pdf=(ROOT/'extracted/legislature-2022-governor-archive.txt').read_text()
    pat=re.compile(r'^([A-Z]{3})\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',re.M)
    pdfrows=collections.Counter((a,b,*map(int,v)) for a,b,*v in pat.findall(pdf))
    u=re.search(r'^\s+STATE UOCAVA\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s*$',pdf,re.M)
    assert u;pdfrows[('','STATE UOCAVA',*map(int,u.groups()))]+=1
    grouped=collections.defaultdict(list)
    for r in all_raw['governor-2022']:grouped[r['source_row_key']].append(r)
    source=collections.Counter((part[0]['county_code'],part[0]['unit_name'],*[int(x['votes']) for x in part]) for part in grouped.values())
    assert source==pdfrows
    results['independent_2022_pdf_raw_rows_exact']=sum(pdfrows.values())
    # Signed December 9 presidential certificate lists five ballot candidates;
    # it does not publish the 581 Others subtotal, which is controlled above.
    nara=(ROOT/'extracted/nara-2024-certification.txt').read_text()
    for value in [435652,5286,8967,377977,2912]:assert f'{value:,}' in nara
    govcert=(ROOT/'extracted/legislature-2022-certification.txt').read_text()
    for value in [12581,287304,376934]:assert f'{value:,}' in govcert
    # Visually transcribed and retained signed Union scans. Do not infer zeros
    # from the unfilled presidential declared-write-in lines in the scan.
    local={
      'senate-2024':{'Cherry, Jason S.':40,'Costello, David Allen':108,'King, Angus S. Jr.':818,'Kouzounas, Demi':692,'BLANK':27,'TBC':1685},
      'president-2024':{'Harris, Kamala D.':762,'Oliver, Chase':10,'Stein, Jill':16,'Trump, Donald J.':863,'West, Cornel':7,'TBC':1685},
      'governor-2022':{'Hunkler, Sam':31,'LePage, Paul R.':721,'Mills, Janet T.':686,'BLANK':12,'TBC':1450}}
    for name,values in local.items():
        union={r['candidate_or_category']:int(r['votes']) for r in all_raw[name] if r['county_code']=='KNO' and r['unit_name']=='Union'}
        assert all(union[k]==v for k,v in values.items())
    results['union_president_blank_discrepancy']={'signed_local_preliminary':19,'current_sos':27,'difference':8}
    # Registration text files contain disjoint seven-field district tuples,
    # not overlapping totals. Companion PDFs expose statewide party controls.
    registration=rows(ROOT/'registration-native-rows.csv')
    active2024={x['registration_key']:x for x in registration if x['as_of_date']=='2024-11-05' and x['status']=='active'}
    for unit in priority['all_unit_coverage']:
        assert unit['results_ward_precinct_ids']==[]
        for c in unit['registration_constituents']:
            raw=active2024[c['native_key']]
            assert c['ward_precinct']==raw['ward_precinct'] and c['source_line']==int(raw['source_line'])
            assert (ROOT/c['source_path']).exists()
    for year in [2024,2022]:
        for status in ['active','inactive']:
            subset=[x for x in registration if x['as_of_date'].startswith(str(year)) and x['status']==status]
            assert len(subset)==(741 if year==2024 else 743)
            assert len({x['registration_key'] for x in subset})==len(subset)
            n=f'registration-{year}-'+('pdf' if status=='active' else 'inactive-pdf')
            t=(ROOT/'extracted'/(n+'.txt')).read_text();line=next(x for x in t.splitlines() if x.startswith('State Totals:'))
            published=list(map(int,re.findall(r'\d+',line)))
            party=collections.Counter()
            for x in subset:
                p=json.loads(x['party_counts_json']);assert sum(p.values())==int(x['total']);party.update(p)
            assert list(party.values())+[sum(int(x['total']) for x in subset)]==published
            results[f'registration_{year}_{status}']=dict(rows=len(subset),total=published[-1],party_controls_exact=True)
    census=gzip.decompress((ROOT/'raw/census-county-codes.txt.gz').read_bytes()).decode()
    fips={x[3].removesuffix(' County'):x[1]+x[2] for x in csv.reader(io.StringIO(census))}
    assert len(fips)==16
    assert all(not r['county'] or fips[r['county']]==r['county_fips'] for r in ranked)
    # Independent actual partisanship worker, separate parser and downloads.
    evidence=json.loads((ROOT/'independent-reconciliation.json').read_text())
    assert evidence['result']['all512_keys_order_candidates_blank_tbc_source_rows_exact']
    assert evidence['result']['ordered_priority_sha256']==digest(keys)
    results['independent_actual_partisanship_worker']='passed; preserved reconciliation with source hash'
    vintage=json.loads((ROOT/'source-vintage-diff.json').read_text())
    assert len(vintage['senate']['all_cell_differences'])==15
    assert len(vintage['president']['all_cell_differences'])==18
    results['archived_vs_current_2024_cell_differences']={'senate':15,'president':18,'only_unit':'Alfred; plus York/state footers'}
    report=STATE/'turnout.md';broken=[]
    for target in re.findall(r'\]\(([^)]+)\)',report.read_text()):
        if target.startswith(('https:','http:','#')):continue
        resolved=report.parent/target.split('#')[0]
        # This validator emits its own final report after the assertions pass.
        if resolved.resolve()==ROOT/'validation.json':continue
        if not resolved.exists():broken.append(target)
    assert not broken,broken
    results['relative_report_links']='all exist'
    assets=json.loads((ROOT/'asset-manifest.json').read_text())
    for a in assets:
        b=(STATE/a['path']).read_bytes()
        assert len(b)==a['bytes'] and digest(b)==a['sha256'],a['path']
    expected_assets={str(p.relative_to(STATE)) for p in ROOT.rglob('*') if p.is_file() and p.name not in ['asset-manifest.json','validation.json']}
    expected_assets|={'turnout.md','data/county-turnout.csv'}
    assert {a['path'] for a in assets}==expected_assets
    results['owned_asset_hashes_verified']=len(assets)
    assert not list(ROOT.rglob('__pycache__'))
    assert all(p.stat().st_size<40*1024*1024 for p in ROOT.rglob('*') if p.is_file())
    (ROOT/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
    print('PASS: 512 Senate rows, every candidate/blank/ballot, all comparators, 164 exact keys, 510 independent 2022 PDF rows, registration, hashes and links')
if __name__=='__main__':main()
