#!/usr/bin/env python3
"""Follow actual county map links; reuse peer bytes by exact hash read-only."""
import concurrent.futures, hashlib, json, pathlib, re
from html.parser import HTMLParser
from urllib.parse import urljoin, unquote
from acquire import ROOT, fetch, body, sha, slug, write_json
STATE=ROOT.parent
PEER=STATE/'data/results-sources'
class Anchors(HTMLParser):
    def __init__(self,base):super().__init__();self.base=base;self.rows=[];self.cur=None
    def handle_starttag(self,t,a):
        if t=='base':
            d=dict(a)
            if d.get('href'):self.base=urljoin(self.base,d['href'])
        if t=='a':
            d=dict(a);self.cur={'href_literal':d.get('href',''),'url':urljoin(self.base,d.get('href','')),'text':'','position':len(self.rows)+1}
    def handle_data(self,s):
        if self.cur is not None:self.cur['text']+=s
    def handle_endtag(self,t):
        if t=='a' and self.cur:
            self.cur['text']=' '.join(self.cur['text'].split());self.rows.append(self.cur);self.cur=None
def anchors(m):
    p=Anchors(m.get('final_url',m['requested_url']));p.feed(body(m).decode('utf-8','replace'));return p.rows
def main():
    ledger=json.loads((PEER/'acquisition-ledger.json').read_text()); peerurls={}
    for x in ledger:
        if x.get('status')==200:
            peerurls[x['url']]=x;peerurls[x.get('final_url',x['url'])]=x
    deps={}; discoveries=[];counties=json.loads((STATE/'data/turnout/priority-set.json').read_text())['all_counties']
    def pin(p):deps[str(p.relative_to(STATE))]=dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
    pin(PEER/'auditor-directory.json')
    def get(k,u,parent,county,label):
        # Pin original object rather than duplicating peer downloads.
        if u in peerurls:
            x=peerurls[u];paths=x['parts'];stored=x['stored_objects']
            b=b''.join((PEER/p).read_bytes() for p in paths)
            import gzip
            raw=gzip.decompress(b)
            assert sha(raw)==x['original_sha256']
            for p,o in zip(paths,stored):
                pp=PEER/p;assert sha(pp.read_bytes())==o['sha256'];pin(pp)
            m=dict(source_id=k,requested_url=u,final_url=x['final_url'],parent_authority_url=parent,county=county,link_label=label,kind='county-authority',status=200,retrieval_utc=x['retrieval_utc'],headers=x['headers'],redirects=x['redirects'],entity_sha256=x['original_sha256'],entity_bytes=x['original_bytes'],stored_encoding='gzip',stored_sha256=sha(b),stored_bytes=len(b),peer_source_id=x['id'],peer_reuse=True)
            if len(paths)==1:m['path']='../data/results-sources/'+paths[0]
            else:m['parts']=[dict(path='../data/results-sources/'+p,sha256=sha((PEER/p).read_bytes()),bytes=(PEER/p).stat().st_size) for p in paths]
            write_json(ROOT/'raw'/f'{k}.meta.json',m);return m
        return fetch(k,u,parent,kind='county-authority',county=county,link_label=label)
    targets=[]
    for c in counties[:41]:
        candidates=[]
        for f in sorted((PEER/'extracts').glob('county-'+c['county_fips']+'-*.json')):
            d=json.loads(f.read_text());hits=[]
            for l in d.get('links',[]):
                t=' '.join(l.get('text','').split());u=l['url']; both=t+' '+u
                if not re.search(r'precinct|\bmaps\b|voting.map',both,re.I):continue
                if re.search(r'official|google|goo\.gl|maps\.apple|maps.live|sample|pollworker|house|senate|supervisor|walking|road.map|plat.book|school|district.result|by.party|registration|registered.voter|\.xlsx|test\.sos',both,re.I):continue
                if not u.startswith('https://'):continue
                hits.append(dict(county=c['county'],county_fips=c['county_fips'],peer_extract=str(f.relative_to(STATE)),peer_link=l))
                if u not in [a['url'] for a in candidates]:candidates.append({'url':u,'text':t})
            if hits:pin(f);discoveries.extend(hits)
        # Strong election map pages first; keep precise observed routes, no guessed county APIs.
        candidates.sort(key=lambda x:(not bool(re.search(r'election.maps|/vote/maps|/auditor/maps|voting.maps',x['url'])),not bool(re.search(r'^maps$|election maps|voting maps',x['text'],re.I))))
        for i,l in enumerate(candidates[:3]):targets.append((c,l,i))
    def land(t):
        c,l,i=t;return get(f"local-{c['county_fips']}-map-page-{i+1}",l['url'],next(d['directory_url'] for d in json.loads((PEER/'auditor-directory.json').read_text()) if d['county_fips']==c['county_fips']),c['county'],l['text'])
    # Sequential peer reuse updates shared deps; bounded requests parallel below for leaves.
    pages=[land(t) for t in targets]
    leaves=[];seen=set()
    for m in pages:
        if m.get('status')!=200 or not m.get('path','').endswith('.gz'):continue
        aa=anchors(m);selected=[]
        for a in aa:
            both=a['text']+' '+a['url']
            ispdf=bool(re.search(r'\.pdf(?:$|\?)|/DocumentCenter/View/|docview\.aspx|viewfile\.aspx',a['url'],re.I))
            if not ispdf or not re.search(r'precinct|ward|county.?wide|map.of.voting',both,re.I):continue
            if re.search(r'school|supervisor|house|senate|congress|result|population|descriptions|primary|registered|safety',both,re.I):continue
            selected.append(a)
        selected.sort(key=lambda a:not bool(re.search(r'county.?wide|county.precinct|all.precinct|map.of.voting',a['text']+' '+a['url'],re.I)))
        for a in selected[:6]:
            if a['url'] in seen:continue
            seen.add(a['url']);leaves.append((m,a))
    extras=[('polk-wall-precinct-map','https://www.polkcountyiowa.gov/media/wrhjbkg0/polk.pdf','polk-election-maps','Polk','Countywide precinct wall map'),('polk-all-precincts-dsm-wdm','https://www.polkcountyiowa.gov/media/4fobodot/all-precincts-dsm-wdm.zip','polk-election-maps','Polk','All precincts Des Moines & West Des Moines'),('polk-all-precincts-other','https://www.polkcountyiowa.gov/media/screthra/all-precincts-all-others.zip','polk-election-maps','Polk','All other precincts'),('johnson-countywide-map','https://johnsoncountyiowa.gov/sites/default/files/Elections/CountywidePrecincts.pdf','johnson-polling-places','Johnson','Countywide precinct map')]
    for k,u,parent,county,label in extras:
        pm=json.loads((ROOT/'raw'/f'{parent}.meta.json').read_text())
        assert u in [a['url'] for a in anchors(pm)]
        get(k,u,pm['final_url'],county,label)
    def leaf(t):
        m,a=t;k='local-'+slug(m.get('county','unknown'))+'-'+sha(a['url'].encode())[:12]
        return fetch(k,a['url'],m['final_url'],kind='county-map-asset',county=m.get('county'),link_label=a['text'],source_link_position=a['position'],approval_status='not established by this retrieval')
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:res=list(pool.map(leaf,leaves))
    write_json(ROOT/'local-map-discoveries.json',discoveries)
    # The peer ledger is mutable during research: pin only exact reused records, not entire changing ledger.
    write_json(ROOT/'peer-dependencies.json',deps)
    write_json(ROOT/'source-manifest.json',dict(schema_version=1,records=[json.loads(p.read_text()) for p in sorted((ROOT/'raw').glob('*.meta.json'))]))
    print(json.dumps(dict(pages=len(pages),assets=len(res),asset_statuses=dict(__import__('collections').Counter(str(x.get('status')) for x in res)),peer_dependencies=len(deps))))
if __name__=='__main__':main()
