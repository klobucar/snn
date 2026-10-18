#!/usr/bin/env python3
"""Write the map question report and download manifest from retained evidence."""
import csv,datetime,gzip,json,pathlib
from acquire import ROOT,digest
STATE=ROOT.parent
def main():
    units=json.loads((ROOT/'unit-inventory.json').read_text());pr=[u for u in units if u['priority']]
    acq=json.loads((ROOT/'acquisitions.json').read_text());pdf=json.loads((ROOT/'pdf-audit.json').read_text())
    geo=json.loads((ROOT/'geometry-audit.json').read_text())['layers'];sources=json.loads((ROOT/'municipal-sources.json').read_text())
    cr=json.loads((ROOT/'census-audit.json').read_text());finer=json.loads((ROOT/'finer-research.json').read_text())
    start=min(x['retrieved_utc'] for x in acq.values());end=max(x['retrieved_utc'] for x in acq.values())
    unique_pdfs={x['path'] for x in pdf.values() if x.get('page_count')};page_paths={p['preview'] for x in pdf.values() for p in x.get('pages',[])}
    item=json.loads(gzip.decompress((ROOT/'raw/town-item.gz').read_bytes()))
    modified=datetime.datetime.fromtimestamp(item['modified']/1000,datetime.timezone.utc).isoformat()
    rows=[]
    for key,r in acq.items():
        scope='source evidence / metadata; inspect status and content'
        count='';crs='';vintage='retrieval snapshot; effective/approval date unestablished'
        if key.startswith('town-batch-'):scope='original GeoLibrary municipal/township native GIS response';count=len(json.loads(gzip.decompress((ROOT/r['path']).read_bytes()))['features']);crs='EPSG:26919';vintage='metadata extent2024-02-23; current snapshot'
        if key.startswith('orono-batch-'):scope='original Orono Precincts_2021 native GIS response';count=3;crs='EPSG:3857';vintage='2021 layer label; current publication'
        if r['path'].endswith('.pdf'):scope='original PDF; scope/vintage in municipal-sources.json';count=pdf.get(key,{}).get('page_count','')
        if key=='census-vtd-2020pl':scope='original historical Census VTD shapefile ZIP';count=cr['feature_count'];crs='EPSG:4269';vintage='2020 Census reference'
        rows.append({'id':key,'local_path':r['path'],'source_url':r['url'],'retrieved_utc':r['retrieved_utc'],'http_status':r['status'],'scope':scope,'geometry_vintage':vintage,'native_crs':crs,'feature_or_page_count':count,'stored_bytes':r['stored_bytes'],'stored_sha256':r['stored_sha256'],'original_sha256':r['original_sha256'],'native_key':''})
    for u in pr:
        for field,scope in [('geojson','full-vertex municipal/component GeoJSON derivative'),('preview','SVG display derivative'),('census_geojson','historical Census name-candidate GeoJSON derivative'),('census_preview','historical Census display derivative')]:
            if field not in u:continue
            p=ROOT/u[field];b=p.read_bytes();rows.append({'id':'priority-'+str(u['rank'])+'-'+field,'local_path':u[field],'source_url':acq['town-layer']['url'] if not field.startswith('census') else acq['census-vtd-2020pl']['url'],'retrieved_utc':start+' to '+end,'http_status':'derived offline','scope':scope,'geometry_vintage':u['geometry_vintage'] if not field.startswith('census') else '2020 Census reference','native_crs':'OGC:CRS84 for GeoJSON; SVG local display transform' if field.endswith('json') else 'SVG viewBox display units','feature_or_page_count':len(u['matched_source_ids']) if not field.startswith('census') else 'see census-compatibility.json','stored_bytes':len(b),'stored_sha256':digest(b),'original_sha256':'see acquisitions.json; derivative not original','native_key':u['native_key']})
    fields=list(rows[0])
    with (ROOT/'manifest.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    text=f'''# Maine precinct and reporting-boundary maps

**Actual downloads and an offline [map index](maps/index.html) are complete for the accepted research workload.** The index has the exact ordered **164 native reporting keys**: **155 municipal/township references, eight combined-label component references, and STATE UOCAVA as administrative, no polygon appropriate**. Every one of the 163 physical entries has a local full-vertex GeoJSON subset and SVG preview. These are boundary **references**, not a validated 2024 or November 2026 election-results crosswalk. The eight combined labels and their unknown extents are retained whole. [All 512 native identities](maps/unit-inventory.json), [CSV inventory](maps/unit-inventory.csv), and [compatibility diagnostics](maps/compatibility-diagnostics.json) also retain the 348-unit remainder.

Retained downloads include **8,421 GeoLibrary polygon features**, **three Orono precinct features**, **{len(unique_pdfs)} distinct original PDFs with {len(page_paths)} page previews**, and the original **199-feature 2020 Census VTD shapefile ZIP**. Original bytes, derivatives, failed responses and metadata are distinguished. Retrievals span **{start} to {end} UTC**, during October 17, 2026 in America/Chicago. [Download manifest](maps/manifest.csv), [HTTP acquisitions](maps/acquisitions.json), [offline validation](maps/validation.json).

## Accepted units and arithmetic

The read-only [turnout contract](data/turnout/priority-set.json) and [ordered key file](data/turnout/priority-keys.txt) govern the workload. Key-file SHA-256 is `086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407`. The all-unit source CSV remains SHA-256 `0d0852ce0029561dec0d764f52272b07c88c329e4f8eb5d4a946ed41f33569be`.

Top 15 = **215,627 / 821,072**. First 163 = **656,778**; first 164 = **658,029 / 821,072 = 80.14266715%**. Pownal contributes 1,251 and crosses. These are native return counts and research priorities; no votes are assigned to a polygon, component, precinct or map color. All 512 identities remain in statewide arithmetic. Counties/FIPS are parent reporting context, not substituted election authorities or map topology.

**STATE UOCAVA**, rank 22, 6,434 votes, has no county/FIPS and no physical polygon. Its [index entry](maps/index.html#unit-22) explicitly says administrative, no polygon appropriate. The official [Uniformed Service and Overseas Voters page](https://www3.maine.gov/sos/elections-voting/uniformed-service-and-overseas-voters) identifies central Elections Division administration and state/federal ballot issuance. The successful original page acquisition is reused read-only from the official-results worker's [request metadata](data/results-sources/requests/9aefb960640e24b8df40.json), not duplicated. Its earlier guessed military-and-overseas route 404 is not the authority. No missing votes are inferred from the absence of geometry.

## Official state GIS: authority chain and vintage

The [state GeoLibrary landing](https://www.maine.gov/geolib/) directs visitors to the [new GeoLibrary Hub](https://mainegeolibrary-maine.hub.arcgis.com/). The web reader exposed that notice; direct original-byte attempts at the old state landing returned 403 and are retained as failures. The new Hub downloaded 200. Its HTML identifies site `c0525bd8d13b4637a352684867faf162` and State of Maine organization `RbMX0mRVOFNTdLzd`. Its [site configuration](https://www.arcgis.com/sharing/rest/content/items/c0525bd8d13b4637a352684867faf162/data?f=pjson) supplies the actual catalog groups. A bounded catalog search of those groups returned the [town/township item](https://www.arcgis.com/sharing/rest/content/items/289a91e826fd4f518debdd824d5dd16d?f=pjson), which supplies the [actual polygon service](https://services1.arcgis.com/RbMX0mRVOFNTdLzd/arcgis/rest/services/Maine_Town_and_Townships_Boundary_Polygons/FeatureServer/0). The item owner is `Emily.Pettit@maine.gov_maine`; its credits identify MaineIT GIS, GeoLibrary and the mapping source agencies. Saved Hub, configuration, catalog result, item, service schema and XML metadata preserve this chain in [acquisitions.json](maps/acquisitions.json).

The layer depicts **organized-town and unorganized-territory political boundaries at 1:24,000**, with land/island detail, **not a statewide current voting-precinct layer**. It has 8,421 features and 924 distinct town/county/geocode groups. Multiple features for a geocode, including separate islands, are expected. The catalog also returns legislative districts and 2000/2010 voting layers; those names do not make them current precincts. The named historical or legislative alternatives were not relabeled or substituted.

The XML extent text says boundaries current as of **February 23, 2024**. The live service data-last-edit timestamp is **2026-06-03T15:31:46.130Z**; the catalog item modification timestamp is **{modified}**. These are different provenance facts. This is a **current service snapshot retrieved in 2026**, containing a 2024 extent statement, **not an independently frozen November 5, 2024 export**. None establishes November 3, 2026 legal approval or unchanged geography.

Native CRS is **EPSG:26919, NAD83 / UTM zone19N**. Source `hasZ=false`, `hasM=false`; true-curve queries were requested and **zero curve geometries returned**. Original Esri JSON batches preserve all native coordinates and attributes, including `OBJECTID`, `GlobalID`, `TOWN`, `COUNTY`, five-character `GEOCODE`, `CNTYCODE`, `ISLANDID`, flags and edit timestamps. `OBJECTID` is a service retrieval ID; `GEOCODE` is a state geographic code; neither becomes an unpublished results precinct ID. Shape area/length fields remain native source attributes, not recomputed longitude/latitude areas. [All IDs and batches](maps/gis-downloads.json), [924-group name inventory](maps/town-name-inventory.json).

## Municipal ward/precinct supplements

The [index](maps/index.html#supplements) links originals and **every page** of every downloaded PDF; the 75-page island registry is also fully previewed. PDF PNGs/text and SVGs are derivatives; no rendered page is described as an original PDF. Current published does not mean approved November 2026. Printed dates below are publisher assertions; a title, filename, upload timestamp or matching count alone is not proof of legal adoption. Full source attempts, redirects and bytes/hashes are retained.

| Municipality / reference | Local original or GIS | Source scope and observed vintage |
| --- | --- | --- |
'''
    for s in sources:
        links=[]
        for a in s.get('assets',[]):
            pa=pdf.get(a['id'],{})
            if pa.get('page_count'):links.append(f'[{a["id"]}](maps/{pa["path"]})')
        if (ROOT/'municipal-gis'/(s['id']+'.geojson.gz')).exists():links.append(f'[precinct GIS](maps/municipal-gis/{s["id"]}.geojson.gz)')
        text+='| '+s['unit']+' | '+(' / '.join(links) or 'No usable original finer map; see attempts')+' | '+s.get('vintage_note','Unestablished').replace('|','/')+' |\n'
    text+='''
**Orono's complete primary chain** is [election map page](https://www.orono.org/915/Election-Redistricting-Maps) -> its actual `arcg.is/0O804` link -> [Elections Map Zone Lookup](https://orono.maps.arcgis.com/apps/instant/lookup/index.html?appid=b81be0f2f464469dbf1e433149ecae58) -> retained app configuration -> webmap `371f73a1d6c74ec28e4694bebac388f2` -> [Precincts_2021/0](https://services.arcgis.com/42HL8w3LvBbvPLB3/arcgis/rest/services/Precincts_2021/FeatureServer/0). App and service item owner is `admin_Orono`, organization `42HL8w3LvBbvPLB3`. Three native polygons have `Ward=1`, `Precinct=1/2/3`; preserve `ID`, `NAME`, both GlobalID fields and population attributes. Population is not a vote count. Native CRS EPSG:3857; no Z/M/curves returned. The 2021 layer label and app's VersionAug02,2022 introduction are historical labels on a currently linked service. No2024 or 2026 legal/results equivalence is asserted. [Native capture and ID checks](maps/gis-downloads.json), [preview](maps/previews/orono-gis.svg).

**Portland's vendor authority chain** is retained in the current [Polling Places HTML](https://portlandmaine.gov/polling-places): the widget header says Precinct Maps and `manualContentItemIds` includes exactly `86d4fb4a-dfa5-49d4-9418-d6f203b75065`, the downloaded [CivicPlus PDF asset](https://content.civicplus.com/api/assets/86d4fb4a-dfa5-49d4-9418-d6f203b75065?cache=1800). [Derived configuration excerpt](maps/portland-authority-snippet.txt). City HTML required an explicitly recorded public read with TLS verification disabled after certificate verification failed; the vendor PDF used verified TLS. No browser security setting was changed. The HTML is not itself a map download, and the asset's effectiveJune2022 text does not establish November 2026 approval.

**Failures and primary alternatives:** Augusta and Auburn's old indexed/CMSContent routes 404; current official election pages exposed successful replacement PDFs. South Portland's two routes return identical bytes, retained once with both acquisition records. Lewiston's linked `maps2.lewistonmaine.gov` GIS host fails DNS; its original city ward PDF and ordinance PDF succeed. Bath's direct council landing 403; its original official PDF succeeds and the web reader exposes the landing's link. Gorham's actual current map URL returns 403 challenge on both www and non-www; the tested alternate attachment path 404. Ellsworth's actual election landing and linked2020 ward PDF return 403 directly, including no-www; the web reader exposes the actual map, but no original PDF bytes were acquired. The physical town/component references remain available, and any matching2020 Census polygons are labeled historical fallbacks. No screenshot was silently substituted for a download. [Network errors](maps/network-errors.json), [full acquisitions](maps/acquisitions.json).

The [finer-map research matrix](maps/finer-research.json) retains investigation for **all 164 priorities**, including municipal pages reused read-only from the official-results worker with their exact request IDs and hashes. Its historical CVR subdivision triggers do not become map matches. For Kennebunk, Waterboro, Presque Isle, Harpswell, Gardiner, Fort Kent, Alfred, Pittsfield and Mount Desert, inspected official routes did not yield an acquired finer ward/precinct map. Gardiner's alternative council page also403. Lisbon supplies a scanned map visibly labeling municipal Wards 1/2 and state House 97/98; Ward 2 appears in both House districts. Its original scan clips the printed revision text. This historical ward/House reference does not establish current SOS W/P equivalence, a complete vintage date, or November 2026 approval. Those fine-boundary gaps are separate from the downloaded municipal whole-return references. Orono and Winslow supplements were acquired from actual links found in those primary pages.

## Combined labels and preserved unknowns

The source results have no numeric municipal/ward/precinct vote-return IDs. Eight priority combined labels have no conservative registration join; all eight have separate component-reference entries and their original whole native key/name. No component receives any part of the combined count.

| Exact historical priority return | Retained component reference / unresolved extent |
| --- | --- |
'''
    for u in pr:
        if '/' not in u['native_name']:continue
        text+='| '+u['native_name']+' | '+', '.join(u['matched_town_names'])+'. '+('; '.join(u['unresolved_components']) if u['unresolved_components'] else 'Components follow the explicit source label/current roster; historical boundary equivalence remains unverified.')+' |\n'
    text+='''
The November 2026 [SOS voting-place report](https://www3.maine.gov/sos/sites/maine.gov.sos/files/inline-files/11.3.2026%20Voting%20Place%20Report%20Posting%20Version.xlsx) has 539 data rows/499 exact labels. Its original bytes and [request metadata](data/results-sources/requests/925f39cdbc953b852aa1.json), [extracted rows](data/results-sources/current-voting-places.json), and [provisional authority relationships](data/results-sources/authority-reconciliation.json) are reused read-only, not duplicated. Its explicit current Millinocket group lists 11 townships plus Millinocket with county `PEN/PIS`; the historical `Millinocket/Twps` key remains `PEN`. Its membership is not established for 2024. Wilton's current Perkins/Washington Township components likewise do not resolve the historical `/Twps` label. Exact GIS matching keeps **Washington Township (Franklin) separate from Washington (Knox)**.

For Bristol/Louds Island Twp, the official [Coastal Island Registry](https://www11.maine.gov/dacf/parks/docs/CIR.pdf), original page 44, identifies `65-185` as LOUD'S/MUSCUNGUS. Only the GeoLibrary feature with exact `ISLANDID=65-185`, `OBJECTID=4898`, is added as a **main-island outline reference**, alongside Bristol. It retains source `TOWN=Lincoln County Island`, `GEOCODE=15000`; it is not renamed or expanded to every county island. The full reporting township extent remains unestablished. [Registry page 44 preview](maps/previews/island-registry-page-44.png).

The current workbook has **538 unique county/municipality/WP tuples, not 539 distinct precincts**. ARO / SAINT AGATHA (and Sinclair) / 1-1 appears at source rows 418 and 437 with identical place/address/opening time and different St. Agatha versus Saint Agatha voting-town text. Both source rows remain; no deduplication or invented precinct is applied. The official-results worker's [current identity audit](data/results-sources/current-voting-identity-audit.json) is reused read-only. Ellsworth's election page also discusses proposed polling-place consolidation; the linked 2020 map, proposal and observed results-PDF ward detail do not establish approved November 2026 geometry. Results evidence stays separate from map identity; no ward totals are allocated here.

All 42 combined labels across the full512-unit inventory retain named components and unknown `/Twps` pieces. Seven nonpriority physical labels have no automatic lexical geometry match: Penobscot Nation Voting District, Indian Twp, Pleasant Point Voting District, Rockwood Strip Twp, Prentiss Twp, T3 ND Twp and T22 MD Twp. They remain visible in compatibility diagnostics; this is not missing-vote treatment. Their current GIS names/codes require a separately evidenced identity relationship, not a short-name guess.

All517/510/512/513 historical source rows remain read-only by source-row identity. No ward IDs are invented for the two 2022 Cranberry Isles rows. The 2022 T3 ND Twp row 190 prints PEN inside HAN's section; that defect is not corrected or used to move a polygon. President's differing combined/split labels, including Wesley/Day Block and Medway/Twps, remain distinct. The corrected SOS versus Legislature/Clerk count difference localized to Alfred does not establish a geometry change; mechanism/timing remain unknown.

## Geometry, completeness and historical fallback audit

Both GIS services were queried for complete counts and object-ID sets, then fetched in batches of at most 80 IDs, below their advertised limits. Count/ID sets were checked again after the batches: **8,421/8,421 state features in 106 batches**, **3/3 Orono features in one batch**. Every requested ID returned once; no transfer-limit flag was true. Original source batches remain independently downloadable from the index. No WFS limit was involved. Native Z/M and curve support versus actual returned geometry are recorded separately.

All 8,421 native GeoLibrary geometries and all derivatives are retained, with **1,262,484 vertices**, complete source attributes and identical ID coverage. Full-state geographic derivatives are split into 16 source-county files solely for size/lookup; that storage split does not create county election results. Priority subsets are separate derivatives, with no simplification or coordinate rounding. Pyproj transforms native CRS to EPSG:4326 with longitude/latitude axis order (OGC:CRS84 GeoJSON); the operation is recorded in the audit. SVGs use `x=longitude*cos(44.5°), y=-latitude`, fitted to their extent and rounded to0.01 display units only. They are unsuitable for measurement; no polygon union, topology repair, clipping or vote allocation is performed.

**GeoLibrary defects:** eight native invalid geometries: `6606`Phippsburg, `6687`Saint George, `7051`Woolwich, `7181`Bath, `7465`Harrington, `7887`Milbridge, `8016`Jonesport, `8399`Matinicus Isle Plt. GEOS reports ring self-intersections. Four affected municipalities are priority; their invalid geometry stays in the subsets. There are zero empty geometries or nonfinite coordinates. One positive-area overlap is between source island features8173/8196 (Piscataquis County Island), **236.21015783465097m²** in native EPSG:26919. Orono's three geometries are individually valid but have two positive-area overlaps: IDs 1/3 = **225.88965055139596**, IDs 2/3 = **1650.274622252098** native Web-Mercator square units; these are not physical ground-area estimates. Invalid native geometries were explicitly excluded from pairwise overlap testing; no absence-of-gaps or legal-boundary guarantee follows. [Full native/derivative topology reasons and overlap pairs](maps/geometry-audit.json).

The [Census TIGER/Line landing](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html), actual [2020PL Maine directory](https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/23_MAINE/23/), and [original VTD ZIP](https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/23_MAINE/23/tl_2020_23_vtd20.zip) are retained. The initially tried non-PL2020/VTD directory/file 404; the actual primary directory supplies the successful original. ZIP CRCs and every member's size/hash pass. It has 199 unique GEOID20 features, NAD83 geographic CRS (EPSG:4269), polygon type 5 without Z/M. All 199 validate and are nonempty. Maine's submitted Census VTD coverage is partial, so this file is a **historical Census reference**, not a complete municipal map or approved precinct layer. State GeoJSON and strictly county/name-prefix candidate subsets/previews are available. [Census member/ID audit](maps/census-audit.json), [candidate compatibility](maps/census-compatibility.json). No 2010/2020 VTD ID is made into a 2024/2026 result key.

## Reproduction and offline checks

From repository root, with Python dependencies `requests`, `shapely`, `pyproj`, `pyshp`, `PyMuPDF` and `Pillow` available (dependencies/caches are not retained):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/research_finer.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/build_maps.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/render_qa.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/write_report.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/validate_maps.py
PYTHONDONTWRITEBYTECODE=1 python3 senate/2026/maine/maps/hash_assets.py
```

These commands are offline. `acquire.py`, `fetch_gis.py`, `fetch_municipal.py` and `discover.py` retain reproducible bounded acquisition methods, known linked source URLs and failure handling; refresh is separate and can change the snapshot. Preserve retained originals before any refresh. Gzip has deterministic `mtime=0`; decompression reproduces the original response entity byte hash. HTTP entity bytes are distinguished from gzip storage, with status/headers/redirects and original/stored sizes/hashes. Original downloaded PDF/ZIP bytes are unchanged; duplicate response URLs can reference one stored object. App shells, logo downloads and challenges are metadata/evidence, not counted map geometry. [Read-only external evidence hashes](maps/external-evidence-references.json).

`validate_maps.py` checks all 512 exact identities/raw names/contract fields and the ordered164 key bytes; the administrative no-polygon case; all acquisition hashes/lengths; pre/post service counts and complete ID sets; bounded batches and transfer flags; every original-to-derived feature/attribute/vertex count; all 163 priority subsets/previews; Census CRC/member IDs; every PDF page preview; report/index relative links; shared-input hashes; and the strict **every retained object <40,000,000bytes** cap. [Asset hashes](maps/asset-hashes.json) cover all owned retained files except themselves. [Validation output](maps/validation.json) gives actual maximum size. PDF maps/contact sheet, Hallowell's two-page scan and the registry identity row were visually inspected; native defects are documented, not repaired.

Remaining material gaps are **November 2026 legal approval, frozen election-day2024 geometry, a results/registration/ward/board crosswalk, unresolved historical combined extents, specific finer-map acquisition gaps, and the documented topology defects**. Historical registration WP/CG/SS/SR/CC/year tuples remain intact but are not automatically election-reporting precincts. An absentee/combined/administrative reporting unit can lack its own polygon. This package supplies research maps and diagnostics, not a live collector, map approval, geographic vote allocation or calibrated probability claim.
'''
    (STATE/'precinct-maps.md').write_text(text)
if __name__=='__main__':main()
