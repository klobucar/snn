#!/usr/bin/env python3
"""Account for every observed source identity. Lexical evidence is never a crosswalk."""
import csv,gzip,json,collections,re
from pathlib import Path
from acquire import ROOT,sha,save_json
from build_geometry import csv_gz
DATA=ROOT.parent/'data'

def read(fn):
 with gzip.open(DATA/fn,'rt',newline='') as f:return list(csv.DictReader(f))
def main():
 counties=list(csv.DictReader((DATA/'county-turnout.csv').open()));byf={r['county_fips']:r for r in counties}
 geom=read_geom={}
 with gzip.open(ROOT/'inventory/native-geometry-units.csv.gz','rt') as f:
  for r in csv.DictReader(f):geom.setdefault((r['county_fips'],r['vintage'][:4]),collections.Counter())[r['native_PREC']]+=1
 refs=[]
 files=['county-turnout.csv','coordinator-priority-keys.txt','coordinator-baseline-reconciliation.json','coordinator-map-subset-checks.json','turnout/priority-set.json','turnout/native-reporting-units.csv.gz','turnout/primary-native-units.csv.gz','turnout/primary-native-records.csv.gz','turnout/primary-native-diagnostics.json','baselines/native-units.csv.gz','baselines/native-source-anomalies.json','baselines/native-source-diagnostics.json','baselines/native-cells-2024.jsonl.gz','baselines/native-cells-2022.jsonl.gz','baselines/native-cells-2020.jsonl.gz','results-sources/native-unit-identities.csv.gz','results-sources/native-unit-observations.csv.gz','results-sources/native-field-schemas.json','results-sources/native-inventory-summary.json']
 reused=[]
 for mp in sorted((DATA/'turnout/raw').glob('original*meta.json')):
  md=json.loads(mp.read_text());files.append('turnout/raw/'+mp.name)
  parts=md.get('stored_parts') or [dict(path=md['stored_path'],bytes=md['stored_bytes'],sha256=md['stored_sha256'])]
  stream=[]
  for part in parts:
   fn='turnout/'+part['path'];b=(DATA/fn).read_bytes();assert len(b)==part['bytes'] and sha(b)==part['sha256'];files.append(fn);stream.append(b)
  stored=b''.join(stream);assert len(stored)==md['stored_bytes'] and sha(stored)==md['stored_sha256']
  b=gzip.decompress(stored);assert len(b)==md['original_bytes'] and sha(b)==md['original_sha256']
  reused.append(dict(source_id=md['id'],metadata='../data/turnout/raw/'+mp.name,requested_url=md['requested_url'],original_sha256=md['original_sha256'],original_bytes=md['original_bytes'],stored_parts=[dict(path='../data/turnout/'+x['path'],bytes=x['bytes'],sha256=x['sha256']) for x in parts],storage='Concatenate exact ordered gzip byte parts before decompression; original full bytes/hash verified.',scope='Read-only results original for source-native identity context; not counted as a new map acquisition.'))
 save_json(ROOT/'peer-original-reuse.json',dict(sources=reused,all_original_hashes_verified=True,no_duplicate_originals_saved=True))
 for fn in files:
  p=DATA/fn
  if p.exists():refs.append(dict(path='../data/'+fn,bytes=p.stat().st_size,sha256=sha(p.read_bytes()),role='read-only exact source or peer artifact; duplicate observations/candidate rows preserved in original, no geographic allocation'))
 rows=[];admin=re.compile(r'^(early voting|early vote|absentee|mail|provisional|central|total|county total|election totals|ev|bbm|evip)(\b|$)',re.I)
 def append(kind,raw,source,fips,year,unit,eclass='',conflict=False,physical_unknown=False):
  matches=geom.get((fips,year),{}).get(unit,0)
  if conflict:status='source conflict';reason='Published county/file identity conflict retained; exact original labels and both county fields are in input_row_json.'
  elif kind=='official-discovery' and ('excluded' in eclass):status='source conflict';reason='Observation class excludes current counts/geography: '+eclass
  elif kind=='official-discovery' and raw.get('unit_kind') in ['vote_center','vote_center_status']:status='administrative/no-polygon';reason='Source identifies vote-center location/status; polling location is not a precinct boundary.'
  elif admin.search(unit):status='administrative/no-polygon';reason='Literal source name explicitly labels an administrative/method/total group; no exclusive polygon assigned.'
  elif physical_unknown:status='unknown';reason='Published county component is absent/unverified; no filename-derived geography match admitted.'
  elif matches:status='ambiguous';reason='Exact literal native ID appears in same-year county precinct file; source identity/vintage equivalence and components are unapproved.'
  else:status='unknown';reason='No exact literal ID in same-year county precinct file; labels/styles/consolidations may differ. This is not proof that a polygon is absent.'
  rows.append(dict(inventory=kind,source_id=source,county_fips=fips,year=year,native_id=unit,observation_class=eclass,status=status,exact_literal_geometry_candidates=matches,reason=reason,input_row_json=json.dumps(raw,ensure_ascii=False,separators=(',',':'))))
 base=read('baselines/native-units.csv.gz')
 for r in base:
  append('historical-OE',r,r['source_id'],r['literal_county_fips'],r['year'],r['native_unit_id'],conflict=r['file_literal_county_conflict']=='1',physical_unknown=not r['literal_county_fips'])
 # Independent first-wave representation is checked as a set; not counted twice.
 turnout=read('turnout/native-reporting-units.csv.gz')
 bk={(r['source_id'],r['native_county_name'],r['native_unit_id']) for r in base};tk={(r['source_id'],r['source_county_name'],r['native_unit_id']) for r in turnout}
 assert bk==tk,(len(bk),len(tk),len(bk-tk),len(tk-bk))
 primary=read('turnout/primary-native-units.csv.gz')
 for r in primary:append('primary-historical',r,r['source_id'],r['county_fips'],'2024',r['native_unit_id'])
 live=read('results-sources/native-unit-identities.csv.gz')
 for r in live:append('official-discovery',r,r['source_id'],r['county_fips'],'2026',r['native_id'],r['observation_class'])
 csv_gz(ROOT/'inventory/reporting-unit-compatibility.csv.gz',rows)
 # Source-native constituent list, including county summaries and separate derived VTDs.
 contract=json.loads((DATA/'turnout/priority-set.json').read_text());const=[]
 for g in contract['groups']:
  for layer,key in [('native_constituents','source-native'),('derived_vtd_constituents','derived-VTD')]:
   for ordinal,u in enumerate(g.get(layer,[])):
    status='administrative/no-polygon' if u.get('unit_type')=='county total' else 'unknown'
    const.append(dict(dispatch_key=g['dispatch_key'],county_fips=g['county_fips'],rank=g['rank'],priority80=g['priority80'],component_class=key,component_ordinal=ordinal,status=status,reason='County summary or VTD stays separate from precinct geometry; native reporting identity requires source-specific crosswalk.',component_json=json.dumps(u,ensure_ascii=False,separators=(',',':'))))
 csv_gz(ROOT/'inventory/accepted-constituents.csv.gz',const)
 peer_summary=json.loads((DATA/'results-sources/native-inventory-summary.json').read_text())
 assert len(live)==peer_summary['source_scoped_identities']
 summary=dict(scope='All observed source identities accounted, no approved matched reporting-to-polygon rows and no votes allocated.',historical_OE_rows=len(base),independent_turnout_identity_set_equal=True,primary_historical_rows=len(primary),official_discovery_rows=len(live),official_observation_positions=peer_summary['observations'],total_identities_accounted=len(rows),accepted_constituents=len(const),accepted_groups=len(contract['groups']),status_counts=dict(collections.Counter(r['status'] for r in rows)),by_inventory={},by_county={},by_source={},reference_inputs=refs,source_observation_positions=f"All {peer_summary['observations']:,} positions/repeats are retained in the read-only results-sources/native-unit-observations.csv.gz; 302,233 selected OE candidate rows remain separately in peer native-cell/record files. They are never deduplicated or reassigned here.")
 for key in ['inventory','county_fips','source_id']:
  dd={}
  for r in rows:
   name=r[key];dd.setdefault(name,collections.Counter())[r['status']]+=1
  summary[{'inventory':'by_inventory','county_fips':'by_county','source_id':'by_source'}[key]]={k:dict(v) for k,v in dd.items()}
 save_json(ROOT/'inventory/compatibility-summary.json',summary)
 save_json(ROOT/'read-only-references.json',dict(references=refs))
 print('compatibility',len(rows),summary['status_counts'],flush=True)
if __name__=='__main__':main()
