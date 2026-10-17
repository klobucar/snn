#!/usr/bin/env python3
"""Retrieve House Clerk official publications and record original-byte provenance."""
import urllib.request, pathlib, hashlib, datetime, json, subprocess
P=pathlib.Path(__file__).resolve().parent
for y in [2024,2020]:
 u=f'https://clerk.house.gov/member_info/electionInfo/{y}/statistics{y}.pdf'
 r=urllib.request.urlopen(u,timeout=30);b=r.read();p=P/f'house-statistics{y}.pdf';p.write_bytes(b)
 (P/f'primary-source-{y}.json').write_text(json.dumps(dict(url=u,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),research_date='2026-10-17',http_status=r.status,headers=dict(r.headers),sha256=hashlib.sha256(b).hexdigest()),indent=2)+'\n')
 subprocess.run(['pdftotext','-layout',str(p),str(p.with_suffix('.txt'))],check=True)
