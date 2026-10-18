#!/usr/bin/env python3
import hashlib,json,pathlib,argparse
ROOT=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
assets={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in ['asset-hashes.json','.acquisitions.lock']}
p=ROOT.parent/'precinct-maps.md';assets['../precinct-maps.md']={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
if args.check:assert assets==json.loads((ROOT/'asset-hashes.json').read_text());print('All',len(assets),'owned asset hashes pass')
else:
    (ROOT/'asset-hashes.json').write_text(json.dumps(assets,indent=2)+'\n')
    print('Hashed',len(assets),'owned files; max',max(x['bytes'] for x in assets.values()))
