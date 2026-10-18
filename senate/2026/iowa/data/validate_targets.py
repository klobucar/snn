#!/usr/bin/env python3
"""Independently recompute historical scenario and selected-county arithmetic."""
from pathlib import Path
from collections import defaultdict
import csv, datetime, hashlib, json, math

ROOT = Path(__file__).resolve().parent
def rows(name):
    with (ROOT / name).open(newline='') as stream:
        return list(csv.DictReader(stream))
def near(left, right):
    assert math.isclose(float(left), float(right), rel_tol=2e-12, abs_tol=2e-6), (left, right)

baseline = {(r['contest'], r['county_fips']): r for r in rows('baselines/county-contests.csv')}
states = rows('baselines/state-scenarios.csv')
targets = rows('baselines/county-target-scenarios.csv')
selected = rows('baselines/selected-county-break-even.csv')
settings = {r['scenario_id']: r for r in json.loads((ROOT / 'baselines/scenario-settings.json').read_text())}
target_groups = defaultdict(list)
for row in targets:
    target_groups[row['scenario_id'], row['goal']].append(row)
selected_by = {(r['scenario_id'], r['goal'], r['county_fips']): r for r in selected}
assert len(states) == len(target_groups) == 36 and len(settings) == 12
assert len(targets) == len(selected) == len(selected_by) == 3_564
checked_selected = 0
for state in states:
    sid, goal = state['scenario_id'], state['goal']
    pref, volume = state['preference_contest'], state['volume_contest']
    assert settings[sid]['preference_contest'] == pref
    assert settings[sid]['allcandidate_volume_contest'] == volume
    inputs = {}
    county_rows = target_groups[sid, goal]
    assert len(county_rows) == len({r['county_fips'] for r in county_rows}) == 99
    for row in county_rows:
        fips = row['county_fips']; p = baseline[pref, fips]; v = baseline[volume, fips]
        d, r = int(p['d']), int(p['r']); pair_observed = d + r
        all_observed = int(p['candidate_writein_votes'])
        all_volume = int(v['candidate_writein_votes'])
        participation = pair_observed / all_observed
        pair = pair_observed if '__native-pair-' in sid else all_volume * participation
        share = d / pair_observed; net = pair * (2 * share - 1)
        inputs[fips] = all_volume, pair, share, net
        assert row['preference_contest'] == pref and row['allcandidate_volume_contest'] == volume
        near(row['all_candidate_volume'], all_volume); near(row['pair_volume'], pair)
        near(row['pair_participation'], participation); near(row['baseline_d_share'], share)
        near(row['baseline_pair_margin'], 2 * share - 1); near(row['baseline_net'], net)
        near(row['net_gain_per_1pp_d_share'], .02 * pair)
    a = sum(v[0] for v in inputs.values()); t = sum(v[1] for v in inputs.values())
    base = sum(v[3] for v in inputs.values())
    desired = {'tie': 0., 'D+1-pair-margin': .01 * t, 'D+1-allcandidate-margin': .01 * a}[goal]
    shift = (desired - base) / (2 * t)
    near(state['all_candidate_volume'], a); near(state['pair_volume'], t)
    near(state['pair_participation'], t / a); near(state['baseline_net'], base)
    near(state['baseline_pair_margin'], base / t)
    near(state['target_net'], desired); near(state['target_pair_margin'], desired / t)
    near(state['target_allcandidate_margin'], desired / a); near(state['unbounded_share_shift'], shift)
    def shifted_net(delta):
        return sum(pair * (2 * min(1., max(0., share + delta)) - 1) for _, pair, share, _ in inputs.values())
    low, high = -1., 1.
    for _ in range(90):
        middle = (low + high) / 2
        if shifted_net(middle) < desired:
            low = middle
        else:
            high = middle
    bounded = (low + high) / 2
    near(state['solved_share_shift'], bounded); near(state['achieved_net'], desired)
    clips = sum(not 0 <= share + shift <= 1 for _, _, share, _ in inputs.values())
    assert int(state['unbounded_clipped_count']) == clips
    assert state['status'] == ('bounded-feasible' if clips else 'unbounded-feasible')
    achieved = gains = 0.
    for row in county_rows:
        fips = row['county_fips']; all_volume, pair, share, net = inputs[fips]
        q = min(1., max(0., share + bounded)); target_net = pair * (2 * q - 1)
        for field, value in [('pair_weight', pair / t), ('allcandidate_weight', all_volume / a),
                             ('target_d_share', q), ('target_pair_margin', 2 * q - 1),
                             ('d_share_change_points', 100 * (q - share)),
                             ('margin_change_points', 200 * (q - share)),
                             ('target_net', target_net), ('net_gain', target_net - net),
                             ('state_pair_margin_contribution_points', 100 * target_net / t),
                             ('unbounded_target_share', share + shift)]:
            near(row[field], value)
        assert row['bound_applied'] == str(not 0 <= share + shift <= 1)
        choice = selected_by[sid, goal, fips]
        required = (desired - (base - net) + pair) / (2 * pair)
        final_den = a if goal == 'D+1-allcandidate-margin' else t
        near(choice['required_d_share'], required); near(choice['final_pair_votes'], t)
        near(choice['final_all_candidate_votes'], a); near(choice['final_denominator'], final_den)
        near(choice['fixed_net'], base - net); near(choice['selected_pair_pool'], pair)
        near(choice['target_net'], desired); near(choice['bounded_display_share'], min(1., max(0., required)))
        near(choice['achieved_net_at_boundary'], base - net + pair * (2 * min(1., max(0., required)) - 1))
        assert choice['selected'] == fips
        assert choice['status'] == ('already-secured' if required < 0 else 'impossible' if required > 1 else 'feasible')
        checked_selected += 1; achieved += target_net; gains += target_net - net
    near(achieved, desired); near(gains, desired - base)

