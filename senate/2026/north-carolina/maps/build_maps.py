"""Offline, full-precision precinct exports and research diagnostics.

Reads turnout inputs without modifying them. Writes only maps/.
Install requirements.txt, or use the optional local .runtime dependency folder.
"""
from pathlib import Path
import collections
import csv
import html
import io
import json
import math
import platform
import sys
import warnings
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".runtime"))
import shapefile
import pyproj
from pyproj.transformer import TransformerGroup
import shapely
from shapely.geometry import shape
from shapely.validation import explain_validity
from source_io import read, sha

VINTAGES = {"2024-07-23": "SBE_PRECINCTS_20240723", "2026-08-24": "SBE_PRECINCTS_20260824"}
EXPECTED = "Wake,Mecklenburg,Guilford,Forsyth,Durham,Buncombe,Cumberland,Union,New Hanover,Johnston,Cabarrus,Gaston,Iredell,Brunswick,Davidson,Alamance,Orange,Pitt,Catawba,Onslow,Randolph,Rowan,Henderson,Harnett,Moore,Craven,Lincoln,Wayne,Nash,Chatham,Cleveland,Rockingham,Robeson,Burke,Carteret,Caldwell,Franklin,Wilson".split(",")

def dump(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")

def table(name, rows):
    with (ROOT / name).open("w", newline="") as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def slug(name):
    return name.lower().replace(" ", "-")

def positions(coords):
    if len(coords) and isinstance(coords[0], (int, float)):
        yield coords
    else:
        for part in coords:
            yield from positions(part)

def transform(coords, transformer):
    if len(coords) and isinstance(coords[0], (int, float)):
        return transformer.transform(*coords)
    return [transform(part, transformer) for part in coords]

def rings(geometry):
    c = geometry["coordinates"]
    return c if geometry["type"] == "Polygon" else [r for polygon in c for r in polygon]

def preview(features, bounds, title):
    # Only the display derivative is rounded and simplified (0.00002 degrees).
    # The native ZIP and GeoJSON retain every source vertex.
    minx, miny, maxx, maxy = bounds
    sx = math.cos(math.radians((miny + maxy) / 2))
    scale = min(930 / ((maxx-minx)*sx), 630 / (maxy-miny))
    ox = (1000-(maxx-minx)*sx*scale)/2
    oy = 65+(650-(maxy-miny)*scale)/2
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 760"><title>{html.escape(title)}</title>',
           '<rect width="1000" height="760" fill="#f8fafc"/>',
           f'<text x="25" y="32" font-family="sans-serif" font-size="22">{html.escape(title)}</text>',
           '<text x="25" y="55" font-family="sans-serif" font-size="14">Research preview · published snapshot · November approval unverified</text>']
    for f in features:
        # Explicitly simplified, non-authoritative preview only; no repair.
        display = shape(f["geometry"]).simplify(0.00002, preserve_topology=True).__geo_interface__
        parts=[]
        for ring in rings(display):
            parts.append("M"+"L".join(f'{ox+(x-minx)*sx*scale:.2f},{oy+(maxy-y)*scale:.2f}' for x,y in ring)+"Z")
        svg.append(f'<path d="{" ".join(parts)}" fill="#dbeafe" fill-rule="evenodd" stroke="#2563eb" stroke-width="0.7"><title>{html.escape(f["properties"]["prec_id"]+" — "+f["properties"]["enr_desc"])}</title></path>')
    svg.append('<text x="25" y="740" font-family="sans-serif" font-size="13">No basemap; independent county extent. Hover for native precinct IDs. Full precision GeoJSON linked in index.</text></svg>')
    return "\n".join(svg)+"\n"

def result_units(year, group):
    date = "20241105" if year == 2024 else "20221108"
    path = ROOT.parent / "data" / "turnout" / f"results_pct_{date}.zip"
    z = zipfile.ZipFile(path)
    units = collections.defaultdict(dict)
    with z.open(f"results_pct_{date}.txt") as f:
        for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter="\t"):
            if row["Contest Group ID"] != str(group):
                continue
            key = row["Precinct"]
            flag = row["Real Precinct"]
            assert flag in ("Y", "N")
            old = units[row["County"]].setdefault(key, flag)
            assert old == flag
    return units, dict(path=str(path.relative_to(ROOT.parent)), sha256=sha(path.read_bytes()), date=date, contest_group_id=group)

