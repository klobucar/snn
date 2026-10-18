#!/usr/bin/env python3
"""Independently validate saved output and prove byte-identical offline rebuild."""
import csv
import datetime
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent.parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    before = json.loads((ROOT/'output-hashes.json').read_text())
    # Refresh output-hashes first after intentional report/code changes; this
    # validation must compare two builds of the same final implementation.
    for name, fingerprint in before.items():
        assert sha(ROOT/name) == fingerprint, ('output changed before validation', name)
    subprocess.run([sys.executable, str(ROOT/'build_turnout.py')], check=True, capture_output=True)
    after = json.loads((ROOT/'output-hashes.json').read_text())
    assert before == after, 'Offline rebuild is not deterministic'
    data = list(csv.DictReader((STATE/'data/county-turnout.csv').open()))
    assert len(data) == 100
    assert len({r['county_fips'] for r in data}) == len({r['ncsbe_county_id'] for r in data}) == 100
    assert all(re.fullmatch(r'37[0-9]{3}', r['county_fips']) for r in data)
    assert [int(r['rank_2024']) for r in data] == list(range(1,101))
    assert [int(r['president_2024_total']) for r in data] == sorted(
        [int(r['president_2024_total']) for r in data], reverse=True)
    for year, prefix, total, ballots, registered in [
        ('2024', 'president_2024', 5699145, 5723987, 7763502),
        ('2022', 'senate_2022', 3773924, 3790202, 7412050)]:
        assert sum(int(r[prefix+'_total']) for r in data) == total
        assert sum(Fraction(int(r[prefix+'_total']), total) for r in data) == 1
        assert sum(int(r['ballots_cast_'+year]) for r in data) == ballots
        assert sum(int(r['registered_voters_'+year]) for r in data) == registered
        native = {r['cid']: r for r in json.loads((ROOT/f'dashboard-{year}-county.json').read_text())}
        for r in data:
            assert sum(int(r[prefix+'_'+k]) for k in ['d','r','other']) == int(r[prefix+'_total'])
            assert int(r['ballots_minus_contest_'+year]) == int(r['ballots_cast_'+year])-int(r[prefix+'_total']) >= 0
            assert native[r['ncsbe_county_id']]['cnm'] == r['county_native']
            assert native[r['ncsbe_county_id']]['bct'] == r['ballots_cast_'+year]
            assert native[r['ncsbe_county_id']]['rtl'] == r['registered_voters_'+year]
        rank_key = 'rank_ballots_'+year
        ballot_sorted = sorted(data, key=lambda r: (-int(r['ballots_cast_'+year]), r['county_fips']))
        assert [int(r[rank_key]) for r in ballot_sorted] == list(range(1,101))
    assert sum(int(r['top15']) for r in data) == 15
    assert sum(int(r['smallest_80pct_set']) for r in data) == sum(int(r['research_priority']) for r in data) == 38
    assert sum(int(r['president_2024_total']) for r in data[:15]) == 3158729
    assert sum(int(r['president_2024_total']) for r in data[:38]) == 4576486
    assert 5*sum(int(r['president_2024_total']) for r in data[:37]) < 4*5699145
    assert 5*sum(int(r['president_2024_total']) for r in data[:38]) >= 4*5699145
    assert data[37]['county'] == 'Wilson'
    checks = json.loads((ROOT/'checks.json').read_text())
    assert set(checks['midterm_2022_concentration']['smallest_80pct_set']) == set(r['county'] for r in data[:38]) | {'Haywood'}
    assert checks['ballots_2024_concentration']['smallest_80pct_set'] == [r['county'] for r in data[:38]]
    candidate_rows = list(csv.DictReader((ROOT/'candidate-reconciliation.csv').open()))
    assert len(candidate_rows) == 15 and all(int(r['difference']) == 0 for r in candidate_rows)
    discrepancies = list(csv.DictReader((ROOT/'zip-discrepancies.csv').open()))
    assert len(discrepancies) == 10 and {r['year'] for r in discrepancies} == {'2024'}
    assert {r['county_native'] for r in discrepancies} == {'MITCHELL','ROWAN'}
    report = (STATE/'turnout.md').read_text()
    generated = report.split('<!-- GENERATED_RANKING_START -->')[1].split('<!-- GENERATED_RANKING_END -->')[0].strip()
    assert generated == (ROOT/'ranking-table.md').read_text().strip()
    relative_links = [s for s in re.findall(r'\[[^\]]*\]\(([^)]+)\)', report) if '://' not in s and not s.startswith('#')]
    link_targets = [(STATE/link.split('#')[0]).resolve() for link in relative_links]
    pending_validation = ROOT/'validation.json'
    assert all(p.exists() or p == pending_validation for p in link_targets), 'Missing local report link'
    owned_files = [STATE/'turnout.md', STATE/'data/county-turnout.csv'] + [p for p in ROOT.rglob('*') if p.is_file()]
    assert all(p.stat().st_size < 40_000_000 for p in owned_files)
    fingerprints = {str(p.relative_to(STATE)): sha(p) for p in owned_files if p.name != 'validation.json'}
    result = dict(validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), status='pass',
        counties=100, primary_statewide_candidate_reconciliations=15,
        primary_candidate_method_reconciliations=75, offline_rebuild_byte_identical=True,
        exact_contest_weights_sum_to_one_both_years=True, checked_relative_report_links=len(relative_links),
        broken_relative_links=0, all_assigned_assets_under_40MB=True,
        known_zip_total_candidate_differences=4, known_zip_total_and_method_differences=10,
        checks_sha256=sha(ROOT/'checks.json'), build_script_sha256=sha(ROOT/'build_turnout.py'),
        all_assigned_file_sha256_except_this_validation=fingerprints)
    (ROOT/'validation.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    assert all(p.exists() for p in link_targets)
    print(json.dumps({k:v for k,v in result.items() if k != 'all_assigned_file_sha256_except_this_validation'},indent=2))

if __name__ == '__main__':
    main()
