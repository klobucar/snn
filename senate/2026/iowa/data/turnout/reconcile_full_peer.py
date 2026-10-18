#!/usr/bin/env python3
"""Read-only reverse comparison to independently extracted peer data, with explicit aliases."""
import csv,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PEER=ROOT.parent/'baselines'
def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def sheet(r):return 'SCOTT-SENATE-PDF' if r['source_id']=='sos-2020-workbook-154-scott.pdf' else r.get('source_sheet',r.get('sheet'))
def label(s):return 'Total' if s in ['Total','Total:'] else s
def compare(name,a,c,key,fields):
    aa={key(r):r for r in a};cc={key(r):r for r in c};assert len(aa)==len(a) and len(cc)==len(c),(name,'duplicate')
    differences=[]
    for k in aa.keys()^cc.keys():differences.append(dict(key=k,type='missing key'))
    for k in aa.keys()&cc.keys():
        for f in fields:
            x=aa[k].get(f,'');y=cc[k].get(f,'')
            if f=='native_unit_label':x=label(x);y=label(y)
            if f=='native_candidate_label' and aa[k]['source_id']=='sos-2020-workbook-154-scott.pdf':
                aliases={'Under Votes':'Undervotes','Over Votes':'Overvotes'};x=aliases.get(x,x);y=aliases.get(y,y)
            if x!=y:differences.append(dict(key=k,field=f,turnout=x,partisanship=y))
    return dict(rows=len(a),peer_rows=len(c),status='pass' if not differences else 'differences',fields=fields,differences=differences)
def main():
    result={'aliases':['Scott sheet display names map only to same original/source section row; native unit key syntax maps by source/sheet/row coordinates.','Scott source metric labels Undervotes/Overvotes map to peer display Under Votes/Over Votes only; no candidate names or counts altered.','Total and Total: map only for administrative footer labels.','State blank FIPS maps to19 only for state footer rows.','2024 root VoterTurnout administrative key/label use source_id/XML path, not worker-authored county control annotation.'],'scope':'all shared source fields, read-only peer extraction; no geography crosswalk approval'}
    shared=['year','county','county_fips','source_id','source_row','source_column','native_unit_label','native_candidate_label','native_method','votes']
    a=read(ROOT/'native-unit-candidate-method.csv');c=[r for r in read(PEER/'native-candidate-method.csv') if r['metric'] in ['candidate_votes','undervotes','overvotes','reported_total']]
    key=lambda r:(r['source_id'],sheet(r),r['source_row'],r['source_column'])
    result['legacy_candidate_method']=compare('legacy',a,c,key,shared)
    result['legacy_unit_rows']=compare('units',read(ROOT/'native-units.csv'),read(PEER/'native-units.csv'),lambda r:(r['source_id'],sheet(r),r['source_row']),['year','county','county_fips','source_id','source_row','native_unit_label'])
    result['legacy_registration_ballots']=compare('registration',read(ROOT/'native-registration-ballots.csv'),read(PEER/'native-registration-ballots.csv'),key,['year','county','county_fips','source_id','source_row','source_column','native_unit_label','metric','value'])
    a=read(ROOT/'native-candidate-sheet-context.csv');c=[r for r in read(PEER/'native-candidate-method.csv') if r['metric'] in ['registered_voters','candidate_sheet_total']]
    c=[dict(r,native_metric=r['native_method'],value=r['votes']) for r in c]
    result['legacy_candidate_sheet_context']=compare('context',a,c,key,['year','county','county_fips','source_id','source_row','source_column','native_unit_label','native_metric','value'])
    keys={
        'clarity-2024-native-candidate-method':['source_id','source_xml_path'],
        'clarity-2024-county-candidate-method':['source_id','source_contest_key','native_choice_key','native_method'],
        'clarity-2024-native-units':['source_id','source_xml_path'],
        'clarity-2024-registration-ballots':['source_id','source_xml_path'],
        'clarity-2024-status-units':['source_id','source_index']}
    for name,keyfields in keys.items():
        aa=read(ROOT/(name+'.csv'));cc=read(PEER/(name+'.csv'));fields=[f for f in aa[0] if f in cc[0] and f!='unit_kind']
        if name=='clarity-2024-registration-ballots':
            for r in cc:
                if r['source_xml_path']=='VoterTurnout':r.update(unit_key='',native_unit_label='',source_scope='county_administrative_control')
        result[name]=compare(name,aa,cc,lambda r:tuple(r[f] for f in keyfields),fields)
    result['status']='pass' if all(v.get('status')=='pass' for v in result.values() if isinstance(v,dict)) else 'differences'
    (ROOT/'full-peer-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:dict(rows=v['rows'],status=v['status'],differences=v['differences'][:3]) if isinstance(v,dict) else v for k,v in result.items()},indent=2))
if __name__=='__main__':main()
