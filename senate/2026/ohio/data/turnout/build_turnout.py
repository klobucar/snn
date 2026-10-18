#!/usr/bin/env python3
"""Deterministically rebuild Ohio turnout products from preserved primary XLSX.

No network or third-party Python dependencies. All arithmetic uses integers or
exact Fractions; decimal percentages are display-only. Native zero-filled
write-in precinct cells are retained as export values, never observed votes.
"""
import argparse
import csv
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import io
import json
from pathlib import Path
from xlsx_rows import sheets

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent.parent
RAW = ROOT / "raw"
CONFIG = {
    2024: {"date": "2024-11-05", "summary": "2024-summary-archive.xlsx",
           "precinct": "2024-statewide-races-precint-level.xlsx",
           "turnout_county": "2024-turnout-by-county.xlsx",
           "turnout_precinct": "2024-turnout-by-precinct.xlsx",
           "contests": {"senate": (list("AA AB AC AD AE AF AG".split()), list("AC AD AE AF AG AH AI".split())),
                        "president": (list("G H I J K L M N O P Q R S T".split()), list("I J K L M N O P Q R S T U V".split()))}},
    2022: {"date": "2022-11-08", "summary": "2022-statewide-races-summary.xlsx",
           "precinct": "2022-statewide-races-by-precinct.xlsx",
           "turnout_county": "2022-voter-turnout-summary.xlsx",
           "turnout_precinct": "2022-voter-turnout-by-precinct.xlsx",
           "contests": {"senate": (list("AB AC AD AE AF AG AH".split()), list("AD AE AF AG AH AI AJ".split()))}},
}

