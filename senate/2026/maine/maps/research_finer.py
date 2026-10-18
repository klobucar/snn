#!/usr/bin/env python3
"""Read-only reuse of official-results captured municipal pages for map discovery.

No source-worker files or state arithmetic are modified. Explicit map links only;
registration W/P labels are investigation triggers, not polygon crosswalks.
"""
import json,gzip,re
from acquire import ROOT,digest
from discover import links
STATE=ROOT.parent;EXT=STATE/'data/results-sources'
def run():
    units=json.loads((STATE/'data/turnout/priority-set.json').read_text())['priority']
    inspections={x['native_key']:x for x in json.loads((EXT/'priority-inspections.json').read_text())}
    municipal=json.loads((ROOT/'municipal-sources.json').read_text());byname={x['unit']:x for x in municipal}
    out=[];gis=json.loads((ROOT/'gis-downloads.json').read_text())
    for u in units:
        historical=sorted({x['ward_precinct'] for x in u['registration_constituents']})
        ins=inspections.get(u['native_key'],{});observed=[];sources=[];seen=set()
        for key in ins.get('pages',[]):
            p=EXT/'requests'/(key+'.json')
            if not p.exists():continue
            r=json.loads(p.read_text())
            if not r.get('body_path'):continue
            bodyfile=EXT/r['body_path']
            if not bodyfile.exists():continue
            b=gzip.decompress(bodyfile.read_bytes()) if str(bodyfile).endswith('.gz') else bodyfile.read_bytes()
            if r.get('status')!=200 or not b.lstrip().startswith((b'<!',b'<html',b'<HTML')):continue
            sources.append({'request_id':key,'metadata_path':'../data/results-sources/requests/'+key+'.json','url':r.get('final_url',r.get('request_url')),'original_sha256':digest(b)})
            for t,h in links(b,r.get('final_url',r.get('request_url'))):
                if h in seen:continue
                if ('map' in (t+' '+h).lower() and any(w in (t+' '+h).lower() for w in ['ward','precinct','district','redistrict'])):
                    seen.add(h);observed.append({'url':h,'text':t,'parent_request_id':key})
        base=u['native_name'].split('/')[0].strip();local=byname.get(base,{})
        out.append({'native_key':u['native_key'],'rank':u['rank'],'native_name':u['native_name'],'historical_registration_wp':historical,'historical_registration_subdivisions_trigger':len(historical)>1,'warning':'Historical registration tuples are not established election-reporting polygons. Current single voting-place rows do not prove absence of municipal wards.','reused_official_pages':sources,'explicit_finer_map_links':observed,'local_supplement_assets':local.get('assets',[]),'local_finer_gis':('municipal-gis/'+local['id']+'.geojson.gz') if local.get('id') in gis else None,'finer_approved_november_2026':'unestablished'})
    (ROOT/'finer-research.json').write_text(json.dumps(out,indent=2)+'\n')
    for x in out:
        if x['historical_registration_subdivisions_trigger'] and not x['local_supplement_assets'] and not x['local_finer_gis']:
            print(x['rank'],x['native_name'],[(y['text'],y['url']) for y in x['explicit_finer_map_links']])
if __name__=='__main__':run()
