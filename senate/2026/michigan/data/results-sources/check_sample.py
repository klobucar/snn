import json,gzip,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
def read(n):
 b=(P/n).read_bytes();return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
a=next(c for c in read('genesee-summary.json') if c['K']=='87');b=next(c for c in read('genesee-details.json')['Contests'] if c['K']=='87')
cols=[sum(v[i] for v in b['V']) for i in range(len(a['V']))]
assert cols==a['V'];assert sum(a['V'])==a['T'];assert len(b['P'])==a['TP']==a['PR']==156;assert all(sum(v)==t for v,t in zip(b['V'],b['T']))
r={'election':'2024-11-05','county':'Genesee','contest':'United States Senator','contest_key':'87','candidate_votes':a['V'],'contest_votes':a['T'],'reporting_units':len(b['P']),'precinct_candidate_sums_equal_summary':True,'precinct_row_totals_equal_candidate_sums':True,'unit_example':b['P'][0],'unit_native_numeric_ids':'Eid and Cid are empty; preserve full label and array order within version','remaining_votes':None,'cadence':None}
(P/'schema-checks.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
