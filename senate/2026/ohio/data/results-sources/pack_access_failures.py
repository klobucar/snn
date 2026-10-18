#!/usr/bin/env python3
"""Losslessly co-compress repetitive access-challenge originals, preserving each request.

Tar members contain exact decoded HTTP response-body bytes, not normalized HTML.
The LZMA dictionary shares repeated challenge-page artwork across original bodies.
Each metadata record retains original SHA256, its member, and shared archive SHA256.
"""
import gzip, hashlib, io, json, pathlib, tarfile
P=pathlib.Path(__file__).resolve().parent
def main():
    entries=[]
    for f in sorted(P.glob('*.meta.json')):
        m=json.loads(f.read_text())
        if m.get('archive_member'):continue
        if m['transport'].get('http_code')==403 and m['original_bytes']>1000000:
            b=gzip.decompress((P/m['body']).read_bytes())
            assert hashlib.sha256(b).hexdigest()==m['original_sha256']
            entries.append((f,m,b))
    if not entries:return
    archive=P/'access-challenge-originals.tar.xz'
    suffix=2
    while archive.exists():
        archive=P/('access-challenge-originals-'+str(suffix).zfill(3)+'.tar.xz');suffix+=1
    with tarfile.open(archive,'w:xz',preset=6) as t:
        for f,m,b in entries:
            member=m['id']+'.body';info=tarfile.TarInfo(member);info.size=len(b);info.mtime=0;info.mode=0o644;t.addfile(info,io.BytesIO(b))
    assert archive.stat().st_size<40*1024*1024
    ah=hashlib.sha256(archive.read_bytes()).hexdigest()
    with tarfile.open(archive,'r:xz') as t:
        for f,m,b in entries:assert t.extractfile(m['id']+'.body').read()==b
    for f,m,b in entries:
        old=P/m['body'];m['initial_individual_gzip_sha256']=m['stored_sha256'];m['body']=archive.name;m['archive_member']=m['id']+'.body';m['stored_sha256']=ah;m['storage']='lossless exact response body tar member in shared XZ archive'
        f.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n');old.unlink()
    print(json.dumps({'exact_originals':len(entries),'original_bytes':sum(len(b) for _,_,b in entries),'shared_archive_bytes':archive.stat().st_size,'archive_sha256':ah},indent=2))
if __name__=='__main__':main()
