#!/usr/bin/env python3
"""Recover observed PDF.js target URLs and a literal HTML base URL, no guesses."""
import json,re
from urllib.parse import parse_qs,urlsplit,urljoin
from acquire import ROOT,fetch,body,sha
from local_acquire import anchors
def main():
    for i in [1,2]:
        m=json.loads((ROOT/'raw'/f'local-19121-map-page-{i}.meta.json').read_text())
        target=parse_qs(urlsplit(m['final_url']).query)['file'][0]
        u=urljoin(m['final_url'],target)
        r=fetch('madison-observed-pdf-'+str(i),u,m['final_url'],kind='county-map-asset',county='Madison',link_label='Approved Madison County Election Precincts' if i==1 else 'Madison County Precinct Locations 2026 General Election',discovery='literal PDF.js viewer file parameter; not guessed API')
        print(r['source_id'],r.get('status'),r.get('entity_bytes'))
    m=json.loads((ROOT/'raw'/'local-19019-map-page-2.meta.json').read_text())
    assert 'base href="https://www.buchanancounty.iowa.gov/"' in body(m).decode('utf-8','replace')
    aa=[a for a in anchors(m) if '.pdf' in a['url'].lower() and re.search(r'precinct',a['text']+' '+a['url'],re.I)]
    for a in aa[:6]:
        r=fetch('buchanan-base-link-'+sha(a['url'].encode())[:10],a['url'],m['final_url'],kind='county-map-asset',county='Buchanan',link_label=a['text'],discovery='literal href resolved using actual HTML base element; earlier broken relative route retained')
        print(r['source_id'],r.get('status'),r.get('entity_bytes'))
if __name__=='__main__':main()
