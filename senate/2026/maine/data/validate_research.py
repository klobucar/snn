#!/usr/bin/env python3
"""Coordinator integrated audit. Full source/map checks are required before publication."""
from pathlib import Path
import csv,datetime,hashlib,json,re,runpy,sys
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
for name in ('reconcile_baselines.py','validate_targets.py','review_vintages.py'):
    runpy.run_path(str(ROOT/'data'/name))
runpy.run_path(str(ROOT/'data/news/inspect_evidence.py'))
def load(rel):return json.loads((ROOT/rel).read_text())
counts={}
for rel in ('data/turnout/asset-manifest.json','data/baselines/asset-manifest.json'):
    entries=load(rel)
    assert len({e['path'] for e in entries})==len(entries)
    for e in entries:
        p=ROOT/e['path'];b=p.read_bytes()
        assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],e['path']
        assert len(b)<40_000_000
    counts[rel]=len(entries)
full='--baselines-only' not in sys.argv
if full:
    runpy.run_path(str(ROOT/'data/review_local_sources.py'))
    source_manifest=load('data/results-sources/asset-manifest.json')
    for entry in source_manifest['assets']:
        p=(ROOT/'data/results-sources'/entry['path']).resolve();b=p.read_bytes()
        assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'],entry['path']
        assert len(b)<40_000_000
    counts['data/results-sources/asset-manifest.json']=len(source_manifest['assets'])
    map_manifest=load('maps/asset-hashes.json')
    for rel,entry in map_manifest.items():
        p=ROOT/'maps'/rel;b=p.read_bytes()
        assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'],rel
        assert len(b)<40_000_000
    counts['maps/asset-hashes.json']=len(map_manifest)
    contract=load('data/turnout/priority-set.json')['all_unit_coverage']
    maps=load('maps/unit-inventory.json');sources=load('data/results-sources/native-unit-inventory.json')
    assert len(contract)==len(maps)==len(sources)==512
    assert [r['native_key'] for r in contract]==[r['native_key'] for r in maps]==[r['native_key'] for r in sources]
    for original,mapped,source in zip(contract,maps,sources):
        for field,value in original.items():assert mapped[field]==value,(original['native_key'],field)
        for field in ('native_key','native_name','county_code','rank','priority','senate_votes'):
            assert source[field]==original[field],(original['native_key'],field)
        assert source['current_boundary_equivalence']=='unverified'
        assert source['outstanding_votes'] is None and source['observed_count_update_cadence'] is None
    keys=(ROOT/'data/turnout/priority-keys.txt').read_text().splitlines()
    priorities=load('data/results-sources/priority-field-audit.json')
    assert [r['native_key'] for r in priorities]==keys==[r['native_key'] for r in maps if r['priority']]
    admin=maps[21];assert admin['native_name']=='STATE UOCAVA' and admin['map_scope']=='none'
    assert not admin['county_fips'] and not admin['matched_source_ids'] and not admin.get('geojson')
    assert not sources[21]['clerk_authority_keys']
    assert sum('municipal/township polygon reference' in r['classification'] for r in maps if r['priority'])==155
    assert sum('combined component reference' in r['classification'] for r in maps if r['priority'])==8
    csv_rows=list(csv.DictReader((ROOT/'data/official-results-sources.csv').open()))
    native_csv=[r for r in csv_rows if r['record_type']=='native historical research unit']
    assert len(csv_rows)==513 and [r['native_key'] for r in native_csv]==[r['native_key'] for r in contract]
    portland=next(r for r in sources if r['native_name']=='Portland')
    assert [r['source_row'] for r in portland['current_membership_mentions']]==list(range(384,396))
    assert next(r for r in native_csv if r['native_name']=='Portland')['current_voting_place_source_rows']=='|'.join(str(i) for i in range(384,396))
    assert len(load('data/results-sources/current-authority-inventory.json'))==560
    current=load('data/results-sources/current-voting-places.json')['rows'];assert len(current)==539
    assert len({(r['county_code'],r['municipality'],r['ward_precinct']) for r in current})==538
    assert {r['source_row'] for r in current if r['source_row'] in (418,437)}=={418,437}
    for rel,metadata in load('maps/external-evidence-references.json').items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==metadata['sha256'],rel
    for rel,metadata in load('data/results-sources/baseline-pin.json').items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==metadata['sha256'],rel
    source_validation=load('data/results-sources/validation.json');map_validation=load('maps/validation.json')
    assert source_validation['status']==map_validation['status']=='pass'
    assert source_validation['asset_manifest_sha256']==hashlib.sha256((ROOT/'data/results-sources/asset-manifest.json').read_bytes()).hexdigest()
    assert source_validation['native_units']==map_validation['all_native_identities']==512
    assert source_validation['priority']==map_validation['ordered_priority_entries']==164
    assert source_validation['asset_count']==len(source_manifest['assets'])
    assert map_validation['original_http_acquisitions_verified']==len(load('maps/acquisitions.json'))==203
    pdfs=load('maps/pdf-audit.json')
    assert len({r['path'] for r in pdfs.values() if r.get('page_count')})==20
    assert len({p['preview'] for r in pdfs.values() for p in r.get('pages',[])})==95
    assert load('data/results-sources/inspection-summary.json')['no_November_live_result_feed_established'] is True
    for p in ROOT.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:assert p.stat().st_size<40_000_000,p
