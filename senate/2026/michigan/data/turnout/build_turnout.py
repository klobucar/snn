#!/usr/bin/env python3
"""Rebuild county-turnout.csv from saved public inputs (Python stdlib).
Run from any directory. Use --refresh to retrieve pinned upstream CSV snapshots.
PDF-to-text files are evidence extracts made with pdftotext -layout, not inputs.
"""
import argparse, collections, csv, datetime, hashlib, io, json, pathlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parent
MI = ROOT.parent.parent
MEDSL_SHA = 'df531089c78e6d0098db1a6bfb3849a066a06995'
OE_SHA = '2103114f669c2bb25f19792bf5ca290300381396'
SOURCES = {
 'medsl-mi2024-senate.csv': f'https://raw.githubusercontent.com/MEDSL/2024-elections-official/{MEDSL_SHA}/2024-senate-county.csv',
 'openelections2022.csv': f'https://raw.githubusercontent.com/openelections/openelections-data-mi/{OE_SHA}/2022/20221108__mi__general__county.csv',
 'openelections2020.csv': f'https://raw.githubusercontent.com/openelections/openelections-data-mi/{OE_SHA}/2020/20201103__mi__general__county.csv',
}
def refresh():
 for name,url in SOURCES.items():
  data=subprocess.check_output(['curl','--fail','--max-time','45','-Ls',url])
  upstream_hash=hashlib.sha256(data).hexdigest()
  if name.startswith('medsl'):
   reader=csv.DictReader(io.StringIO(data.decode())); out=io.StringIO(newline='')
   w=csv.DictWriter(out,fieldnames=reader.fieldnames); w.writeheader()
   w.writerows(r for r in reader if r['state_po']=='MI'); data=out.getvalue().encode()
  (ROOT/name).write_bytes(data)
  (ROOT/(name+'.retrieval.json')).write_text(json.dumps(dict(url=url,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),upstream_sha256=upstream_hash,saved_sha256=hashlib.sha256(data).hexdigest(),transform='filter state_po=MI; serialize CSV' if name.startswith('medsl') else 'none'),indent=2)+'\n')
def main():
 if argparse.ArgumentParser(description=__doc__).parse_known_args()[1] == ['--refresh']: refresh()
 raw=list(csv.DictReader((ROOT/'medsl-mi2024-senate.csv').open()))
 assert len(raw)==747 and {r['mode'] for r in raw}=={'TOTAL'}
 assert all(int(r['votes'])>=0 for r in raw)
 assert {r['unofficial'] for r in raw}=={'FALSE'}
 groups=collections.defaultdict(list)
 for r in raw: groups[r['county_fips']].append(r)
 assert len(groups)==83
 expected={'ELISSA SLOTKIN':2712686,'MIKE ROGERS':2693680,'JOSEPH SOLIS-MULLEN':56697,'DOUGLAS P. MARSH':53978,'DAVE STEIN':41363,'DOUG DERN':18779,'VALERIE LEE WILLIS':2,'JAMES CHAPMAN':1,'MARCUS A. IRVINE':1}
 actual=collections.Counter()
 for r in raw: actual[r['candidate']]+=int(r['votes'])
 assert dict(actual)==expected, (actual,expected)
 state=sum(actual.values()); assert state==5577187
 hist=collections.defaultdict(int)
 for r in csv.DictReader((ROOT/'openelections2022.csv').open()):
  if r['office']=='Governor':
   county_key=r['county'].upper().replace('.','')
   county_key={'GD TRAVERSE':'GRAND TRAVERSE'}.get(county_key,county_key)
   hist[county_key]+=int(r['votes'])
 assert len(hist)==83 and sum(hist.values())==4461972
 rows=[]
 for fips, rr in groups.items():
  assert len(rr)==9 and len({r['candidate'] for r in rr})==9
  total=sum(int(r['votes']) for r in rr)
  assert {int(r['totalvotes']) for r in rr}=={total}
  name=rr[0]['county_name']; d=sum(int(r['votes']) for r in rr if r['party_simplified']=='DEMOCRAT'); rep=sum(int(r['votes']) for r in rr if r['party_simplified']=='REPUBLICAN')
  assert name in hist and hist[name]>0, ('Missing 2022 county volume',name)
  rows.append(dict(county=name.title().replace('St Clair','St. Clair').replace('St Joseph','St. Joseph'),county_fips=fips,senate_2024_d=d,senate_2024_r=rep,senate_2024_other=total-d-rep,senate_2024_total=total,ballots_cast_2024='',ballots_cast_2024_status='not retrieved; do not infer from contest votes or rounded rates',governor_2022_total=hist[name],ballots_cast_2022='',senate_2020_total='',senate_2020_status='not used: inspected OpenElections extract incomplete and includes noncandidate rows',source_2024='MEDSL official-returns derivative; statewide candidate reconciliation to House Clerk',source_2022='OpenElections derivative; statewide volume reconciliation to MI Legislature',research_date='2026-10-17'))
 assert sum(r['governor_2022_total'] for r in rows)==4461972
 assert len(hist)==83
 rows.sort(key=lambda r:(-r['senate_2024_total'],r['county_fips']))
 cum=0; cutoff=None
 for i,r in enumerate(rows,1):
  cum+=r['senate_2024_total'];r['rank_2024']=i;r['statewide_senate_2024_pct']=f"{100*r['senate_2024_total']/state:.8f}";r['cumulative_senate_2024_total']=cum;r['cumulative_senate_2024_pct']=f'{100*cum/state:.8f}';r['top15']=int(i<=15)
  if cutoff is None and cum*5>=state*4:cutoff=i
 for r in rows:r['smallest_80pct_set']=int(r['rank_2024']<=cutoff)
 with (MI/'data/county-turnout.csv').open('w',newline='') as f:
  fields=['rank_2024','county','county_fips','senate_2024_d','senate_2024_r','senate_2024_other','senate_2024_total','statewide_senate_2024_pct','cumulative_senate_2024_total','cumulative_senate_2024_pct','top15','smallest_80pct_set','ballots_cast_2024','ballots_cast_2024_status','governor_2022_total','ballots_cast_2022','senate_2020_total','senate_2020_status','source_2024','source_2022','research_date']
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 summary=dict(research_date='2026-10-17',counties=83,candidates_per_county=9,senate_2024_candidates=dict(actual),senate_2024_total=state,senate_2024_other=state-actual['ELISSA SLOTKIN']-actual['MIKE ROGERS'],governor_2022_total=sum(hist.values()),top15=[r['county'] for r in rows[:15]],smallest_80pct_set=[r['county'] for r in rows[:cutoff]],cutoff_rank=cutoff,top15_total=rows[14]['cumulative_senate_2024_total'],before_cutoff_total=rows[cutoff-2]['cumulative_senate_2024_total'],cutoff_total=rows[cutoff-1]['cumulative_senate_2024_total'])
 (ROOT/'checks.json').write_text(json.dumps(summary,indent=2)+'\n')
 table='| Rank | County | Senate votes 2024 | State % | Cumulative % | Governor votes 2022 |\n| ---: | --- | ---: | ---: | ---: | ---: |\n'
 table+='\n'.join(f"| {r['rank_2024']} | {r['county']} | {r['senate_2024_total']:,} | {float(r['statewide_senate_2024_pct']):.4f} | {float(r['cumulative_senate_2024_pct']):.4f} | {r['governor_2022_total']:,} |" for r in rows)+'\n'
 (ROOT/'ranking-table.md').write_text(table)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
