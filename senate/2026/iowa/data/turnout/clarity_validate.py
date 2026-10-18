#!/usr/bin/env python3
"""Reconcile 2024 historical XML/JSON source contexts to canvass, preserving differences."""
import csv,gzip,io,json,zipfile
import xml.etree.ElementTree as E
from collections import Counter,defaultdict
import build as b

def read(n):
    with (b.ROOT/n).open(newline='') as f:return list(csv.DictReader(f))
def xml(r):
    z=zipfile.ZipFile(io.BytesIO(b.raw(r)));assert z.namelist()==['detail.xml'];return E.fromstring(z.read('detail.xml'))
def main():
    can=read('canvass-candidate-method.csv');native=read('clarity-2024-native-candidate-method.csv');controls=read('clarity-2024-county-candidate-method.csv');units=read('clarity-2024-native-units.csv');turnout=read('clarity-2024-registration-ballots.csv');status=read('clarity-2024-status-units.csv')
    cvals={};parties={}
    for r in can:
        if r['year']!='2024' or r['metric'] not in ['named_candidate','generic_writein']:continue
        parts=r['candidate_or_metric_label'].rsplit(', ',1);name=parts[0];party=parts[1] if len(parts)==2 else ''
        cvals[r['county_fips'],r['native_method'],name]=int(r['votes']);parties[name]=party
    diffs=[];party_diffs=[]
    for r in controls:
        expected=cvals[r['county_fips'],r['native_method'],r['native_candidate_label']]
        diffs.append(dict(county=r['county'],county_fips=r['county_fips'],source_id=r['source_id'],native_choice_key=r['native_choice_key'],candidate=r['native_candidate_label'],method=r['native_method'],native_votes=int(r['votes']),canvass_votes=expected,difference=int(r['votes'])-expected))
        if r['party_header']!=parties[r['native_candidate_label']]:party_diffs.append(dict(county=r['county'],county_fips=r['county_fips'],source_id=r['source_id'],candidate=r['native_candidate_label'],method=r['native_method'],county_xml_party=r['party_header'],state_canvass_party=parties[r['native_candidate_label']]))
    assert len(diffs)==2376 and all(r['difference']==0 for r in diffs)
    assert len({(r['source_id'],r['source_xml_path']) for r in native})==len(native)==26448
    assert len({r['unit_key'] for r in units})==len(units)
    candunits=[r for r in units if 'Contest_Precinct' in r['unit_kind']];tu=[r for r in units if 'Contest_Precinct' not in r['unit_kind']]
    sums=defaultdict(int)
    for r in native:sums[r['county_fips'],r['native_candidate_label'],r['native_method']]+=int(r['votes'])
    assert all(sums[r['county_fips'],r['candidate'],r['method']]==r['native_votes'] for r in diffs if r['method']!='Total')
    # State XML all candidate/county rows and JSON totals are separate primary controls.
    root=xml(b.BYID['sos-2024-state-reports-detailxml-zip']);contest=next(c for c in root.findall('Contest') if c.get('text')=='President and Vice President');state_county=[]
    for choice in contest.findall('Choice'):
        name=choice.get('text');assert int(choice.get('totalVotes'))==cvals['19','Total',name]
        for vt in choice.findall('VoteType'):
            method=vt.get('name');assert int(vt.get('votes'))==cvals['19',method,name]
            counties=vt.findall('County');assert len(counties)==99
            for co in counties:
                fips=b.COUNTIES[co.get('name')]['county_fips'];v=int(co.get('votes'));assert v==cvals[fips,method,name]
                state_county.append(dict(source_id='sos-2024-state-reports-detailxml-zip',native_contest_key=contest.get('key'),native_choice_key=choice.get('key'),candidate=name,county=co.get('name'),county_fips=fips,native_method=method,votes=v))
    js=json.loads(b.raw(b.BYID['sos-2024-app-sum-json']));pres=next(c for c in js['Contests'] if c['C']=='President and Vice President')
    for name,v in zip(pres['CH'],pres['V']):assert v==cvals['19','Total',name]
    assert pres['T']==1663506 and pres['BC']==1674011
    countyrec=[]
    for county,co in b.COUNTIES.items():
        fips=co['county_fips'];cu=[r for r in candunits if r['county_fips']==fips];tt=[r for r in turnout if r['county_fips']==fips and r['source_scope']=='native_precinct'];tc=next(r for r in turnout if r['county_fips']==fips and r['source_scope']=='county_administrative_control');ss=[r for r in status if r['county_fips']==fips]
        labels=[r['native_unit_label'] for r in cu];tl=[r['native_unit_label'] for r in tt];sl=[r['native_unit_label'] for r in ss]
        assert labels==sl,(county,labels,sl)
        for field in ['totalVoters','ballotsCast']:
            actual=sum(int(r[field]) for r in tt);control=int(tc[field]);skey='R' if field=='totalVoters' else 'B';sv=sum(int(r[skey]) for r in ss)
            countyrec.append(dict(county=county,county_fips=fips,metric=field,candidate_units=len(cu),turnout_units=len(tt),status_units=len(ss),xml_turnout_unit_sum=actual,xml_turnout_county_control=control,status_unit_sum=sv,xml_unit_minus_county=actual-control,status_minus_county=sv-control,candidate_units_missing_from_turnout=json.dumps([n for n in labels if n not in tl]),status_missing_from_candidate=json.dumps([n for n in sl if n not in labels])))
    b.csvout('clarity-2024-canvass-reconciliation.csv',diffs);b.csvout('clarity-2024-party-label-differences.csv',party_diffs);b.csvout('clarity-2024-state-county-candidate-method.csv',state_county);b.csvout('clarity-2024-context-reconciliation.csv',countyrec)
    result=dict(status='counts_pass_with_retained_context_and_party_scope_differences',counties=99,candidate_units=len(candunits),turnout_units=len(tu),status_units=len(status),candidate_method_cells=len(native),county_candidate_method_controls=len(controls),all_unit_and_county_candidate_sums_exact=True,state_XML_county_candidate_method_cells=len(state_county),state_JSON_all_candidates_exact=True,state_reporting_attributes=dict(contest.attrib),county_XML_party_label_differences=len(party_diffs),party_difference_counties=len({r['county_fips'] for r in party_diffs}),context_differences=[r for r in countyrec if r['xml_unit_minus_county'] or r['status_minus_county'] or r['candidate_units_missing_from_turnout']!='[]'],under_over_finer_unit_scope='not present in downloaded candidate XML; never inferred from residual',source_status='historical tabulation-system snapshot, counts validated to state canvass; completeness flags are not current November approval or votes-counted probabilities')
    b.dump('clarity-2024-validation.json',result);print(json.dumps({k:v for k,v in result.items() if k!='context_differences'},indent=2));print('retained context difference groups',len(result['context_differences']))
if __name__=='__main__':main()
