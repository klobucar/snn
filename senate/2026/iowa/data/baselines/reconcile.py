#!/usr/bin/env python3
"""Full read-only peer comparison; documented aliases are format/scope only."""
import collections,csv,json,re
from common import *
def peer(name):
    with (TURNOUT/name).open() as f:return list(csv.DictReader(f))
def compare(a,b,key,fields,aliases=None):
    ma={key(r):r for r in a};mb={key(r):r for r in b}
    assert len(ma)==len(a) and len(mb)==len(b),'duplicate comparison key'
    diffs=[]
    for k in sorted(set(ma)|set(mb)):
        if k not in ma or k not in mb:diffs.append({'key':k,'missing':'ours' if k not in ma else 'peer'});continue
        for own,other in fields:
            av=ma[k].get(own,'');bv=mb[k].get(other,'')
            if aliases:av,bv=aliases(own,av,bv)
            if av!=bv:diffs.append({'key':k,'field':own,'ours':av,'peer':bv})
    return {'our_rows':len(a),'peer_rows':len(b),'differences':diffs,'status':'pass' if not diffs else 'disagreement'}
def main():
    result={'scope':'independently extracted raw originals compared read-only; no cross-year/2026 crosswalk approval','aliases':['State footer blank county FIPS in ours maps to peer state19.','Full candidate header=our candidate label + comma + party when printed.','Scott PDF sheet display aliases map to one retained original; numeric source_row is same contest-section text line; Total and Total: designate administrative footer.','Native workbook key exact source/sheet/row/column; no unit-label deduplication.']}
    own=records('canvass-candidate-method.csv');other=peer('canvass-candidate-method.csv')
    key=lambda r:(r['year'],r['county_fips'] or '19',r['native_method'],r['source_id'],r['source_column'])
    def labels(field,av,bv):return (av,bv)
    for r in own:
        if r['party_header']:r['candidate_or_metric_label']+=', '+r['party_header']
    def textalias(field,av,bv):
        if field=='raw_line':av=re.sub(r'Page\s+\d+\s+of\s+\d+.*$','',av)
        return av,bv
    result['aliases'].append('Our raw_line retains embedded complete pagination labels; peer removed these before storage. Comparison removes only complete Page N of N suffixes; originals retained.')
    result['canvass_all_cells']=compare(own,other,key,[('votes','votes'),('candidate_or_metric_label','candidate_or_metric_label'),('raw_line','raw_line'),('section_text_line','section_text_line')],textalias)
    mine=records('priority-order.csv');priority=json.loads((TURNOUT/'priority-set.json').read_text());theirs=priority['all_counties']
    result['full_priority_order']=compare(mine,[{k:str(v) for k,v in r.items()} for r in theirs],lambda r:r.get('rank',r.get('rank_2024')),[('county','county'),('county_fips','county_fips'),('candidate_writein_votes','pres2024_candidate_generic_writein_votes'),('cumulative_votes','cumulative_candidate_generic_writein_votes'),('priority80','in_minimum80')])
    result['priority_summary']={'our':json.loads((ROOT/'priority.json').read_text()),'peer_threshold':priority['threshold'],'peer_denominator':priority['baseline']['denominator']}
    own=records('native-candidate-method.csv');other=peer('native-unit-candidate-method.csv')
    own=[r for r in own if r['metric'] not in ['registered_voters','candidate_sheet_total']]
    def nkey(r):return (r['source_id'],'PDF Senate' if r['source_id'].endswith('scott.pdf') else r.get('sheet',r.get('source_sheet')),r['source_row'],r['source_column'])
    def normalize(field,av,bv):
        if field=='native_unit_label' and av in ('Total:','Total') and bv in ('Total:','Total'):av=bv='Total'
        if field=='native_candidate_label':
            av={'Under Votes':'Undervotes','Over Votes':'Overvotes'}.get(av,av)
        return av,bv
    result['native_candidate_cells']=compare(own,other,nkey,[('year','year'),('county','county'),('county_fips','county_fips'),('native_unit_label','native_unit_label'),('native_candidate_label','native_candidate_label'),('native_method','native_method'),('votes','votes')],normalize)
    ours=records('native-units.csv');other=peer('native-units.csv')
    result['native_unit_rows']=compare(ours,other,lambda r:(r['source_id'],'PDF Senate' if r['source_id'].endswith('scott.pdf') else r.get('sheet',r.get('source_sheet')),r['source_row']),[('year','year'),('county_fips','county_fips'),('native_unit_label','native_unit_label'),('native_unit_numeric_id','native_unit_numeric_id')],normalize)
    own=records('native-registration-ballots.csv')
    result['native_registration_ballot_cells']=compare(own,peer('native-registration-ballots.csv'),nkey,[('year','year'),('county_fips','county_fips'),('native_unit_label','native_unit_label'),('metric','metric'),('value','value')])
    context=[]
    for r in records('native-candidate-method.csv'):
        if r['metric'] in ['registered_voters','candidate_sheet_total']:
            context.append(r|{'native_metric':'Registered Voters' if r['metric']=='registered_voters' else 'Total','value':r['votes']})
    result['native_candidate_sheet_context_cells']=compare(context,peer('native-candidate-sheet-context.csv'),nkey,[('year','year'),('county','county'),('county_fips','county_fips'),('native_unit_label','native_unit_label'),('native_metric','native_metric'),('value','value')])
    own=records('turnout-report.csv');other=peer('turnout-report-counties.csv')
    fields=[(x,x) for x in ['election_day_voters','absentee_voters','total_voters','active_registered','inactive_registered','registration_as_of','published_active_turnout_pct','published_total_turnout_pct']]
    result['turnout_report_fields']=compare(own,other,lambda r:(r['year'],r['county_fips']),fields)
    clarity_files=['clarity-2024-native-candidate-method.csv','clarity-2024-county-candidate-method.csv','clarity-2024-native-units.csv','clarity-2024-registration-ballots.csv','clarity-2024-status-units.csv']
    for name in clarity_files:
        own=records(name);other=peer(name)
        if 'native-candidate' in name:key=lambda r:(r['source_id'],r['source_xml_path'])
        elif 'county-candidate' in name:key=lambda r:(r['source_id'],r['native_choice_key'],r['native_method'])
        elif 'registration-ballots' in name:
            key=lambda r:(r['source_id'],r['source_xml_path'])
            for r in own:
                if r['source_xml_path']=='VoterTurnout':r['unit_key']='';r['native_unit_label']='';r['source_scope']='county_administrative_control'
        else:key=lambda r:r['unit_key']
        shared=[(k,k) for k in own[0] if k in other[0] and k!='unit_kind']
        result[name.removesuffix('.csv')]=compare(own,other,key,shared)
    result['aliases'].append('2024 XML county VoterTurnout control is keyed by source_id+XML path: our explicit administrative unit key/county label maps to peer blank unit key/label and county_administrative_control scope. Constituent context keys match exactly. unit_kind is a worker-authored description, not a primary identity field; all actual XML identity/clock fields compared.')
    result['peer_artifact_hashes']=[{'path':'../turnout/'+f,'sha256':sha((TURNOUT/f).read_bytes()),'bytes':(TURNOUT/f).stat().st_size} for f in ['SCHEMA.md','canvass-candidate-method.csv','priority-set.json','native-units.csv','native-unit-candidate-method.csv','native-registration-ballots.csv','native-candidate-sheet-context.csv','turnout-report-counties.csv']+clarity_files]
    result['status']='pass' if all(v.get('status')=='pass' for v in result.values() if isinstance(v,dict) and 'status' in v) else 'disagreement'
    dump('peer-reconciliation.json',result)
    print({k:(v['status'],len(v.get('differences',[]))) for k,v in result.items() if isinstance(v,dict) and 'status' in v})
if __name__=='__main__':main()
