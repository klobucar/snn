#!/usr/bin/env python3
"""Reconstruct one exact original using only stdlib and saved ordered parts."""
import argparse,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('source_id');p.add_argument('output',type=Path);a=p.parse_args()
 d=json.loads((ROOT/'sources'/(a.source_id+'.json')).read_text());chunks=[]
 for part in d['stored_parts']:
  b=(ROOT/part['path']).read_bytes();assert len(b)==part['bytes'] and hashlib.sha256(b).hexdigest()==part['sha256'];chunks.append(b)
 b=b''.join(chunks)
 if d['storage_encoding']=='gzip':b=gzip.decompress(b)
 assert len(b)==d['original_bytes'] and hashlib.sha256(b).hexdigest()==d['original_sha256']
 a.output.write_bytes(b);print(a.output,len(b),d['original_sha256'])
if __name__=='__main__':main()