source_candidates = {(r['contest'], r['county_fips'], r['candidate_or_metric_label']): r
                     for r in rows('baselines/canvass-candidate-method.csv')
                     if r['native_method'] == 'Total' and r['county_fips'] and r['metric'] == 'candidate_votes'
                     and r['party_header'] not in ('DEM', 'REP')}
other_rows = rows('baselines/scenario-other-candidates.csv')
other_totals = defaultdict(lambda: defaultdict(float))
seen_others = set()
for row in other_rows:
    sid, pref, fips = row['scenario_id'], row['preference_contest'], row['county_fips']
    label = row['native_candidate_label']; key = sid, fips, label
    assert key not in seen_others; seen_others.add(key)
    original = source_candidates[pref, fips, label]
    denominator = int(baseline[pref, fips]['candidate_writein_votes'])
    all_volume = int(baseline[settings[sid]['allcandidate_volume_contest'], fips]['candidate_writein_votes'])
    votes = int(original['votes']); fixed = all_volume * votes / denominator
    assert row['party_header'] == original['party_header']
    near(row['historical_candidate_votes'], votes); near(row['historical_candidate_generic_denominator'], denominator)
    near(row['scenario_allcandidate_volume'], all_volume); near(row['fixed_scenario_candidate_votes'], fixed)
    other_totals[sid][label] += fixed
for sid, setting in settings.items():
    expected = {(sid, fips, label) for (pref, fips, label) in source_candidates if pref == setting['preference_contest']}
    assert {k for k in seen_others if k[0] == sid} == expected
for state in states:
    pair = float(state['pair_volume']); net = float(state['target_net'])
    largest = max(other_totals[state['scenario_id']].values(), default=0.)
    near(state['scenario_d_votes'], (pair + net) / 2)
    near(state['scenario_r_votes'], (pair - net) / 2)
    near(state['largest_separate_other_votes'], largest)
    assert state['d_exceeds_all_separate_others'] == str((pair + net) / 2 > largest)

fixtures = json.loads((ROOT / 'baselines/live-remainder-examples.json').read_text())['examples']
assert len(fixtures) == 3
for example, margin, denominator in zip(fixtures, [0., .01, .01], [200., 200., 230.]):
    result = example['result']; desired = margin * denominator
    near(result['final_pair_votes'], 200); near(result['final_all_candidate_votes'], 230)
    near(result['final_denominator'], denominator); near(result['fixed_net'], -20)
    near(result['selected_pair_pool'], 100); near(result['target_net'], desired)
    near(result['required_d_share'], (desired + 20 + 100) / 200)
    assert result['status'] == 'feasible'

base = next(r for r in states if r['scenario_id'] == '2020-senate__native-pair-2020-senate' and r['goal'] == 'tie')
near(base['pair_volume'], 1_619_856); near(base['baseline_net'], -110_138)
result = {'status': 'pass', 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'state_scenarios': len(states), 'preference_volume_mixes': len(settings),
          'county_target_rows': len(targets), 'selected_county_requirements': checked_selected,
          'separate_other_candidate_rows': len(other_rows), 'synthetic_fixed_counted_remainder_cases': len(fixtures),
          'same_seat2020_pair': 1_619_856, 'same_seat2020_D_minus_R': -110_138,
          'same_seat2020_tie_D_share_pp': 110_138 / (2 * 1_619_856) * 100,
          'input_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
              'baselines/county-contests.csv', 'baselines/state-scenarios.csv',
              'baselines/county-target-scenarios.csv', 'baselines/selected-county-break-even.csv',
              'baselines/scenario-other-candidates.csv', 'baselines/live-remainder-examples.json')},
          'scope': 'Historical arithmetic and final-denominator examples only; generic marks remain distinct, no current candidate effects, remaining-vote estimate or calibrated forecast.'}
output = ROOT / 'coordinator-target-checks.json'
if output.exists():
    old = json.loads(output.read_text())
    if {k:v for k,v in old.items() if k != 'checked_utc'} == {k:v for k,v in result.items() if k != 'checked_utc'}:
        result['checked_utc'] = old['checked_utc']
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:v for k,v in result.items() if k != 'input_hashes'}, indent=2))
