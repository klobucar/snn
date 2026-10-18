#!/usr/bin/env python3
"""Coordinator's read-only cross-assignment reconciliation; no geographic allocation."""
from pathlib import Path
from collections import defaultdict
from fractions import Fraction
import csv, datetime, gzip, hashlib, json

ROOT = Path(__file__).resolve().parents[1]
def rows(rel):
    with (ROOT / rel).open(newline='') as f: return list(csv.DictReader(f))
def sha(b): return hashlib.sha256(b).hexdigest()
turnout = rows('data/county-turnout.csv')
baseline = rows('data/county-baselines.csv')
candidates = rows('data/baselines/candidate-votes.csv')
controls = rows('data/baselines/state-controls.csv')
assert len(turnout) == 512 and len(baseline) == 2052
assert len({r['native_key'] for r in turnout}) == 512
assert len({r['source_row_id'] for r in baseline}) == 2052
groups = defaultdict(list)
for r in baseline: groups[r['source_id']].append(r)
assert {k: len(v) for k,v in groups.items()} == {'senate-2020':517,'governor-2022':510,'senate-2024':512,'president-2024':513}
assert {k: sum(int(r['contest_votes']) for r in v) for k,v in groups.items()} == {'senate-2020':819183,'governor-2022':676819,'senate-2024':821072,'president-2024':831375}
for r in baseline:
    assert int(r['d_votes']) + int(r['r_votes']) + int(r['other_votes']) == int(r['contest_votes'])
    assert int(r['contest_votes']) + int(r['blank']) == int(r['tbc'])
byrow = {r['source_row_id']:r for r in baseline}
seen = set(); sums = defaultdict(int)
for r in candidates:
    key = (r['source_row_id'], r['candidate_id']); assert key not in seen; seen.add(key)
    b = byrow[r['source_row_id']]
    assert r['native_key'] == b['native_key'] and r['source_row'] == b['source_row']
    assert int(r['votes']) == int(b[r['candidate_id'] + '_votes'])
    sums[(r['source_id'],r['candidate_id'])] += int(r['votes'])
for r in controls:
    v = sums[(r['source_id'],r['category'])] if r['category'] not in ('blank','tbc') else sum(int(b[r['category']]) for b in groups[r['source_id']])
    assert v == int(r['all_native_row_sum']) == int(r['cached_statewide_control']) and int(r['difference']) == 0
senate = {r['native_key']:r for r in groups['senate-2024']}
mapping = {'cherry_independent_2024':'cherry_votes','costello_democratic_2024':'costello_votes','king_independent_2024':'king_votes','kouzounas_republican_2024':'kouzounas_votes','blank_senate_2024':'blank','ballots_cast_2024':'tbc','senate_votes_2024':'contest_votes'}
comparisons = 0
for t in turnout:
    b = senate[t['native_key']]
    for left,right in mapping.items(): assert int(t[left]) == int(b[right]); comparisons += 1
    assert t['unit_name'] == b['native_unit_name'] and t['unit_name'].strip() == b['unit_name'] and t['county_code'] == b['native_county_code']
    assert t['county_fips'] == b['county_fips'] and t['source_rows'] == b['source_row']
    assert Fraction(t['weight_exact']) == Fraction(int(t['senate_votes_2024']),821072)
ranked = sorted(turnout,key=lambda r:(-int(r['senate_votes_2024']),r['county_code'],r['unit_name']))
assert [r['native_key'] for r in ranked] == [r['native_key'] for r in turnout]
assert [int(r['rank']) for r in turnout] == list(range(1,513))
assert sum(Fraction(r['weight_exact']) for r in turnout) == 1
assert sum(int(r['senate_votes_2024']) for r in turnout[:15]) == 215627
assert sum(int(r['senate_votes_2024']) for r in turnout[:163]) == 656778
assert sum(int(r['senate_votes_2024']) for r in turnout[:164]) == 658029
assert 5*656778 < 4*821072 <= 5*658029
assert turnout[163]['unit_name'] == 'Pownal' and int(turnout[163]['senate_votes_2024']) == 1251
priority = json.loads((ROOT/'data/turnout/priority-set.json').read_text())
keys = ''.join(r['native_key']+'\n' for r in turnout[:164]).encode()
assert keys == (ROOT/'data/turnout/priority-keys.txt').read_bytes() == (ROOT/'data/baselines/priority-keys.txt').read_bytes()
assert sha(keys) == priority['ordered_priority_keys_sha256'] == '086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'
assert [r['native_key'] for r in priority['priority']] == [r['native_key'] for r in turnout[:164]]
uocava = next(r for r in turnout[:164] if r['unit_name']=='STATE UOCAVA')
assert int(uocava['rank']) == 22 and int(uocava['senate_votes_2024']) == 6434
assert not uocava['county_fips'] and not uocava['county_code']
manifest = json.loads((ROOT/'data/turnout/manifest.json').read_text())
for key in ('senate-2024','president-2024','governor-2022'):
    source = next(r for r in manifest if r['source_id']==key)
    raw = gzip.decompress((ROOT/'data/turnout'/source['saved_path']).read_bytes())
    assert sha(raw) == source['original_sha256']
    assert {r['source_original_sha256'] for r in groups[key]} == {sha(raw)}
result = {'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'baseline_native_source_rows':2052,'candidate_cells':len(candidates),'state_controls':len(controls),
          'senate_units':512,'senate_numeric_comparisons':comparisons,'priority_units':164,
          'top15_votes':215627,'first163_votes':656778,'priority_votes':658029,'statewide_votes':821072,
          'priority_fraction':str(Fraction(658029,821072)),'priority_keys_sha256':sha(keys),
          'administrative_unit':'STATE UOCAVA remains county-unassigned and has no fabricated polygon',
          'geography':'native labels/rows; cross-contest and 2026 boundary equivalence not assumed',
          'input_hashes':{p:sha((ROOT/p).read_bytes()) for p in ['data/county-turnout.csv','data/county-baselines.csv','data/baselines/candidate-votes.csv','data/baselines/state-controls.csv','data/turnout/priority-keys.txt']}}
out = ROOT/'data/coordinator-baseline-reconciliation.json'
if out.exists():
    previous=json.loads(out.read_text())
    if {k:v for k,v in previous.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}: result['checked_utc']=previous['checked_utc']
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
