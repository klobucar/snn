#!/usr/bin/env python3
"""Download original Alaska DOE evidence using curl default certificate verification."""
import concurrent.futures, datetime, hashlib, json, pathlib, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parent

def fetch(name,url):
    path=ROOT/name
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    p=subprocess.run(['curl','--location','--fail','--silent','--show-error','--connect-timeout','20','--max-time','180','--dump-header',str(path)+'.headers','--output',str(path),'--write-out','%{json}',url],capture_output=True,text=True)
    record=dict(file=name,url=url,started_utc=started,retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),curl_exit_code=p.returncode,tls_verification='curl default; no insecure override',error=p.stderr)
    try: record['http']=json.loads(p.stdout)
    except ValueError: record['curl_stdout']=p.stdout
    if path.exists():record.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if path.exists() and path.stat().st_size>=40*1024**2:
        parts=[]
        with path.open('rb') as inp:
            while b:=inp.read(24*1024**2):
                partname=f'{name}.part{len(parts)+1:02d}';(ROOT/partname).write_bytes(b);parts.append(dict(file=partname,bytes=len(b),sha256=hashlib.sha256(b).hexdigest()))
        partrecord=dict(original_file=name,original_sha256=record['sha256'],parts=parts)
        (ROOT/(name.replace('.zip','')+'-parts.json')).write_text(json.dumps(partrecord,indent=2)+'\n')
        record['preserved_in_parts']=parts;path.unlink()
    h=pathlib.Path(str(path)+'.headers')
    if h.exists(): record['headers_sha256']=hashlib.sha256(h.read_bytes()).hexdigest()
    (ROOT/(name+'.retrieval.json')).write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:record.get(k) for k in ['file','url','curl_exit_code','bytes','sha256']}),flush=True)
    return record

def main():
    args=sys.argv[1:]
    if args==['--refresh']:
        prior=json.loads((ROOT/'manifest.json').read_text());args=[v for r in prior if r['curl_exit_code']==0 for v in [r['file'],r['url']]]
    if len(args)%2:raise SystemExit('collect.py NAME URL [NAME URL ...]')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: records=list(pool.map(lambda p:fetch(*p),zip(args[::2],args[1::2])))
    (ROOT/'manifest.json').write_text(json.dumps([json.loads(p.read_text()) for p in sorted(ROOT.glob('*.retrieval.json'))],indent=2)+'\n')
    assert all(r['curl_exit_code']==0 for r in records)
if __name__=='__main__':main()
