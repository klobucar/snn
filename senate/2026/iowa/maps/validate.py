#!/usr/bin/env python3
"""Independent offline checks of bytes, full native derivatives and conserved scopes."""
import collections,csv,gzip,hashlib,html,io,json,pathlib,re,urllib.parse,zipfile
from html.parser import HTMLParser
import shapefile
from acquire import ROOT,body,sha,write_json
from build import CONTRACT_SHA,KEY_SHA
STATE=ROOT.parent
class LocalLinks(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,t,a):
        d=dict(a)
        if d.get('id'):self.ids.append(d['id'])
        for k in ['href','src']:
            if d.get(k):self.links.append(d[k])
def main():
    errors=[];checks={}
    def check(name,value,details=None):
        checks[name]=dict(pass_=bool(value),details=details)
        if not value:errors.append(name)
    contract=STATE/'data/turnout/priority-set.json';raw=contract.read_bytes();c=json.loads(raw);cc=c['all_counties']
    check('final_contract_exact_hash_and_bytes',sha(raw)==CONTRACT_SHA and len(raw)==9106895)
    keys=(STATE/'data/coordinator-priority-keys.txt').read_bytes()
    check('exact41_ordered_key_bytes',sha(keys)==KEY_SHA and keys.decode().splitlines()==['IA:'+x['county_fips'] for x in cc[:41]])
    inv=json.loads((ROOT/'inventory/counties.json').read_text())
    check('all99_order_and_fips',[(x['county'],x['county_fips'],x['rank']) for x in inv]==[(x['county'],x['county_fips'],x['rank_2024']) for x in cc] and len(set(x['county_fips'] for x in inv))==99)
    with (STATE/'data/county-turnout.csv').open() as f:turnout=list(csv.DictReader(f))
    check('all99_county_turnout_order_and_marks',[(x['county_fips'],int(x['pres2024_candidate_generic_writein_votes'])) for x in turnout]==[(x['county_fips'],x['pres2024_candidate_generic_writein_votes']) for x in cc])
    diag=json.loads(gzip.decompress((ROOT/'inventory/constituent-diagnostics.json.gz').read_bytes()))['ordered_exact_source_constituents']
    expected=[(x['county_fips'],y,k,i+1,o) for x in cc for y,contexts in x['native_constituents'].items() for k,v in contexts.items() if isinstance(v,list) for i,o in enumerate(v)]
    actual=[(x['county_fips'],x['year'],x['context'],x['context_ordinal'],x['original_constituent']) for x in diag]
    check('all13558_exact_objects_keys_scopes_order',actual==expected and len(actual)==13558)
    check('all99_exact_native_rosters',[x['native_source_roster'] for x in inv]==[x['native_constituents']['2024']['native_source_roster'] for x in cc])
    check('administrative_exceptions',sum(x['diagnostic_status']=='administrative-no-polygon' for x in diag)==297 and all(x['diagnostic_status']=='administrative-no-polygon' for x in diag if x['context']=='candidate_administrative_controls'))
    lucas=next(x for x in cc if x['county']=='Lucas')['native_constituents']['2024']
    check('lucas_7_candidate_5_turnout_7_status',len(lucas['candidate_reporting_units'])==7 and len(lucas['turnout_context_units'])==5 and len(lucas['status_context_units'])==7)
    check('root_turnout_blank_contest_keys',all(x['original_constituent']['source_contest_key']=='' for x in diag if x['context']=='turnout_context_units'))
    check('no_approved_crosswalk_or_allocation',all(not x['approved_polygon_matches'] and x['vote_allocation'] is None for x in diag))
    check('priority41_has_actual_reference_assets',all(x['accepted_reference_asset_ids'] and x.get('index_preview') and (ROOT/x['index_preview']).exists() and x.get('index_download') and (ROOT/x['index_download']).exists() for x in inv[:41]))
    counts={}
    for name in ['read-only-pins.json','peer-dependencies.json']:
        pin=json.loads((ROOT/name).read_text());bad=[]
        for path,d in pin.items():
            p=STATE/path
            if not p.exists() or p.stat().st_size!=d['bytes'] or sha(p.read_bytes())!=d['sha256']:bad.append(path)
        check('dependency_hashes_'+name,not bad,bad);counts[name]=len(pin)
    records=json.loads((ROOT/'source-manifest.json').read_text())['records'];bad=[];parts=0;responses=0
    for m in records:
        if not m.get('entity_sha256'):continue
        try:
            b=body(m);responses+=1
            if len(b)!=m['entity_bytes'] or sha(b)!=m['entity_sha256']:bad.append(m['source_id']+':entity')
            if m.get('path'):
                st=(ROOT/m['path']).read_bytes()
                if sha(st)!=m['stored_sha256'] or len(st)!=m['stored_bytes']:bad.append(m['source_id']+':stored')
            else:
                digest=hashlib.sha256();n=0
                for p in m['parts']:
                    piece=(ROOT/p['path']).read_bytes();parts+=1;digest.update(piece);n+=len(piece)
                    if sha(piece)!=p['sha256'] or len(piece)!=p['bytes'] or len(piece)>=40000000:bad.append(m['source_id']+':part')
                if digest.hexdigest()!=m['stored_sha256'] or n!=m['stored_bytes']:bad.append(m['source_id']+':reconstruction')
        except Exception as e:bad.append(m['source_id']+':'+str(e))
    check('all_original_bytes_headers_split_reconstruction',not bad,bad);counts.update(responses_verified=responses,split_parts=parts)
    audits=json.loads((ROOT/'geometry-audit.json').read_text())['archives'];bad=[];nfeatures=0;nvertices=0
    mm={m['source_id']:m for m in records}
    for a in audits:
        if a.get('error'):bad.append(a);continue
        z=zipfile.ZipFile(io.BytesIO(body(mm[a['source_id']])));ns={n.lower():n for n in z.namelist()}
        if z.testzip():bad.append(a['source_id']+':CRC')
        for l in a.get('layers',[]):
            base=l['shp_member'][:-4];r=shapefile.Reader(**{e:io.BytesIO(z.read(ns[(base+'.'+e).lower()])) for e in ['shp','shx','dbf']},encoding=l['dbf_encoding'],encodingErrors='strict')
            native=json.loads(gzip.decompress((ROOT/l['native_derivative']).read_bytes()))['features']
            if not l['record_balance'] or len(native)!=len(r):bad.append(l['layer_key']+':count')
            for sr,f in zip(r.iterShapeRecords(),native):
                s=sr.shape;nfeatures+=1;nvertices+=len(s.points)
                if [list(p) for p in s.points]!=f['points'] or list(s.parts)!=f['parts'] or sr.record.as_dict()!=f['attributes'] or (list(s.z) if hasattr(s,'z') else None)!=f['z'] or (list(s.m) if hasattr(s,'m') else None)!=f['m']:bad.append(l['layer_key']+':native content')
    check('all_zip_crc_native_attributes_vertices_parts_z_m',not bad,bad);counts.update(native_features_verified=nfeatures,native_vertices_verified=nvertices,layers=sum(len(a['layers']) for a in audits),zip_archives=len(audits))
    pdfs=json.loads((ROOT/'pdf-audit.json').read_text())['sources'];bad=[];npdf=0;npage=0
    import fitz
    for p in pdfs:
        if p.get('error'):bad.append(p);continue
        m=mm[p['source_id']];b=body(m);z=zipfile.ZipFile(io.BytesIO(b)) if b[:2]==b'PK' else None
        if z and z.testzip():bad.append(p['source_id']+':CRC')
        for d in p['documents']:
            docbytes=z.read(d['archive_member']) if z else b
            doc=fitz.open(stream=docbytes,filetype='pdf');npdf+=1;npage+=len(doc)
            if sha(docbytes)!=d['original_sha256'] or len(docbytes)!=d['original_bytes'] or len(doc)!=d['page_count']:bad.append(d['pdf_key'])
            if not d['first_page_preview'] or not (ROOT/d['first_page_preview']).exists():bad.append(d['pdf_key']+':preview')
        if not p['contact_sheets'] or not all((ROOT/x).exists() for x in p['contact_sheets']):bad.append(p['source_id']+':contact sheets')
    check('all_pdf_original_member_hashes_pages_renders',not bad,bad);counts.update(pdf_documents=npdf,pdf_pages=npage)
    broken=[];files=[ROOT/'index.html']+list((ROOT/'counties').glob('*.html'))
    for f in files:
        p=LocalLinks();p.feed(f.read_text())
        for link in p.links:
            u=urllib.parse.urlsplit(link)
            if u.scheme or u.netloc or not u.path:continue
            target=(f.parent/urllib.parse.unquote(u.path)).resolve()
            if not target.exists():broken.append(dict(file=str(f.relative_to(ROOT)),link=link))
    report=STATE/'precinct-maps.md'
    for label,link in re.findall(r'\[([^\]]*)\]\(([^)]+)\)',report.read_text()):
        u=urllib.parse.urlsplit(link)
        target=report.parent/urllib.parse.unquote(u.path)
        # These two declared outputs are emitted below, then explicitly checked.
        if not u.scheme and u.path and not target.exists() and target.resolve() not in [(ROOT/'validation.json').resolve(),(ROOT/'asset-hashes.json').resolve()]:broken.append(dict(file='precinct-maps.md',link=link))
    check('all_offline_html_and_report_markdown_links',not broken,broken)
    owned=[f for f in ROOT.rglob('*') if f.is_file()]+[report]
    too_big=[dict(path=str(f.relative_to(STATE)),bytes=f.stat().st_size) for f in owned if f.stat().st_size>=40000000]
    check('strict_all_objects_below40000000',not too_big,too_big)
    check('no_dependency_or_cache_directories',not any(p.is_dir() and p.name in ['node_modules','__pycache__','.cache','.venv','venv'] for p in ROOT.rglob('*')))
    out=dict(status='pass_with_retained_source_defects_and_unapproved_crosswalks' if not errors else 'fail',checks=checks,counts=counts,errors=errors,scope='Research assets only; no approved current crosswalk, allocation, live collection or forecast claim.')
    write_json(ROOT/'validation.json',out)
    # Deliberately excludes itself and validation report to avoid hash cycles; validation checks bytes directly.
    assets=[dict(path=str(f.relative_to(STATE)),bytes=f.stat().st_size,sha256=sha(f.read_bytes())) for f in sorted(owned) if f.name not in ['asset-hashes.json','validation.json']]
    write_json(ROOT/'asset-hashes.json',dict(schema_version=1,excluded=['maps/asset-hashes.json','maps/validation.json'],assets=assets))
    assert (ROOT/'validation.json').is_file() and (ROOT/'asset-hashes.json').is_file()
    assert (ROOT/'validation.json').stat().st_size<40000000 and (ROOT/'asset-hashes.json').stat().st_size<40000000
    print(json.dumps(dict(status=out['status'],errors=errors,counts=counts,assets=len(assets))))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
