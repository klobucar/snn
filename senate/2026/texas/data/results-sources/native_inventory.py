#!/usr/bin/env python3
"""Offline, lossless source-position inventory. Does not build a crosswalk."""
import base64, collections, csv, gzip, io, json
from fetch import ROOT,read

def write_csv(path,rows,fields):
    s=io.StringIO(newline='');w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows)
    b=s.getvalue().encode();path.write_bytes(gzip.compress(b,mtime=0) if path.suffix=='.gz' else b)

def build():
    obs=[];schemas={}; groups=collections.defaultdict(list)
    def add(sid,fips,election,stage,kind,path,ordinal,nid,row,contest=None):
        r=dict(source_id=sid,county_fips=fips,election_id=election,observation_class=stage,
          unit_kind=kind,source_pointer=path,source_ordinal=ordinal,native_id=str(nid),
          contest_id=contest,raw_row_json=json.dumps(row,ensure_ascii=False,separators=(',',':')))
        obs.append(r);groups[(sid,fips,election,stage,kind,str(nid))].append(r)
    for fips,eid in [('48439','127297'),('48029','127291'),('48141','127348'),('48157','127480'),('48367','126014'),('48027','126390')]:
        settings=json.loads(read('clarity-'+fips+'-electionsettings'))
        detail=settings['settings']['electiondetails'];stage='test_mode_excluded' if detail.get('istestmode')=='1' else 'November_initial_zero' if detail['electiondate']=='11/3/2026' else 'older_election_excluded'
        for suf in ['status','details','vc','vc_status']:
            sid='clarity-'+fips+'-'+suf
            if not (ROOT/'raw'/(sid+'.json')).exists():continue
            x=json.loads(read(sid));schemas[sid]=dict(election_details=detail,websiteupdatedat=settings['websiteupdatedat'],root_fields=list(x) if isinstance(x,dict) else None,body_scope='complete retained entity; test/old exclusions apply')
            if suf=='vc':
                for i,z in enumerate(x):
                    u=z.get('voteCenter',{});add(sid,fips,eid,stage,'vote_center',f'/{i}/voteCenter',i,u.get('idVoteCenter'),z)
            elif suf=='details':
                for ci,z in enumerate(x['Contests']):
                    for i,nid in enumerate(z['P']):
                        row={k:v[i] for k,v in z.items() if isinstance(v,list) and len(v)==len(z['P'])};row['K']=z['K']
                        add(sid,fips,eid,stage,'contest_native_reporting_identity',f'/Contests/{ci}/P/{i}',i,nid,row,z['K'])
            else:
                for i,nid in enumerate(x['P']):
                    row={k:v[i] for k,v in x.items() if isinstance(v,list) and len(v)==len(x['P'])}
                    add(sid,fips,eid,stage,'vote_center_status' if suf=='vc_status' else 'native_reporting_status',f'/P/{i}',i,nid,row)
    for sid in ['harris-reporting','harris-senate-precinct']:
        x=json.loads(read(sid));schemas[sid]=dict(root_fields=list(x),array_lengths={k:len(v) for k,v in x.items() if isinstance(v,list)},body_scope='complete 1126 initial entity; no current geography approval')
        for i,nid in enumerate(x['p']):
            row={k:v[i] for k,v in x.items() if isinstance(v,list) and len(v)==len(x['p'])}
            add(sid,'48201','1126','November_initial_zero','native_reporting_status' if sid=='harris-reporting' else 'contest_native_reporting_identity',f'/p/{i}',i,nid,row,x.get('i'))
    # All native fields in the published CSV, including repeated candidate headers.
    sid='county-48085-result1-sample';b=read(sid).decode('utf-8-sig');rows=list(csv.reader(io.StringIO(b)))
    schemas[sid]=dict(headers=rows[:2],row_count=len(rows),stage='June 13 local runoff, excluded from November',body_scope='complete CSV entity')
    for i,row in enumerate(rows[2:],3):
        if len(row)>2:add(sid,'48085','2026-06-13','older_election_excluded','csv_precinct_label',f'/csv-row/{i}',i,row[1],dict(header_rows=rows[:2],cells=row))
    # Full 546-page original Grayson precinct PDF text. Exclude only the exact
    # normalized report title, not arbitrary words or numeric-looking IDs.
    sid='county-48181-office-follow1-sample'
    text=gzip.decompress((ROOT/(sid+'.txt.gz')).read_bytes()).decode()
    schemas[sid]=dict(stage='March 3 Democratic primary, excluded from November',text_derivative=sid+'.txt.gz',report_title_exclusion='Precinct Summary Results Report OFFICIAL RESULTS',scope='all literal Precinct header labels in all 546 retained PDF text pages; candidate cells remain in complete original/text')
    for pi,p in enumerate(text.split('\f'),1):
        for li,line in enumerate(p.splitlines(),1):
            if line.startswith('Precinct ') and ' '.join(line.split())!='Precinct Summary Results Report OFFICIAL RESULTS':
                add(sid,'48181','2026-03-03','older_election_excluded','pdf_precinct_label',f'/pdf-page/{pi}/line/{li}',pi,line[len('Precinct '):],dict(page=pi,line_number=li,source_line=line))
    fields=['source_id','county_fips','election_id','observation_class','unit_kind','source_pointer','source_ordinal','native_id','contest_id','raw_row_json']
    write_csv(ROOT/'native-unit-observations.csv.gz',obs,fields)
    identities=[]
    for key,rr in groups.items():
        r={k:v for k,v in rr[0].items() if k not in ['raw_row_json','contest_id','source_ordinal']};r['occurrences']=len(rr);r['first_raw_row_json']=rr[0]['raw_row_json'];identities.append(r)
    write_csv(ROOT/'native-unit-identities.csv.gz',identities,list(identities[0]))
    (ROOT/'native-field-schemas.json').write_text(json.dumps(schemas,indent=2,ensure_ascii=False)+'\n')
    counts={sid:dict(observations=sum(r['source_id']==sid for r in obs),literal_identities=sum(r['source_id']==sid for r in identities)) for sid in schemas}
    (ROOT/'native-inventory-summary.json').write_text(json.dumps(dict(observations=len(obs),source_scoped_identities=len(identities),sources=counts,limits='Names and IDs only; no boundary, legal approval, method additivity or cross-source equivalence inferred. Duplicate source positions retained in observations. Complete original bodies control any fields not indexed.'),indent=2)+'\n')
    return counts
if __name__=='__main__': print(json.dumps(build(),indent=2))