def js(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()

def csv_bytes(rows):
    rows = list(rows)
    assert rows
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()

def load_master(filename, columns):
    return dict(next(sheets(RAW / filename, names={"Master"}, columns=set(columns)))[1])

def load_fips():
    result = {}
    for r in csv.DictReader(io.StringIO((RAW / "national_county2020.txt").read_text()), delimiter="|"):
        if r["STATE"] == "OH":
            result[r["COUNTYNAME"].removesuffix(" County")] = r["STATEFP"] + r["COUNTYFP"]
    assert len(result) == 88 and len(set(result.values())) == 88
    return result

def pct(n, d):
    return f"{100*n/d:.9f}"

def ranking(values):
    ordered = sorted(values, key=lambda r: (-r["votes"], r["county_fips"]))
    total = sum(r["votes"] for r in ordered)
    cumulative = 0
    for rank, r in enumerate(ordered, 1):
        cumulative += r["votes"]
        r.update(rank=rank, cumulative_votes=cumulative, state_share_percent=pct(r["votes"], total),
                 cumulative_share_percent=pct(cumulative, total))
    n80 = next(r["rank"] for r in ordered if 5*r["cumulative_votes"] >= 4*total)
    return {"statewide_denominator": total, "ordered_county_keys": [r["county_fips"] for r in ordered],
            "top15_votes": ordered[14]["cumulative_votes"],
            "top15_share_percent": ordered[14]["cumulative_share_percent"],
            "minimum80_count": n80, "minimum80_votes": ordered[n80-1]["cumulative_votes"],
            "minimum80_share_percent": ordered[n80-1]["cumulative_share_percent"],
            "previous_votes": ordered[n80-2]["cumulative_votes"],
            "previous_share_percent": ordered[n80-2]["cumulative_share_percent"],
            "minimum80_county_keys": [r["county_fips"] for r in ordered[:n80]], "rows": ordered}

def build():
    fips = load_fips()
    products = {}
    candidate_rows, state_checks, candidate_checks, stats_checks = [], [], [], []
    catalog, county_stats, inventories, summaries, unit_stats_by_year = {}, {}, {}, {}, {}
    for year, cfg in CONFIG.items():
        summary_cols = list("A B C D E F".split())
        precinct_cols = list("A B C D E F G H".split())
        for scols, pcols in cfg["contests"].values():
            summary_cols += scols
            precinct_cols += pcols
        summary = load_master(cfg["summary"], summary_cols)
        precinct = load_master(cfg["precinct"], precinct_cols)
        counties = {r["A"]: (i, r) for i, r in summary.items() if r.get("A") in fips}
        assert set(counties) == set(fips)
        units = [(i, r) for i, r in precinct.items() if r.get("A") in fips]
        assert len({(r["A"], r["C"]) for _, r in units}) == len(units)
        assert {r["A"] for _, r in units} == set(fips)
        assert all(isinstance(r["C"], str) and r["C"] for _, r in units)
        summaries[year] = counties
        inventories[year] = defaultdict(list)
        county_stats[year] = {}
        unit_stats_by_year[year] = {}
        aggregate = defaultdict(Counter)
        unit_candidates, unit_statistics = [], []
        # Keep every native source row exactly once, including any administrative unit.
        # These statewide files name every row as a precinct; no inferred method split.
        for i, r in units:
            county = r["A"]
            unit_key = f"{cfg['date']}|{fips[county]}|{r['C']}"
            identity = {"unit_key": unit_key, "precinct_code_native": r["C"],
                        "precinct_name_native": r["B"], "source_row": i}
            inventories[year][county].append(identity)
            stat = {"election_date": cfg["date"], "county_native_id": county,
                    "county_fips": fips[county], **identity,
                    "registered_voters": r["F"], "ballots_counted": r["G"],
                    "region_native": r["D"], "media_market_native": r["E"],
                    "voting_method": "", "undervotes": "", "overvotes": "",
                    "source_status": "official_canvass;method_under_over_not_published",
                    "source_path": f"raw/{cfg['precinct']}", "source_sheet": "Master"}
            assert all(isinstance(stat[k], int) and stat[k] >= 0 for k in ["registered_voters", "ballots_counted"])
            unit_statistics.append(stat)
            unit_stats_by_year[year][unit_key] = stat
            for col in precinct_cols:
                if isinstance(r.get(col), int):
                    aggregate[county][col] += r[col]
            for contest, (scols, pcols) in cfg["contests"].items():
                for scol, pcol in zip(scols, pcols):
                    native_label = summary[2][scol]
                    assert precinct[2][pcol] == native_label
                    wi = "(WI)" in native_label
                    value = r[pcol]
                    assert isinstance(value, int) and value >= 0
                    if wi:
                        assert value == 0
                    unit_candidates.append({"election_date": cfg["date"], "contest_key": contest,
                        "county_fips": fips[county], "unit_key": unit_key,
                        "candidate_native_label": native_label, "candidate_native_column": pcol,
                        "native_export_value": value, "votes_observed": "" if wi else value,
                        "value_status": "unavailable_writein_placeholder" if wi else "observed_official_canvass",
                        "voting_method": "", "source_row": i})
        products[f"reporting-units-{year}.csv.gz"] = gzip.compress(csv_bytes(unit_statistics), mtime=0)
        products[f"precinct-candidates-{year}.csv.gz"] = gzip.compress(csv_bytes(unit_candidates), mtime=0)
        # Separate turnout workbooks are independently published controls, not extra votes.
        turnout_c = next(sheets(RAW / cfg["turnout_county"]))[1]
        turnout_p = next(sheets(RAW / cfg["turnout_precinct"]))[1]
        turnout_c = {r["A"]: (i, r) for i, r in turnout_c if r.get("A") in fips}
        turnout_p = {(r["A"], r["C"]): (i, r) for i, r in turnout_p if r.get("A") in fips}
        assert set(turnout_c) == set(fips)
        assert set(turnout_p) == {(r["A"], r["C"]) for _, r in units}
        for i, r in units:
            tp = turnout_p[(r["A"], r["C"])][1]
            assert all(r[k] == tp[k] for k in ["A", "B", "C", "F", "G"])
        for county, (i, r) in counties.items():
            county_stats[year][county] = {"registered_voters": r["D"], "ballots_counted": r["E"]}
            for metric, scol, pcol in [("registered_voters", "D", "F"), ("ballots_counted", "E", "G")]:
                tc = turnout_c[county][1][scol]
                difference = aggregate[county][pcol] - r[scol]
                assert difference == 0 and tc == r[scol]
                stats_checks.append({"year": year, "county_fips": fips[county], "county_native_id": county,
                    "metric": metric, "summary_value": r[scol], "precinct_sum": aggregate[county][pcol],
                    "precinct_minus_summary": difference, "turnout_workbook_value": tc,
                    "turnout_minus_summary": tc-r[scol]})
            for contest, (scols, pcols) in cfg["contests"].items():
                for scol, pcol in zip(scols, pcols):
                    label = summary[2][scol]
                    wi = "(WI)" in label
                    count = r[scol]
                    assert isinstance(count, int) and count >= 0
                    candidate_rows.append({"election_date": cfg["date"], "contest_key": contest,
                        "contest_native_label": "U.S. Senator" if contest == "senate" else "President and Vice President",
                        "county_native_id": county, "county_fips": fips[county],
                        "candidate_native_label": label, "candidate_native_column": scol,
                        "write_in": wi, "votes": count, "source_path": f"raw/{cfg['summary']}",
                        "source_sheet": "Master", "source_row": i, "source_status": "official_canvass_all_candidates"})
                    pcount = aggregate[county][pcol]
                    if not wi:
                        assert pcount == count, (year, county, label, pcount, count)
                    candidate_checks.append({"year": year, "contest_key": contest,
                        "county_fips": fips[county], "county_native_id": county,
                        "candidate_native_label": label, "summary_votes": count,
                        "precinct_native_export_sum": pcount, "precinct_observed_sum": "" if wi else pcount,
                        "native_export_minus_summary": pcount-count,
                        "difference_status": "documented_writeins_not_published_at_precinct" if wi else "exact_match"})
        for metric, scol, pcol in [("registered_voters", "D", "F"), ("ballots_counted", "E", "G")]:
            assert sum(r[scol] for _, r in counties.values()) == summary[3][scol] == precinct[3][pcol]
        catalog[year] = {"election_date": cfg["date"], "election_native_title": summary[1]["A"],
            "election_numeric_id": None, "county_native_id_semantics": "County Name field; no numeric county ID in these workbooks",
            "precinct_native_id_semantics": "Precinct Code within County Name and election vintage",
            "source_summary": f"raw/{cfg['summary']}", "source_precinct": f"raw/{cfg['precinct']}",
            "source_turnout_county": f"raw/{cfg['turnout_county']}",
            "source_turnout_precinct": f"raw/{cfg['turnout_precinct']}",
            "reporting_unit_count": len(units), "county_count": 88, "contests": {}}
        for contest, (scols, pcols) in cfg["contests"].items():
            candidates = []
            for scol, pcol in zip(scols, pcols):
                label = summary[2][scol]
                ssum = sum(r[scol] for _, r in counties.values())
                psum = sum(aggregate[c][pcol] for c in counties)
                assert ssum == summary[3][scol]
                candidates.append({"candidate_native_label": label, "summary_column": scol,
                                   "precinct_column": pcol, "write_in": "(WI)" in label,
                                   "certified_statewide_votes": summary[3][scol]})
                state_checks.append({"year": year, "contest_key": contest, "candidate_native_label": label,
                    "county_sum": ssum, "certified_statewide_votes": summary[3][scol],
                    "county_minus_state": ssum-summary[3][scol], "precinct_export_sum": psum,
                    "precinct_export_minus_state": psum-summary[3][scol],
                    "precinct_difference_status": "documented_unavailable_writeins" if "(WI)" in label else "exact_match"})
            catalog[year]["contests"][contest] = {"contest_native_label": "U.S. Senator" if contest == "senate" else "President and Vice President",
                "contest_numeric_id": None, "candidate_numeric_ids": None, "candidates": candidates,
                "all_candidate_votes": sum(c["certified_statewide_votes"] for c in candidates),
                "writein_votes_not_geolocated_to_precinct": sum(c["certified_statewide_votes"] for c in candidates if c["write_in"])}
    products["candidate-catalog.json"] = js(catalog)
    products["county-candidate-votes.csv"] = csv_bytes(candidate_rows)
    products["state-candidate-reconciliation.csv"] = csv_bytes(state_checks)
    products["county-precinct-candidate-reconciliation.csv"] = csv_bytes(candidate_checks)
    products["county-statistics-reconciliation.csv"] = csv_bytes(stats_checks)
    county_counts = defaultdict(Counter)
    for r in candidate_rows:
        county_counts[r["county_native_id"]][f"{r['election_date'][:4]}_{r['contest_key']}"] += r["votes"]
    ranks = {}
    for metric, kind in [("2024_senate", "all_candidate_contest_votes"), ("2024_president", "all_candidate_contest_votes"),
                         ("2022_senate", "all_candidate_contest_votes"), ("2024_ballots", "ballots_counted"), ("2022_ballots", "ballots_counted")]:
        year = int(metric[:4])
        ranks[metric] = ranking([{"county_native_id": c, "county_fips": fips[c],
            "votes": county_stats[year][c]["ballots_counted"] if "ballots" in metric else county_counts[c][metric]} for c in fips])
        ranks[metric]["denominator_type"] = kind
    primary = ranks["2024_senate"]
    priority_keys = primary["minimum80_county_keys"]
    rows = []
    rank_lookups = {m: {r["county_native_id"]: r["rank"] for r in v["rows"]} for m, v in ranks.items()}
    for r in primary["rows"]:
        c = r["county_native_id"]
        total = r["votes"]
        row = {"rank_2024_senate": r["rank"], "county": c, "county_fips": fips[c], "county_native_id": c,
               "senate_2024_votes": total, "senate_2024_state_share_fraction": f"{total}/{primary['statewide_denominator']}",
               "senate_2024_state_share_percent": r["state_share_percent"],
               "senate_2024_cumulative_votes": r["cumulative_votes"],
               "senate_2024_cumulative_share_percent": r["cumulative_share_percent"],
               "in_top15": int(r["rank"] <= 15), "in_minimum80": int(fips[c] in priority_keys),
               "president_2024_votes": county_counts[c]["2024_president"], "rank_2024_president": rank_lookups["2024_president"][c],
               "senate_2022_votes": county_counts[c]["2022_senate"], "rank_2022_senate": rank_lookups["2022_senate"][c]}
        for year in CONFIG:
            row.update({f"ballots_counted_{year}": county_stats[year][c]["ballots_counted"],
                        f"registered_voters_{year}": county_stats[year][c]["registered_voters"],
                        f"rank_{year}_ballots": rank_lookups[f"{year}_ballots"][c],
                        f"native_reporting_units_{year}": len(inventories[year][c]),
                        f"senate_{year}_writein_votes": sum(q["votes"] for q in candidate_rows if q["county_native_id"] == c and q["election_date"].startswith(str(year)) and q["contest_key"] == "senate" and q["write_in"]),
                        f"senate_{year}_ballots_minus_contest_votes": county_stats[year][c]["ballots_counted"] - county_counts[c][f"{year}_senate"],
                        f"voting_method_{year}": "", f"undervotes_{year}": "", f"overvotes_{year}": "",
                        f"source_summary_{year}": f"data/turnout/raw/{CONFIG[year]['summary']}"})
        row["source_status"] = "official_canvass_all_candidates;method_under_over_unavailable"
        rows.append(row)
    products["../county-turnout.csv"] = csv_bytes(rows)
    products["ranking-comparisons.json"] = js(ranks)
    vintages = {"warning": "Identifier/name comparisons only; neither a geometry crosswalk nor proof of unchanged boundaries or 2026 approval.", "counties": []}
    for c in sorted(fips, key=fips.get):
        old = {r["precinct_code_native"]: r["precinct_name_native"] for r in inventories[2022][c]}
        new = {r["precinct_code_native"]: r["precinct_name_native"] for r in inventories[2024][c]}
        vintages["counties"].append({"county_fips": fips[c], "county_native_id": c,
            "codes_only_2022": sorted(old.keys()-new.keys()), "codes_only_2024": sorted(new.keys()-old.keys()),
            "shared_codes": len(old.keys() & new.keys()),
            "shared_codes_changed_names": [{"precinct_code_native": k, "name_2022": old[k], "name_2024": new[k]} for k in sorted(old.keys() & new.keys()) if old[k] != new[k]]})
    products["reporting-unit-vintages.json"] = js(vintages)
    priority = {"schema_version": 1, "state": "Ohio", "state_fips": "39", "target_election": "2026-11-03 special U.S. Senate; unexpired term ending 2029-01-03",
        "baseline_election": "2024-11-05 general", "baseline_contest_native_label": "U.S. Senator",
        "denominator": "All seven certified candidates, including four named write-ins, across all 88 counties",
        "statewide_votes": primary["statewide_denominator"], "top15_votes": primary["top15_votes"],
        "top15_share_percent": primary["top15_share_percent"], "minimum80_count": primary["minimum80_count"],
        "minimum80_votes": primary["minimum80_votes"], "minimum80_share_percent": primary["minimum80_share_percent"],
        "previous_votes": primary["previous_votes"], "previous_share_percent": primary["previous_share_percent"],
        "integer_threshold_test": "5*cumulative_votes >= 4*statewide_votes; previous prefix fails",
        "sort": "descending Senate all-candidate votes, then ascending FIPS for a tie",
        "ordered_county_keys_all88": primary["ordered_county_keys"],
        "ordered_priority_county_keys": priority_keys,
        "source_manifest": "source-manifest.json", "source_summary": "raw/2024-summary-archive.xlsx",
        "source_precinct": "raw/2024-statewide-races-precint-level.xlsx", "source_sheet": "Master",
        "candidate_catalog": "candidate-catalog.json", "county_candidate_extract": "county-candidate-votes.csv",
        "scope": "All88 counties retained below. Priority counties are the union of top15 and smallest80%, which here equals the32-county80% set.",
        "unit_warning": "Native county IDs are the published County Name strings; numeric county/election/contest/candidate IDs are not published in these exports. Precinct codes require county and election vintage. No write-in residual is assigned to a fabricated precinct. Do not equate names or codes across years with approved boundaries.",
        "county_records": []}
    for row in rows:
        c = row["county"]
        priority["county_records"].append({"rank": row["rank_2024_senate"], "county_fips": fips[c],
            "county_native_id": c, "native_numeric_county_id": None, "in_priority": bool(row["in_minimum80"]),
            "senate_2024_votes": row["senate_2024_votes"], "summary_source_row_2024": summaries[2024][c][0],
            "summary_source_row_2022": summaries[2022][c][0],
            "writein_votes_not_precinct_allocated": {str(y): row[f"senate_{y}_writein_votes"] for y in CONFIG},
            "reporting_units": {str(y): {"source_path": f"raw/{CONFIG[y]['precinct']}", "source_sheet": "Master",
                "normalized_path": f"reporting-units-{y}.csv.gz", "units": inventories[y][c]} for y in CONFIG}})
    products["priority-set.json"] = js(priority)
    products["../../turnout.md"] = report(rows, ranks, catalog).encode()
    return products

def report(rows, ranks, catalog):
    p = ranks["2024_senate"]
    names = [r["county"] for r in rows if r["in_minimum80"]]
    lines = ["# Ohio turnout geography for the 2026 Senate special election", "",
        "Research local date: **2026-10-17 (America/Chicago)**; source retrievals: **2026-10-18 UTC**. The baseline is the **November 5, 2024 general-election U.S. Senator contest**, all seven certified candidates. All 88 counties remain in every statewide denominator.", "",
        f"The **top 15 supply {p['top15_votes']:,} / {p['statewide_denominator']:,} votes ({float(p['top15_share_percent']):.6f}%)**. The exact smallest set reaching 80% is **{p['minimum80_count']} counties, {p['minimum80_votes']:,} votes ({float(p['minimum80_share_percent']):.6f}%)**. The first 31 supply {p['previous_votes']:,} ({float(p['previous_share_percent']):.6f}%), below the threshold. The integer tests are `5*4,581,738 >= 4*5,704,620` and `5*4,542,798 < 4*5,704,620`. Descending volume maximizes coverage for each county count; therefore no smaller county set can reach 80%.", "",
        "The ordered 80% geography is: **" + ", ".join(names) + "**. The top-15/80% union is this same 32-county set. [priority-set.json](data/turnout/priority-set.json) retains the ordered FIPS keys, all 88 county records, native unit codes and names, source rows and source paths for both vintages.", "",
        "## Baseline choice and primary evidence", "",
        "[Ohio Directive 2025-54](https://www.ohiosos.gov/assets/directive-2025-54-writ-of-special-election-for-united-states-senate-election.pdf), issued November 13, 2025 and checked October 17, 2026, specifies the November 3, 2026 special election for the unexpired term ending January 3, 2029. **2022 Senate is the recent midterm and same-seat comparator**. The 2024 Senate contest concerns Ohio's other seat and different candidates. Ohio had no 2020 U.S. Senate election; no such baseline is created.", "",
        "The state certified the [2024 general election on December 2, 2024](https://www.ohiosos.gov/office/media-center/categories/press-releases/2024-12-02) and the [2022 general election on December 9, 2022](https://www.ohiosos.gov/office/media-center/categories/press-releases/2022-12-09). Original official-canvass workbooks were recovered from archived Ohio SOS URLs, not transcribed from a third-party result table:", "",
        "- [2024 county summary, archived 2024-12-07](https://web.archive.org/web/20241207004035if_/https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-race-summary.xlsx): [retained XLSX](data/turnout/raw/2024-summary-archive.xlsx). `Master!AA:AG` is Senate, `G:T` is president; county rows 5-92, statewide controls row 3.",
        "- [2024 precinct original, archived 2024-12-22](https://web.archive.org/web/20241222221124if_/https://www.ohiosos.gov/globalassets/elections/2024/gen/official/statewide-races-precint-level.xlsx): [retained XLSX](data/turnout/raw/2024-statewide-races-precint-level.xlsx). The source filename really spells `precint`. `Master!AC:AI` is Senate, `I:V` is president, rows 5-8882 are 8,878 reporting units.",
        "- [2022 county summary, archived 2022-12-29](https://web.archive.org/web/20221229143511if_/https://www.ohiosos.gov/globalassets/elections/2022/gen/statewide-races-summary.xlsx): [retained XLSX](data/turnout/raw/2022-statewide-races-summary.xlsx). `Master!AB:AH` is Senate, county rows 5-92, statewide controls row 3.",
        "- [2022 precinct original, archived 2025-03-12](https://web.archive.org/web/20250312114330if_/https://www.ohiosos.gov/globalassets/elections/2022/gen/statewide-races-by-precinct.xlsx): [retained XLSX](data/turnout/raw/2022-statewide-races-by-precinct.xlsx). `Master!AD:AJ` is Senate, rows 5-8937 are 8,933 reporting units.", "",
        "The separate official county and precinct turnout workbooks for each year were also downloaded and checked against every corresponding county and native precinct code/name, registration and ballot count. Their archive timestamps, URLs, HTTP status/headers, retrieval UTC and original/stored SHA-256 hashes are in [source-manifest.json](data/turnout/source-manifest.json). Source titles say Official Canvass. Archive capture dates are not election dates or certification dates. Legacy state archive URLs now redirect to the new data portal in browsing; direct terminal requests returned maintenance/403 HTML. Those failures and the failed correctly spelled precinct URL are retained and excluded from arithmetic. The civic map page was used only to discover a URL; none of its counts enter a baseline.", "",
        "[Census's 2020 county code reference](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt), [retained locally](data/turnout/raw/national_county2020.txt), provides all 88 five-digit county FIPS. Source-native county IDs are the `County Name` strings; these workbooks publish no numeric county, election, contest or candidate ID. Native candidate identifiers are the exact header labels plus workbook/sheet/column. These absences are explicit nulls in the [candidate catalog](data/turnout/candidate-catalog.json), not invented numeric IDs.", "",
        "## Candidate universe and reconciliation", "",
        "All published county candidate cells sum exactly to each source's certified statewide row. Non-write-in precinct cells sum exactly to each county and state candidate control. The separate Ohio partisanship worker independently verified the 2024 Senate county values against the official `U.S. Congress` side sheet and all seven statewide values against the [House Clerk 2024 publication](https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf). The turnout validator also checks all seven 2024 and all seven 2022 Senate candidates against the independently downloaded [House Clerk 2022 publication](https://clerk.house.gov/member_info/electionInfo/2022/statistics2022.pdf); see [14 primary Senate controls](data/turnout/house-clerk-senate-reconciliation.csv). Those primary PDFs, their retrieval metadata and text extractions are retained read-only under `data/baselines/`. The [county candidate extract](data/turnout/county-candidate-votes.csv), [state candidate checks](data/turnout/state-candidate-reconciliation.csv) and [county/precinct checks](data/turnout/county-precinct-candidate-reconciliation.csv) retain every difference.", "",
        "| Election/contest | Candidate native label | Certified votes |", "| --- | --- | ---: |"]
    for year in CONFIG:
        for contest, info in catalog[year]["contests"].items():
            for c in info["candidates"]:
                lines.append(f"| {year} {contest} | {c['candidate_native_label']} | {c['certified_statewide_votes']:,} |")
    lines += ["", "Both precinct workbooks explicitly state that write-in results are unavailable at precinct level and direct readers to the summary workbook. The zeroes in those precinct candidate columns are placeholders, preserved in `native_export_value` while `votes_observed` is blank. They omit **640** 2024 Senate votes, **2,771** 2024 presidential votes and **1,739** 2022 Senate votes. County write-ins remain in the ranking and in statewide arithmetic; the residual is never assigned to an invented administrative unit. The county summary is selected because it preserves the full certified candidate universe. No discrepancy is forced to zero.", "",
        "These are ordinary official county/precinct canvass exports, not a precinct-sorted model, a boundary allocation, or a 2026 live feed. The entire workbooks are retained, including all other contests and source sheets. Normalized compressed precinct candidate extracts preserve the selected contest cells, their native columns/rows and availability status.", "",
        "## Denominators and independent volume comparisons", "",
        "| Metric | Statewide denominator | Top-15 votes/ballots | Top-15 % | Minimum counties for 80% | 80% set share % |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for metric, info in ranks.items():
        lines.append(f"| {metric.replace('_',' ')} | {info['statewide_denominator']:,} | {info['top15_votes']:,} | {float(info['top15_share_percent']):.6f} | {info['minimum80_count']} | {float(info['minimum80_share_percent']):.6f} |")
    lines += ["", "All five independent rankings select the same 32-county 80% membership, although the orders and shares differ. Each comparison is independently ranked, never substituted for Senate votes. [ranking-comparisons.json](data/turnout/ranking-comparisons.json) retains all five full orders, cumulative integers and separate exact 80% sets. The [88-county CSV](data/county-turnout.csv) gives their ranks side by side. Registration totals are **8,159,946 (2024)** and **8,029,950 (2022)**. Ballots counted are **5,851,387** and **4,201,368**; Senate contest votes are **5,704,620** and **4,133,342**; 2024 president votes are **5,767,788**. These are distinct quantities.", "",
        "The 2024 Senate ballot-minus-contest gap is **146,767**, the presidential gap **83,599**; the 2022 Senate gap is **68,026**. A subtraction is not a certified undervote, overvote or rejected-ballot classification. The archived statewide files do not publish voting-method splits or separate under/over counts for these contests; those normalized fields are blank. Missing is not zero. Ballots/registration is registered-voter participation, not voting-eligible-population turnout. The 2022 comparator reflects a midterm electorate and candidate effects; it is not a forecast of special-election turnout.", "",
        "## Native units, vintages and handoff limits", "",
        "Every source reporting row is retained exactly once: **8,878 in 2024 and 8,933 in 2022**, 88 counties each. Composite keys are `election_date|county_FIPS|Precinct Code`; county plus code is unique within each vintage. No rows with administrative labels, split precincts, zero registration or zero votes are filtered out. These particular statewide inventories have no missing code or duplicate county/code and all registration values are positive; the source calls each row a precinct and supplies no administrative-unit classification. County-level write-in residuals are a separate limitation, not extra precincts. Voting-method data cannot be inferred from precinct names.", "",
        "The [2024 unit inventory](data/turnout/reporting-units-2024.csv.gz) and [2022 inventory](data/turnout/reporting-units-2022.csv.gz) preserve exact native names/codes, region/media market, source row and statistics. Names containing `CENTRAL` are retained as ordinary native labels, not reclassified as central-count boards. [Unit vintage comparison](data/turnout/reporting-unit-vintages.json) exposes codes added/removed and shared codes with changed names. It is only an identifier/name audit: equal codes do not establish equal geometry, and changed names do not prove a split. No approved 2026 boundary vintage or precinct crosswalk is asserted. Map/reporting workers must reconcile current units against this historical inventory before slice-level comparisons.", "",
        "## Reproduction and checks", "",
        "From the repository root, run:", "", "```sh",
        "python3 senate/2026/ohio/data/turnout/build_turnout.py",
        "python3 senate/2026/ohio/data/turnout/validate_turnout.py", "```", "",
        "The builder uses only Python's standard library, reads cached XLSX scalar values without modifying the sources, and emits deterministic CSV/JSON and gzip (`mtime=0`). Validation reconstructs every generated byte from the archived inputs, checks hashes and archive status, all 88 FIPS/native county identities, unit uniqueness/coverage, every county/candidate and statewide control, independently published turnout workbooks, missing write-ins, exact rational weights summing to one, ordering, top15 and integer minimal-80% tests, relative links and the 40 MiB per-file bound. [validation.json](data/turnout/validation.json) records the executed results. The validator emits `artifact-manifest.json` with hashes/sizes for every turnout-owned source, script and product, and `partisanship-reconciliation.csv` for its read-only cross-worker comparisons. No live API, collection cadence, exact remaining count, current map approval or calibrated Needle is inferred.", "",
        "The remaining substantive gaps are precinct allocation of named write-ins, voting-method and under/over counts, a verified 2026 reporting-unit/boundary crosswalk, and current live-feed testing. Historical county ranking and the exact priority geography are reconciled; these gaps limit finer live comparisons.", "",
        "## All 88 counties", "", "| Rank | County / FIPS | 2024 Senate votes | State % | Cumulative % | 2022 Senate votes |", "| ---: | --- | ---: | ---: | ---: | ---: |"]
    for r in rows:
        lines.append(f"| {r['rank_2024_senate']} | {r['county']} / {r['county_fips']} | {r['senate_2024_votes']:,} | {float(r['senate_2024_state_share_percent']):.6f} | {float(r['senate_2024_cumulative_share_percent']):.6f} | {r['senate_2022_votes']:,} |")
    return "\n".join(lines) + "\n"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="rebuild in memory and compare every generated byte")
    args = parser.parse_args()
    products = build()
    if args.check:
        mismatches = [p for p, b in products.items() if not (ROOT/p).exists() or (ROOT/p).read_bytes() != b]
        assert not mismatches, mismatches
        print(f"PASS: deterministic reconstruction of {len(products)} products")
    else:
        for path, body in products.items():
            (ROOT/path).write_bytes(body)
        print(f"Wrote {len(products)} products")

if __name__ == "__main__":
    main()
