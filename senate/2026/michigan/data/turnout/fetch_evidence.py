#!/usr/bin/env python3
"""Retrieve small public primary evidence and record HTTP metadata/checksums."""
import datetime,hashlib,json,pathlib,subprocess
P=pathlib.Path(__file__).resolve().parent
sources={
'index.html':'https://www.michigan.gov/sos/elections/election-results-and-data',
'certification.html':'https://www.michigan.gov/sos/resources/news/2024/11/22/michigan-board-of-state-canvassers-certifies-the-2024-general-election',
'access-matters.pdf':'https://www.michigan.gov/sos/-/media/Project/Websites/sos/Press-releases/2025/documents/MDOS-2024-Elections-Report.pdf',
'house-statistics2024.pdf':'https://clerk.house.gov/member_info/electionInfo/2024/statistics2024.pdf',
'legislature2022-total.pdf':'https://legislature.mi.gov/documents/2023-2024/billanalysis/House/pdf/2023-HLA-5571-211FCAD0.pdf',
'results2024.html':'https://mvic.sos.state.mi.us/votehistory/Index?type=C&electionDate=11-5-2024',
'medsl-provenance.md':'https://raw.githubusercontent.com/MEDSL/2024-elections-official/df531089c78e6d0098db1a6bfb3849a066a06995/README.md',
}
manifest=[]
for name,url in sources.items():
 t=datetime.datetime.now(datetime.timezone.utc).isoformat()
 cp=subprocess.run(['curl','--max-time','20','-Ls','-A','Mozilla/5.0','-D',str(P/(name+'.headers')),url,'-o',str(P/name),'-w','%{http_code}'],capture_output=True,text=True)
 row=dict(file=name,url=url,retrieved_utc=t,curl_exit=cp.returncode,http_status=cp.stdout,headers_file=name+'.headers')
 if (P/name).exists():
  b=(P/name).read_bytes();row.update(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),access_status='blocked: Cloudflare challenge, not election results' if b'Just a moment' in b else 'retrieved')
 if cp.returncode:row['error']=cp.stderr
 manifest.append(row)
(P/'evidence-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
