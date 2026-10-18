#!/usr/bin/env python3
"""Fetch exact retained URLs into a NEW directory; never overwrite archived sources.
This replays known downloads, not an election collector; results may change.
"""
import argparse,json
from pathlib import Path
import acquire
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-id',required=True);p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args()
 original_root=acquire.ROOT;d=json.loads((original_root/'sources'/(a.source_id+'.json')).read_text())
 assert not a.output_dir.exists(),'Use a new output directory to preserve prior observations.'
 a.output_dir.mkdir(parents=True);acquire.ROOT=a.output_dir
 out=acquire.fetch(a.source_id,d['requested_url'],d.get('parent_source_url'))
 print(json.dumps(dict(source_id=a.source_id,status=out.get('status'),original_sha256=out.get('original_sha256'),matches_archived_entity=out.get('original_sha256')==d.get('original_sha256'),error=out.get('error')),indent=2))
if __name__=='__main__':main()
