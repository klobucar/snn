#!/usr/bin/env python3
"""Verify and reconstruct a split native archive at an explicit output path.

Example: python3 reconstruct.py polk-all-precincts-dsm-wdm /tmp/polk-dsm-wdm.zip
The output is not stored in this package; do not commit a >=40 MB joined object.
"""
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
key,out=sys.argv[1:]
m=json.loads((ROOT/'raw'/f'{key}.meta.json').read_text())
target=pathlib.Path(out).resolve()
assert not target.is_relative_to(ROOT),'write reconstruction outside package to preserve strict object bounds'
digest=hashlib.sha256();total=0
with target.open('xb') as f:
    for p in m['parts']:
        b=(ROOT/p['path']).read_bytes()
        assert len(b)==p['bytes'] and hashlib.sha256(b).hexdigest()==p['sha256']
        f.write(b);digest.update(b);total+=len(b)
assert total==m['stored_bytes'] and digest.hexdigest()==m['stored_sha256']
print(f'{total} exact original bytes; SHA256 {digest.hexdigest()}')
