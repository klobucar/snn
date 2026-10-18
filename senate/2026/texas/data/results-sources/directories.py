#!/usr/bin/env python3
"""Parse actual complete jurisdiction labels, never substring matches."""
import csv,html,json,re
from fetch import ROOT,read
from inspect_html import page
TX=ROOT.parents[1]
def norm(s):return ' '.join(s.upper().split())
def plain(s):return ' '.join(html.unescape(re.sub('<[^>]*>',' ',s)).split())
def derive():
    rows=list(csv.DictReader((TX/'data/county-turnout.csv').open()))
    links={norm(x['text']):x['url'] for x in page('sos-county-links').links};officials={}
    for dl in re.findall(r'<dl\b[^>]*>(.*?)</dl>',read('sos-county-officials').decode(),re.S|re.I):
        dt=re.search(r'<dt\b[^>]*>(.*?)</dt>',dl,re.S|re.I)
        if dt:officials[norm(plain(dt[1]))]=[plain(x) for x in re.findall(r'<dd\b[^>]*>(.*?)</dd>',dl,re.S|re.I)]
    src=json.loads((TX/'data/turnout/county-source-links.json').read_text());peer={}
    for z in src[1:]:
        name=next((v for k,v in z.items() if re.fullmatch('A[0-9]+',k)),None)
        if name:peer[norm(name)]=z
    out=[];pr=[]
    for r in rows:
        label=norm(r['county']+' County');alias={'LASALLE COUNTY':'LA SALLE COUNTY','DEWITT COUNTY':'DE WITT COUNTY'}.get(label,label)
        dd=officials.get(label,officials.get(alias));assert dd,label
        out.append(dict(dispatch_key=r['dispatch_key'],county_fips=r['county_fips'],county=r['county'],rank=int(r['rank']),priority=r['priority80']=='1',directory_label=label if label in officials else alias,authority_role=dd[0],authority_name=dd[1],directory_source='sos-county-officials',publication_directory_source='sos-county-links',official_directory_url=links.get(label,links.get(alias)),scope='priority_authority_inventory; see individual priority record' if r['priority80']=='1' else 'discovery_inventory_only',gap='Directory identifies office/site, not current November county/vendor or native-unit completeness.'))
        n=norm(r['county']);a={'LASALLE':'LA SALLE','DEWITT':'DE WITT'}.get(n,n)
        pr.append(dict(dispatch_key=r['dispatch_key'],county=r['county'],peer_directory_record=peer.get(a,peer.get(n,{})),scope='historical derivative source-list discovery; official affiliation/current availability separately verified'))
    return out,pr
if __name__=='__main__':
    a,b=derive()
    for fn,x in [('county-discovery.json',a),('peer-county-routes.json',b)]:(ROOT/fn).write_text(json.dumps(x,indent=2)+'\n')
    print(json.dumps(dict(counties=len(a),officials=sum(bool(x['authority_role']) for x in a),SOS_website_anchors=sum(bool(x['official_directory_url']) for x in a))))
