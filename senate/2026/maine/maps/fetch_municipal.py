#!/usr/bin/env python3
"""Replay known linked municipal map downloads (cached unless --refresh).

This is bounded research acquisition, not a live collector. Preserve a snapshot
before refreshing; some primary sources now fail and those failures are evidence.
"""
import argparse,json
from acquire import fetch,ROOT
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');a=p.parse_args()
    for s in json.loads((ROOT/'municipal-sources.json').read_text()):
        for asset in s.get('assets',[]):
            try:fetch(asset['id'],asset['url'],asset['kind'],s.get('vintage_note',''),refresh=a.refresh)
            except Exception as e:print(asset['id'],str(e))
