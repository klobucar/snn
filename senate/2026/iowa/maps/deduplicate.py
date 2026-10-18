#!/usr/bin/env python3
"""Replace exact duplicate entity storage with verified read-only/canonical refs."""
import gzip, json, os, pathlib
from acquire import ROOT,sha,body,write_json
STATE=ROOT.parent
def main():
    peers={};dependencies=json.loads((ROOT/'peer-dependencies.json').read_text())
    mf=STATE/'data/turnout/source-manifest.json'
    for r in json.loads(mf.read_text()):
        p=(mf.parent/r['path']).resolve() if r.get('path') else None
        if p and p.exists() and r.get('original_sha256'):
            b=p.read_bytes()
            try:raw=gzip.decompress(b)
            except Exception:raw=b
            if sha(raw)==r['original_sha256']:
                peers[sha(raw)]=dict(path=os.path.relpath(p,ROOT),stored_encoding='gzip' if b[:2]==b'\x1f\x8b' else 'identity',stored_sha256=sha(b),stored_bytes=len(b),peer_source_id=r['id'])
    files=sorted((ROOT/'raw').glob('*.meta.json'));metas=[json.loads(f.read_text()) for f in files]
    canon={};oldpaths=[];changes=[]
    for f,m in zip(files,metas):
        if not m.get('path') or not m.get('entity_sha256'):continue
        h=m['entity_sha256'];old=m['path'];ref=peers.get(h) or canon.get(h)
        if ref and ref['path']!=old:
            assert sha(body(m))==h
            m['storage_reuse_note']='Exact entity SHA256 equality verified; original per-request metadata retained. Duplicate payload not stored.'
            m.update(ref);m['peer_reuse']=ref['path'].startswith('../');oldpaths.append(old)
            write_json(f,m);changes.append(dict(source_id=m['source_id'],old_path=old,canonical_path=m['path'],entity_sha256=h))
            if m['peer_reuse']:
                pp=(ROOT/m['path']).resolve();dependencies[str(pp.relative_to(STATE))]=dict(bytes=pp.stat().st_size,sha256=sha(pp.read_bytes()))
        canon[h]={k:m[k] for k in ['path','stored_encoding','stored_sha256','stored_bytes']}
    refs={json.loads(f.read_text()).get('path') for f in files}
    for old in oldpaths:
        p=(ROOT/old).resolve()
        if old not in refs and p.is_relative_to(ROOT) and p.exists():p.unlink()
    write_json(ROOT/'peer-dependencies.json',dependencies)
    prior=json.loads((ROOT/'storage-reuse.json').read_text()) if (ROOT/'storage-reuse.json').exists() else []
    seen={(r['source_id'],r['canonical_path'],r['entity_sha256']) for r in prior}
    write_json(ROOT/'storage-reuse.json',prior+[r for r in changes if (r['source_id'],r['canonical_path'],r['entity_sha256']) not in seen])
    # Audit content does not change; update only storage pointer to the exact same bytes.
    for p in (ROOT/'pdf-audit').glob('*.json'):
        d=json.loads(p.read_text());f=ROOT/'raw'/(d['source_id']+'.meta.json')
        if f.exists():d['source_path']=json.loads(f.read_text()).get('path');write_json(p,d)
    for p in (ROOT/'audit').glob('*.json'):
        d=json.loads(p.read_text());f=ROOT/'raw'/(d['source_id']+'.meta.json')
        if f.exists():d['source_path']=json.loads(f.read_text()).get('path');write_json(p,d)
    print(json.dumps(dict(duplicate_entities_referenced=len(changes),peer_dependencies=len(dependencies))))
if __name__=='__main__':main()
