#!/usr/bin/env python3
"""Read-only cross-check of the independent partisanship HD volume baseline.

Writes only turnout-owned audit files. Does not require the peer analysis to
rebuild turnout; use after that worker has published its local CSV.
"""
import collections
import csv
import datetime
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
STATE = ROOT.parent.parent


def main():
    source = STATE / 'data/county-baselines.csv'
    raw = source.read_bytes()
    rows = list(csv.DictReader(raw.decode().splitlines()))
    comparisons = []
    for year, contest, ours in [
        ('2024', 'U.S. President / Vice President', STATE / 'data/county-turnout.csv'),
        ('2022', 'U.S. Senator', ROOT / 'district-turnout-2022.csv'),
    ]:
        selected = [r for r in rows if r['election_year'] == year and r['contest'] == contest and r['stage'] == 'first_choices']
        assert len(selected) == (328 if year == '2024' else 205)
        totals = collections.Counter()
        for r in selected:
            totals[r['source_unit_id']] += int(r['votes'])
        ours_rows = list(csv.DictReader(ours.open()))
        assert len(totals) == len(ours_rows) == 41
        for r in ours_rows:
            hd = r['native_house_district']
            actual, expected = int(r['all_candidate_votes']), totals[hd]
            assert actual == expected, (year, hd, actual, expected)
            comparisons.append(dict(election_year=year, native_house_district=hd,
                                    turnout_votes=actual, partisanship_votes=expected, difference=actual - expected))
    with (ROOT / 'peer-hd-cross-check.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparisons[0]))
        writer.writeheader()
        writer.writerows(comparisons)
    metadata = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    compared_file='../county-baselines.csv', compared_sha256=hashlib.sha256(raw).hexdigest(),
                    comparisons=len(comparisons), differences=0,
                    scope='Same-election HD candidate-volume sums only; no cross-year district join')
    # The companion audit supplies scanner counts. Full-source counts are checked
    # here against our independently extracted official district turnout tables.
    gap_source = STATE / 'data/baselines/cvr-ballot-coverage-gaps.csv'
    gaps = list(csv.DictReader(gap_source.open()))
    units = {r['source_label']: r for r in csv.DictReader((ROOT / 'reporting-units-2022.csv').open())}
    assert len(gaps) == 6
    for r in gaps:
        ours = units[r['unit_name']]
        assert int(r['full_ballots']) == int(ours['ballots_cast'])
        assert int(r['missing_ballots']) == int(r['full_ballots']) - int(r['cvr_ballots'])
    assert sum(int(r['missing_ballots']) for r in gaps) == 250
    assert sum(int(r['missing_candidate_votes']) for r in gaps) == 237
    metadata['companion_cvr_gap_audit'] = dict(file='../baselines/cvr-ballot-coverage-gaps.csv',
                                              sha256=hashlib.sha256(gap_source.read_bytes()).hexdigest(),
                                              gap_units=6, missing_ballots=250, missing_candidate_votes=237,
                                              verification='Full-ballot cells independently match turnout HD PDFs; CVR values supplied by companion audit')
    (ROOT / 'peer-hd-cross-check.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('PASS: 82 same-election HD totals match; six companion CVR gap full-ballot counts match official turnout PDFs.')


if __name__ == '__main__':
    main()