links=0
documents=sorted(ROOT.rglob('*.md')) if full else [ROOT/p for p in ('turnout.md','county-partisanship.md','data/turnout/SCHEMA.md','data/baselines/SCHEMA.md')]
for p in documents:
    for dest in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        dest=dest.strip().strip('<>')
        if not dest or dest.startswith(('#','http:','https:','mailto:','data:')):continue
        assert (p.parent/unquote(dest.split('#')[0])).exists(),(str(p),dest);links+=1
assert links>=(1000 if full else 46),'Markdown checks must cover the actual report/schema links'
baseline=load('data/coordinator-baseline-reconciliation.json');targets=load('data/coordinator-target-checks.json')
result={'status':'pass','scope':'baselines_and_news_only','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'native_baseline_rows':baseline['baseline_native_source_rows'],'candidate_cells':baseline['candidate_cells'],'state_controls':baseline['state_controls'],
        'priority_units':164,'senate_all_units':512,'state_scenarios':targets['state_scenarios'],'unit_target_rows':targets['native_unit_target_rows'],
        'preference_scenarios':targets['preference_anchor_scenarios'],'artifact_hashes_checked':counts,'baseline_relative_links':links,
        'news_snapshots':load('data/news/inspection.json')['snapshots'],'source_and_map_integration':'pending; not a publication-ready audit'}
if full:
    result.pop('baseline_relative_links')
    result.update(scope='integrated_four_question_research_package',source_and_map_integration='pass; scenario research, not a live implementation or calibrated forecast',
        all_state_relative_links=links,official_native_rows=512,official_priority_audits=164,current_clerk_labels=560,current_voting_place_rows=539,
        current_unique_county_municipality_WP=538,map_priority_physical_references=163,map_administrative_exceptions=1,
        map_HTTP_captures=203,map_unique_PDFs=20,map_unique_page_previews=95,
        worker_source_assertions=source_validation['assertions'],local_transcribed_candidate_cells=load('data/coordinator-local-source-review.json')['candidate_baseline_cells'],
        authority_name_matching='complete printed names/components; Portland12-row and analogous-name regression checks passed',
        limitations='Current feeds/cadence/outstanding counts, legal map approval/crosswalks, local/RCV discrepancies and source-specific access gaps remain documented.')
output=ROOT/'data/coordinator-checks.json'
if output.exists():
    previous=json.loads(output.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=previous['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
