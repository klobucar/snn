#!/usr/bin/env python3
"""Offline cross-report reconciliation and retained-evidence integrity checks."""

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def check_hash(path, expected):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == expected, f"Checksum mismatch: {path}"


turnout = read_csv(DATA / "county-turnout.csv")
baseline = read_csv(DATA / "county-baselines.csv")
senate = {
    row["fips"]: row
    for row in baseline
    if row["year"] == "2024" and row["contest"] == "senate"
}
governor = {
    row["fips"]: row
    for row in baseline
    if row["year"] == "2022" and row["contest"] == "governor"
}
fips = {row["county_fips"] for row in turnout}
assert len(turnout) == len(fips) == len(senate) == len(governor) == 83
assert fips == senate.keys() == governor.keys()

for row in turnout:
    county = senate[row["county_fips"]]
    for turnout_field, baseline_field in (
        ("senate_2024_d", "d_votes"),
        ("senate_2024_r", "r_votes"),
        ("senate_2024_other", "other_votes"),
        ("senate_2024_total", "contest_votes"),
    ):
        assert int(row[turnout_field]) == int(county[baseline_field]), row["county"]
    assert int(row["governor_2022_total"]) > 0
    assert int(row["governor_2022_total"]) == int(
        governor[row["county_fips"]]["contest_votes"]
    ), row["county"]

assert sum(int(row["senate_2024_total"]) for row in turnout) == 5_577_187
assert sum(int(row["governor_2022_total"]) for row in turnout) == 4_461_972
priority = [row for row in turnout if row["smallest_80pct_set"] == "1"]
assert len(priority) == 23
assert sum(int(row["senate_2024_total"]) for row in priority) == 4_484_963
assert sum(int(row["senate_2024_total"]) for row in priority[:-1]) * 5 < 5_577_187 * 4

scenarios = defaultdict(list)
for row in read_csv(DATA / "baselines/county-target-scenarios.csv"):
    scenarios[row["scenario"]].append(row)
for state in read_csv(DATA / "baselines/state-scenarios.csv"):
    rows = scenarios[state["scenario"]]
    assert len(rows) == 83 and {row["fips"] for row in rows} == fips
    expected = float(state["target_margin_pp"]) / 100 * float(state["major_party_votes"])
    actual = sum(float(row["target_net_d_minus_r_votes"]) for row in rows)
    assert math.isclose(actual, expected, abs_tol=1e-7), state["scenario"]

inventory = read_csv(DATA / "official-results-sources.csv")
counties = [row for row in inventory if row["scope"] == "county"]
assert len(counties) == 83 and {row["county_fips"] for row in counties} == fips
assert len(inventory) == 86

hash_count = 0
for entry in json.loads((DATA / "baselines/manifest.json").read_text()):
    check_hash(DATA / "baselines" / entry["file"], entry["saved_sha256"])
    hash_count += 1
for entry in json.loads((DATA / "turnout/evidence-manifest.json").read_text()):
    if "sha256" in entry and (DATA / "turnout" / entry["file"]).exists():
        check_hash(DATA / "turnout" / entry["file"], entry["sha256"])
        hash_count += 1
for line in (DATA / "results-sources/SHA256SUMS").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    check_hash(DATA / "results-sources" / name.lstrip("*"), digest)
    hash_count += 1

maps = DATA.parent / "maps"
map_rows = read_csv(maps / "manifest.csv")
assert len(map_rows) == 93
priority_fips = {row["county_fips"] for row in priority}
geo_coverage = defaultdict(set)
geo_counts = defaultdict(int)
for row in map_rows:
    asset = maps / row["local_path"]
    check_hash(asset, row["sha256"])
    hash_count += 1
    if row["format"] == "GeoJSON":
        year = row["local_path"].split("/")[0]
        features = json.loads(asset.read_text())["features"]
        assert len(features) == int(row["feature_count"])
        county_field = "COUNTYFIPS" if year == "2024" else "CountyFIPS"
        assert all(feature["properties"][county_field] == row["fips"][2:] for feature in features)
        geo_coverage[year].add(row["fips"])
        geo_counts[year] += len(features)
assert dict(geo_coverage) == {"2024": priority_fips, "2026": priority_fips}
assert dict(geo_counts) == {"2024": 3220, "2026": 2789}

print(
    f"Verified 83-county cross-report counts, 23 priority counties, "
    f"{len(scenarios)} statewide scenarios, 86 result-source rows, "
    f"46 county/vintage GeoJSONs, 93 map assets, "
    f"and {hash_count} retained-evidence/asset checksums."
)
