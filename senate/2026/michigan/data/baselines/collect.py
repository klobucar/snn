#!/usr/bin/env python3
"""Retrieve public inputs, pin Git commits, retain MI/contest extracts and hashes."""
import urllib.request, json, hashlib, csv, io, zipfile, pathlib, datetime, gzip
P=pathlib.Path(__file__).resolve().parent
manifest=[]
def get(u):
 r=urllib.request.urlopen(u,timeout=40); b=r.read(); return b,dict(r.headers)
def save(repo,branch,path,name,filterfn=None):
 commit=json.loads(get(f'https://api.github.com/repos/{repo}/commits/{branch}')[0])['sha']
 url=f'https://raw.githubusercontent.com/{repo}/{commit}/{path}'
 b,h=get(url); original=b
 if path.endswith('.zip'):
  z=zipfile.ZipFile(io.BytesIO(b)); b=z.read(z.namelist()[0])
 if filterfn:
  rd=csv.DictReader(io.StringIO(b.decode('utf-8-sig'))); out=io.StringIO(); w=csv.DictWriter(out,fieldnames=rd.fieldnames);w.writeheader();w.writerows(r for r in rd if filterfn(r));b=out.getvalue().encode()
 if name=='2024-president-mi.csv.gz': b=gzip.compress(b,mtime=0)
 (P/name).write_bytes(b)
 manifest.append(dict(file=name,url=url,repository=repo,commit=commit,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),research_date='2026-10-17',http_status=200,headers=h,download_sha256=hashlib.sha256(original).hexdigest(),saved_sha256=hashlib.sha256(b).hexdigest(),transformation='ZIP decompression and/or CSV row filtering; original column values retained',source_status='Secondary transcription of official results; primary archive access blocked'))
save('MEDSL/2024-elections-official','main','2024-senate-county.csv','2024-senate-mi.csv',lambda r:r['state_po']=='MI')
save('MEDSL/2024-elections-official','main','individual_states/mi24.zip','2024-president-mi.csv.gz',lambda r:r['office']=='US PRESIDENT')
for year,date,office in [(2020,'20201103','U.S. Senate'),(2022,'20221108','Governor')]:
 save('openelections/openelections-data-mi','master',f'{year}/{date}__mi__general__county.csv',f'{year}-county.csv')
save('MEDSL/2024-elections-official','main','README.md','MEDSL-README.md')
save('openelections/openelections-data-mi','master','README.md','OpenElections-README.md')
url='https://github.com/pmheideman/us-county-election-results/releases/download/v1.0.0/us_county_election_results_v1.0.0.zip'
b,h=get(url); z=zipfile.ZipFile(io.BytesIO(b))
for member in ['us_county_results_long.csv','SOURCES.csv']:
 rd=csv.DictReader(io.StringIO(z.read(member).decode('utf-8-sig'))); rows=list(rd)
 if member.startswith('us_county'):
  rows=[r for r in rows if r['state_po']=='MI' and r['year']=='2020' and r['office']=='senate' and r['stage']=='general']; sourceids={r['source'] for r in rows}; name='2020-senate-mi.csv'
 else:
  rows=[r for r in rows if any(v in sourceids for v in r.values())];name='2020-sources.csv'
 out=io.StringIO();w=csv.DictWriter(out,fieldnames=rd.fieldnames);w.writeheader();w.writerows(rows);saved=out.getvalue().encode();(P/name).write_bytes(saved)
 manifest.append(dict(file=name,url=url,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),research_date='2026-10-17',http_status=200,headers=h,download_sha256=hashlib.sha256(b).hexdigest(),saved_sha256=hashlib.sha256(saved).hexdigest(),transformation='ZIP member '+member+' filtered to Michigan 2020 general Senate / relevant source metadata',source_status='Secondary compilation; preserve source and quality flags'))
(P/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