def main():
    counties_path = ROOT.parent / "data" / "county-turnout.csv"
    counties = list(csv.DictReader(counties_path.open()))
    assert len(counties) == 100
    assert len({c["county_fips"] for c in counties}) == 100
    assert len({c["ncsbe_county_id"] for c in counties}) == 100
    priority = [c for c in counties if c["research_priority"] == "1"]
    assert [c["county"] for c in priority] == EXPECTED
    assert sum(int(c["president_2024_total"]) for c in counties) == 5699145
    assert sum(int(c["president_2024_total"]) for c in priority) == 4576486
    byname = {c["county_native"]: c for c in counties}
    source_results, result_deps = {}, []
    for year, group in [(2024, 1393), (2022, 1378)]:
        source_results[year], dep = result_units(year, group)
        result_deps.append(dep)
        assert set(source_results[year]) == set(byname)

    checks = dict(priority_count=38, inventory_count=100, priority_president_2024_votes=4576486,
        statewide_president_2024_votes=5699145, priority_pct=4576486/5699145*100,
        dependencies=[dict(path="data/county-turnout.csv",sha256=sha(counties_path.read_bytes()))]+result_deps,
        runtime=dict(python=platform.python_version(),pyshp=shapefile.__version__,pyproj=pyproj.__version__,
            proj=pyproj.proj_version_str,shapely=shapely.__version__,geos=shapely.geos_version_string), vintages={})
    allrecords = {}
    diagnostics = {}
    native_geometries = {}
    manifest=[]
    indexrows=[]
    inventory=[]
    for vintage, basename in VINTAGES.items():
        archive = read("raw/"+basename+".zip")
        z=zipfile.ZipFile(io.BytesIO(archive))
        members = {i.filename:dict(bytes=i.file_size,sha256=sha(z.read(i.filename)),crc32=f"{i.CRC:08x}") for i in z.infolist()}
        # z.read verifies ZIP CRC for every member, including all .shp/.shx/.dbf bytes.
        prj=z.read(basename+".prj").decode()
        source_crs=pyproj.CRS.from_wkt(prj)
        assert source_crs.to_epsg() == 2264
        with warnings.catch_warnings(record=True) as recorded:
            group=TransformerGroup(source_crs,pyproj.CRS("EPSG:4326"),always_xy=True)
        transformer=next(t for t in group.transformers if t.accuracy == 4.0)
        reader=shapefile.Reader(shp=io.BytesIO(z.read(basename+".shp")),
            shx=io.BytesIO(z.read(basename+".shx")),dbf=io.BytesIO(z.read(basename+".dbf")),encoding="utf-8")
        records=collections.defaultdict(list)
        geoms=collections.defaultdict(list)
        issues=collections.defaultdict(list)
        transformed=collections.defaultdict(list)
        for rownum, sr in enumerate(reader.iterShapeRecords(),1):
            props=sr.record.as_dict()
            county=byname[props["county_nam"]]
            assert props["county_id"] == int(county["ncsbe_county_id"])
            native=sr.shape.__geo_interface__
            g=shape(native)
            issue=dict(prec_id=props["prec_id"],source_id=props["id"],source_row=rownum,
                native_valid=g.is_valid,native_empty=g.is_empty,native_reason=explain_validity(g))
            records[props["county_nam"]].append(props)
            geoms[props["county_nam"]].append(g)
            if county["research_priority"] != "1":
                continue
            geo={"type":native["type"],"coordinates":transform(native["coordinates"],transformer)}
            points=list(positions(geo["coordinates"]))
            assert len(points) == len(sr.shape.points)
            assert all(math.isfinite(v) for p in points for v in p)
            assert all(-85 < x < -75 and 33 < y < 37 for x,y in points)
            assert all(len(r)>=4 and r[0]==r[-1] for r in rings(geo))
            gg=shape(geo)
            issue.update(geojson_valid=gg.is_valid,geojson_empty=gg.is_empty,
                geojson_reason=explain_validity(gg),vertices=len(points))
            if not g.is_valid or not gg.is_valid or g.is_empty or gg.is_empty:
                issues[props["county_nam"]].append(issue)
            # Source properties remain intact; enrichment fields have a distinct prefix.
            props_out=dict(props,_county_fips=county["county_fips"],_source_row=rownum,_snapshot=vintage)
            transformed[props["county_nam"]].append(dict(type="Feature",id=county["county_fips"]+":"+props["prec_id"],properties=props_out,geometry=geo))
        assert set(records) == set(byname)
        allrecords[vintage]=records
        native_geometries[vintage]=geoms
        vm=dict(archive="raw/"+basename+".zip",archive_sha256=sha(archive),zip_members=members,
            statewide_features=len(reader),source_crs_wkt=prj,source_crs="EPSG:2264",geojson_crs="OGC:CRS84 (WGS84 longitude, latitude)",
            source_fields=[dict(name=f[0],type=f[1],width=f[2],decimals=f[3]) for f in reader.fields[1:]],
            transform=dict(description=transformer.description,pipeline=transformer.definition,accuracy_metres=transformer.accuracy,
                best_available=group.best_available,warnings=[str(w.message) for w in recorded],
                unavailable_operations=[o.name for o in group.unavailable_operations]),counties={})
        checks["vintages"][vintage]=vm
        diagnostics[vintage]={}
        (ROOT/vintage).mkdir(exist_ok=True)
        source_meta=json.loads((ROOT/"raw"/(basename+".zip.meta.json")).read_text())
        for county in priority:
            cn=county["county_native"]
            feats=sorted(transformed[cn],key=lambda f:f["properties"]["prec_id"])
            ids=[f["properties"]["prec_id"] for f in feats]
            assert len(set(ids))==len(ids) and all(ids)
            bounds=[min(g.bounds[0] for g in map(lambda f:shape(f["geometry"]),feats)),
                    min(g.bounds[1] for g in map(lambda f:shape(f["geometry"]),feats)),
                    max(g.bounds[2] for g in map(lambda f:shape(f["geometry"]),feats)),
                    max(g.bounds[3] for g in map(lambda f:shape(f["geometry"]),feats))]
            rel=f'{vintage}/{slug(county["county"])}'
            fc=dict(type="FeatureCollection",name=f'{county["county"]} — NCSBE {vintage}',bbox=bounds,features=feats)
            (ROOT/(rel+".geojson")).write_text(json.dumps(fc,separators=(",",":"),ensure_ascii=False,allow_nan=False)+"\n")
            (ROOT/(rel+".svg")).write_text(preview(feats,bounds,f'{county["county"]} · {vintage} · {len(feats)} precincts'))
            invalid=sum(not g.is_valid for g in geoms[cn])
            vm["counties"][cn]=dict(feature_count=len(feats),bbox=bounds,native_invalid=invalid,
                geojson_invalid=sum(not shape(f["geometry"]).is_valid for f in feats),native_empty=sum(g.is_empty for g in geoms[cn]),
                unique_nonempty_precinct_ids=True,source_ids_unique=len({r["id"] for r in records[cn]})==len(feats),
                source_id_examples=[{k:r[k] for k in ['id','county_id','county_nam','prec_id','enr_desc','of_prec_id']} for r in sorted(records[cn],key=lambda r:r['prec_id'])[:3]],
                vertex_count=sum(len(list(positions(f["geometry"]["coordinates"]))) for f in feats))
            overlaps=[]
            valid=[(i,g) for i,g in enumerate(geoms[cn]) if g.is_valid and not g.is_empty]
            tree=shapely.STRtree([g for _,g in valid])
            for i,(ri,g) in enumerate(valid):
                for j in tree.query(g,predicate="intersects"):
                    if int(j)<=i: continue
                    rj,other=valid[int(j)]
                    area=g.intersection(other).area * (1200/3937)**2
                    if area>1:
                        overlaps.append(dict(prec_id_a=records[cn][ri]["prec_id"],prec_id_b=records[cn][rj]["prec_id"],overlap_square_metres=area))
            diagnostics[vintage][cn]=dict(geometry_defects=issues[cn],overlap_pairs_over_1_square_metre=overlaps,
                invalid_features_excluded_from_overlap_check=invalid,overlap_check_crs="EPSG:2264; converted ftUS² to m²",
                limitations="No independent legal county outline/gap test; overlap test excludes invalid shapes and areas <=1 m²; no geometry repaired.")
            for suffix in [".geojson",".svg"]:
                path=ROOT/(rel+suffix)
                manifest.append(dict(county=county["county"],county_fips=county["county_fips"],ncsbe_county_id=county["ncsbe_county_id"],
                    source_url=source_meta["url"],official_owner="North Carolina State Board of Elections",geometry_vintage=vintage,
                    status="historical pre-election snapshot" if vintage.startswith('2024') else "latest published archive; November 2026 approval unverified",
                    retrieved_utc=source_meta["retrieved_utc"],local_path=rel+suffix,format="GeoJSON" if suffix==".geojson" else "SVG preview derivative",
                    crs="OGC:CRS84" if suffix==".geojson" else "local equirectangular display; no measurement CRS",feature_count=len(feats),
                    bytes=path.stat().st_size,sha256=sha(path.read_bytes()),bbox=json.dumps(bounds,separators=(",",":")),
                    native_invalid=invalid,geojson_invalid=vm["counties"][cn]["geojson_invalid"],november_2026_approval="not established"))
            indexrows.append(dict(county=county["county"],vintage=vintage,count=len(feats),path=rel,invalid=invalid))
    # Independent service IDs and attribute pagination, with zero geometry duplication.
    count=json.loads(read("raw/onemap-count.json.gz"))["count"]
    oid_info=json.loads(read("raw/onemap-ids.json.gz"))
    pages=[json.loads(read(f"raw/onemap-attributes-page-{i}.json.gz")) for i in range(2)]
    features=[f["attributes"] for p in pages for f in p["features"]]
    oids=[f["objectid"] for f in features]
    assert len(features)==count==len(oid_info["objectIds"])==len(set(oids))
    assert set(oids)==set(oid_info["objectIds"])
    assert not pages[-1].get("exceededTransferLimit",False)
    service_keys={(f["county_nam"],f["prec_id"]) for f in features}
    archive_keys={(cn,f["prec_id"]) for cn,rows in allrecords["2026-08-24"].items() for f in rows}
    comparison=[]
    source_attribute_differences=[]
    source_blank_padding_differences=0
    archive_bykey={(cn,r["prec_id"]):r for cn,rows in allrecords["2026-08-24"].items() for r in rows}
    for f in features:
        k=(f["county_nam"],f["prec_id"])
        if k in archive_bykey:
            def normalized(value):
                return (value.strip() or None) if isinstance(value,str) else value
            source_blank_padding_differences += int(archive_bykey[k]['of_prec_id'] != f['of_prec_id'] and normalized(archive_bykey[k]['of_prec_id']) == normalized(f['of_prec_id']))
            diffs={a:[archive_bykey[k][a],f[a]] for a in ['id','county_id','enr_desc','of_prec_id'] if normalized(archive_bykey[k][a])!=normalized(f[a])}
            if diffs: source_attribute_differences.append(dict(county=k[0],prec_id=k[1],differences=diffs))
    checks["onemap_pagination"]=dict(count=count,ids_count=len(oid_info['objectIds']),page_counts=[len(p['features']) for p in pages],
        transfer_limit_flags=[p.get('exceededTransferLimit',False) for p in pages],unique_ids=len(set(oids)),all_ids_exactly_reconciled=True,
        current_archive_ids_only=sorted(archive_keys-service_keys),service_ids_only=sorted(service_keys-archive_keys),
        source_attribute_differences=source_attribute_differences,source_blank_padding_differences=source_blank_padding_differences,
        geometry_equivalence="not tested; service native CRS 32119 differs from archive 2264")
    # Exact literal result-label comparison; this is deliberately not a crosswalk.
    result_details=[]
    for county in counties:
        cn=county["county_native"]
        a={r['prec_id'] for r in allrecords['2024-07-23'][cn]}
        b={r['prec_id'] for r in allrecords['2026-08-24'][cn]}
        row=dict(county=county['county'],county_fips=county['county_fips'],ncsbe_county_id=county['ncsbe_county_id'],research_priority=county['research_priority'],
            president_2024_votes=county['president_2024_total'],geometry_2024_count=len(a),geometry_current_count=len(b),
            source_inventory='NCSBE statewide ZIPs contain this county; county GeoJSON exported only for priority set',november_2026_approval='not established')
        real_2024={k for k,v in source_results[2024][cn].items() if v=='Y'}
        comparison.append(dict(county=county['county'],county_fips=county['county_fips'],common_ids=sorted(a&b),historical_only_ids=sorted(a-b),current_only_ids=sorted(b-a),
            real_2024_units_without_historical_map=sorted(real_2024-a),historical_map_ids_without_real_2024_unit=sorted(a-real_2024),
            note='Shared IDs do not prove unchanged geometry; not a crosswalk.'))
        for year in [2024,2022]:
            real={k for k,v in source_results[year][cn].items() if v=='Y'}
            admin={k for k,v in source_results[year][cn].items() if v=='N'}
            row[f'results_{year}_real_units']=len(real)
            row[f'results_{year}_administrative_units']=len(admin)
            if year==2024:
                row['2024_real_literal_id_matches_to_2024_map']=len(real&a)
                row['2024_real_units_without_literal_2024_map_match']=len(real-a)
            for unit in sorted(real|admin):
                result_details.append(dict(county=county['county'],county_fips=county['county_fips'],ncsbe_county_id=county['ncsbe_county_id'],year=year,
                    contest='President' if year==2024 else 'US Senate',research_priority=county['research_priority'],result_unit_literal=unit,
                    real_precinct_flag=source_results[year][cn][unit],literal_match_2024_map=int(unit in a),literal_match_current_map=int(unit in b),
                    interpretation='administrative unit; no geographic assignment inferred' if unit in admin else 'literal label check only; geometry/election validity unestablished'))
        inventory.append(row)
    dump('checks.json',checks)
    dump('geometry-diagnostics.json',diagnostics)
    dump('vintage-id-comparison.json',comparison)
    table('county-inventory.csv',inventory)
    table('result-unit-diagnostics.csv',result_details)
    table('manifest.csv',manifest)
    groups=[]
    for county in priority:
        pieces=[]
        for r in [r for r in indexrows if r['county']==county['county']]:
            p=r['path']; v=r['vintage']
            pieces.append(f'<td><a href="{p}.svg"><img src="{p}.svg" alt="{html.escape(county["county"])} {v} precinct preview" loading="lazy"/></a><p>{v}: {r["count"]} features · {r["invalid"]} invalid<br><a href="{p}.geojson">Full precision GeoJSON</a> · <a href="{p}.svg">SVG preview</a></p></td>')
        groups.append(f'<tr><th>{html.escape(county["county"])}<br>FIPS {county["county_fips"]}<br>SBE {county["ncsbe_county_id"]}</th>{"".join(pieces)}</tr>')
    (ROOT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>North Carolina precinct research maps</title><style>body{font:16px system-ui;max-width:1300px;margin:2rem auto;padding:1rem;color:#172554}table{width:100%;border-collapse:collapse}td,th{border:1px solid #cbd5e1;padding:.7rem}th{width:13%}td{width:43%}img{width:100%;height:auto}a{color:#1d4ed8}p{line-height:1.5}</style><h1>North Carolina precinct research maps</h1><p>38 priority counties · 80.30127326% of certified 2024 presidential votes. Original NCSBE ZIPs retained in raw/. Historical July 23, 2024 and latest published August 24, 2026 snapshots. <strong>November 2026 approval and results crosswalk remain unverified.</strong></p><p>Previews are simplified display derivatives. GeoJSON retains every vertex, transformed from NAD83 State Plane ftUS to WGS84 longitude/latitude (4 m stated operation accuracy). Native invalid geometry is preserved. No basemap or vote allocation. <a href="../precinct-maps.md">Research report</a> · <a href="manifest.csv">Asset manifest</a> · <a href="county-inventory.csv">All 100 county inventory</a></p><table><thead><tr><th>County</th><th>Historical snapshot</th><th>Current published snapshot</th></tr></thead><tbody>'+''.join(groups)+'</tbody></table></html>\n')
    print(json.dumps(dict(counties=38,assets=len(manifest),features={v:sum(c['feature_count'] for c in x['counties'].values()) for v,x in checks['vintages'].items()},
        invalid={v:sum(c['native_invalid'] for c in x['counties'].values()) for v,x in checks['vintages'].items()},
        service_count=count,service_pages=[len(p['features']) for p in pages],
        service_nonpadding_attribute_differences=len(source_attribute_differences)),indent=2))

if __name__=='__main__':
    main()
