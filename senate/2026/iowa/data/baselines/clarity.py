#!/usr/bin/env python3
"""Independently parse all 99 actual linked 2024 county XML/JSON originals.
Every context retains its own identity; no normalization of unit names/spaces.
"""
import collections,io,json,re,zipfile
import xml.etree.ElementTree as E
from common import *
def xml(meta):
    z=zipfile.ZipFile(io.BytesIO(raw(meta)));assert z.namelist()==['detail.xml'];return E.fromstring(z.read('detail.xml'))
def main():
    fmap=fipsmap();byf={f:n for n,f in fmap.items()};ms={r['id']:r for r in sources()};units=[];cells=[];countyrows=[];regs=[];statuses=[];scope=[];checks=[];contestreg=[];metadata=[];party_differences=[]
    primary={(r['county_fips'],r['candidate_or_metric_label'],r['native_method']):int(r['votes']) for r in records('canvass-candidate-method.csv') if r['year']=='2024' and r['metric']=='candidate_votes'}
    for fips in sorted(byf):
        meta=ms['sos-2024-county-xml-'+fips];assert meta['status']==200
        root=xml(meta);assert root.findtext('ElectionDate')=='11/5/2024';clock=root.findtext('Timestamp');county=byf[fips]
        c=next(c for c in root.findall('Contest') if c.get('text')=='President and Vice President');ck=c.get('key');sid=meta['id'];parts=meta['url'].split('/');eid,version=parts[-4:-2]
        common={'year':2024,'county':county,'county_fips':fips,'source_id':sid}
        first=list(c.find('Choice').find('VoteType'));names=[p.get('name') for p in first];assert len(names)==len(set(names))
        for i,name in enumerate(names,1):
            units.append(common|{'unit_key':f'{sid}|Contest[{ck}]/Precinct[{i}]','native_unit_label':name,'native_unit_id':'','source_xml_path':f"Contest[@key='{ck}']/Choice[1]/VoteType[1]/Precinct[{i}]",'source_ordinal':i,'source_contest_key':ck,'native_election_id':eid,'native_version':version,'unit_kind':'native_XML_Contest_Precinct; physical/split/style identity unestablished','source_clock':clock,'source_reporting_flag':''})
        for choice in c.findall('Choice'):
            label=choice.get('text');party=choice.get('party','');cid=choice.get('key');total=int(choice.get('totalVotes'));methodsum=0
            countyrows.append(common|{'source_contest_key':ck,'native_choice_key':cid,'native_candidate_label':label,'party_header':party,'native_method':'Total','votes':total,'source_clock':clock})
            target=primary.get((fips,label,'Total'));checks.append({'source_id':sid,'county_fips':fips,'native_candidate_label':label,'native_method':'Total','native_sum':total,'native_control':total,'primary_control':target,'difference':total-target if target is not None else None})
            for vt in choice.findall('VoteType'):
                method=vt.get('name');v=int(vt.get('votes'));methodsum+=v
                assert [p.get('name') for p in vt]==names,(fips,label,method,'unit order conflict')
                countyrows.append(common|{'source_contest_key':ck,'native_choice_key':cid,'native_candidate_label':label,'party_header':party,'native_method':method,'votes':v,'source_clock':clock})
                for i,p in enumerate(vt,1):
                    cells.append(common|{'source_xml_path':f"Contest[@key='{ck}']/Choice[@key='{cid}']/VoteType[@name='{method}']/Precinct[{i}]",'unit_key':f'{sid}|Contest[{ck}]/Precinct[{i}]','native_unit_label':p.get('name'),'source_unit_ordinal':i,'native_contest_key':ck,'native_choice_key':cid,'native_candidate_label':label,'party_header':party,'native_method':method,'votes':int(p.get('votes')),'source_clock':clock})
                sm=sum(int(p.get('votes')) for p in vt);target=primary.get((fips,label,method))
                checks.append({'source_id':sid,'county_fips':fips,'native_candidate_label':label,'native_method':method,'native_sum':sm,'native_control':v,'primary_control':target,'difference':sm-target if target is not None else None});assert sm==v
            assert methodsum==total
        for vt in c.findall('VoteType'):
            for i,p in enumerate(vt,1):contestreg.append(common|{'source_contest_key':ck,'native_method':vt.get('name'),'native_method_total':vt.get('votes'),'source_ordinal':i,'native_unit_label':p.get('name'),'votes':p.get('votes'),'source_clock':clock})
        turn=root.find('VoterTurnout');turnnames=[]
        for i,p in enumerate(turn.findall('Precincts/Precinct'),1):
            name=p.get('name');turnnames.append(name);key=f'{sid}|VoterTurnout/Precincts/Precinct[{i}]';path=f'VoterTurnout/Precincts/Precinct[{i}]'
            units.append(common|{'unit_key':key,'native_unit_label':name,'native_unit_id':'','source_xml_path':path,'source_ordinal':i,'source_contest_key':'','native_election_id':eid,'native_version':version,'unit_kind':'native_XML_VoterTurnout_Precinct; separate source context','source_clock':clock,'source_reporting_flag':p.get('percentReporting','')})
            regs.append(common|{'unit_key':key,'native_unit_label':name,'source_scope':'native_precinct','source_xml_path':path,**{k:p.get(k,'') for k in ['totalVoters','ballotsCast','voterTurnout','percentReporting']},'source_clock':clock})
        regs.append(common|{'unit_key':sid+'|VoterTurnout','native_unit_label':county,'source_scope':'source_county_total','source_xml_path':'VoterTurnout',**{k:turn.get(k,'') for k in ['totalVoters','ballotsCast','voterTurnout','percentReporting']},'source_clock':clock})
        smeta=ms['sos-2024-county-status-'+fips];status=json.loads(raw(smeta));statusnames=status['P'];assert len(statusnames)==len(set(statusnames))
        for i,name in enumerate(statusnames):
            attrs={}
            for k in ['S','R','B','C','CONTEST','PT','U']:
                v=status.get(k);attrs[k]=v[i] if isinstance(v,list) else '' if v is None else v
            statuses.append({'county':county,'county_fips':fips,'source_id':smeta['id'],'source_index':i,'native_unit_label':name,'unit_key':smeta['id']+f'|P[{i}]',**attrs})
        settings=json.loads(raw(ms['sos-2024-county-settings-'+fips]))
        metadata.append({'county':county,'county_fips':fips,'source_id':sid,'native_election_id':eid,'native_version':version,'source_clock':clock,'settings_websiteupdatedat':settings.get('websiteupdatedat'),'settings_stateprecinctsreporting':settings.get('stateprecinctsreporting'),'settings_stateprecinctsparticipating':settings.get('stateprecinctsparticipating'),'contest_attributes':c.attrib,'turnout_attributes':turn.attrib,'under_over_scope':'not published at native candidate-unit level in this XML; unknown, never inferred'})
        scope.append({'county':county,'county_fips':fips,'candidate_unit_count':len(names),'turnout_unit_count':len(turnnames),'status_unit_count':len(statusnames),'candidate_not_turnout':json.dumps([n for n in names if n not in turnnames]),'turnout_not_candidate':json.dumps([n for n in turnnames if n not in names]),'candidate_not_status':json.dumps([n for n in names if n not in statusnames]),'status_not_candidate':json.dumps([n for n in statusnames if n not in names]),'turnout_native_ballots_sum':sum(int(p.get('ballotsCast')) for p in turn.findall('Precincts/Precinct')),'turnout_county_ballots':turn.get('ballotsCast'),'status_ballots_sum':sum(status['B'])})
    state=xml(ms['sos-2024-state-reports-detailxml-zip']);c=next(c for c in state.findall('Contest') if c.get('text')=='President and Vice President');statechecks=[]
    for choice in c.findall('Choice'):
        label=choice.get('text');total=int(choice.get('totalVotes'));target=primary.get(('',label,'Total'))
        statechecks.append({'native_candidate_label':label,'native_method':'Total','county_fips':'','state_xml_votes':total,'primary_canvass_votes':target,'difference':total-target if target is not None else None})
        for vt in choice.findall('VoteType'):
            method=vt.get('name');v=int(vt.get('votes'));target=primary.get(('',label,method))
            statechecks.append({'native_candidate_label':label,'native_method':method,'county_fips':'','state_xml_votes':v,'primary_canvass_votes':target,'difference':v-target if target is not None else None})
            for p in vt:
                f=fmap[p.get('name')];target=primary.get((f,label,method));v=int(p.get('votes'))
                statechecks.append({'native_candidate_label':label,'native_method':method,'county_fips':f,'state_xml_votes':v,'primary_canvass_votes':target,'difference':v-target if target is not None else None})
    statewide_parties={choice.get('text'):choice.get('party','') for choice in c.findall('Choice')}
    for r in countyrows:
        party=statewide_parties[r['native_candidate_label']]
        if r['party_header']!=party:party_differences.append(r|{'state_xml_party':party,'status':'exact named-ticket count match; party identity difference preserved'})
    statejson=json.loads(raw(ms['sos-2024-app-sum-json']));j=next(c for c in statejson['Contests'] if c['C']=='President and Vice President')
    jsonchecks=[{'source_id':'sos-2024-app-sum-json','native_contest_key':j['K'],'native_choice_aggregate_id':cid,'native_candidate_label':label,'party_header':party,'votes':v,'primary_control':primary['',label,'Total'],'difference':v-primary['',label,'Total']} for cid,label,party,v in zip(j['CHAggId'],j['CH'],j['P'],j['V'])]
    assert sum(j['V'])==j['T']==1663506
    csvout('clarity-2024-state-json-checks.csv',jsonchecks);csvout('clarity-2024-party-label-differences.csv',party_differences)
    csvout('clarity-2024-native-units.csv',units);csvout('clarity-2024-native-candidate-method.csv',cells);csvout('clarity-2024-county-candidate-method.csv',countyrows);csvout('clarity-2024-registration-ballots.csv',regs);csvout('clarity-2024-status-units.csv',statuses);csvout('clarity-2024-context-coverage.csv',scope);csvout('clarity-2024-primary-checks.csv',checks);csvout('clarity-2024-state-primary-checks.csv',statechecks);csvout('clarity-2024-contest-registration.csv',contestreg);dump('clarity-2024-source-metadata.json',metadata)
    summary={'county_count':len(scope),'candidate_constituents':sum(r['candidate_unit_count'] for r in scope),'turnout_constituents':sum(r['turnout_unit_count'] for r in scope),'status_constituents':sum(r['status_unit_count'] for r in scope),'native_candidate_cells':len(cells),'county_candidate_controls':len(countyrows),'primary_comparison_cells':len(checks),'state_primary_comparison_cells':len(statechecks),'state_json_candidate_checks':len(jsonchecks),'party_label_differences':len(party_differences),'party_label_counties':len({r['county_fips'] for r in party_differences}),'primary_disagreements':[r for r in checks+statechecks if r['difference'] not in [0]],'context_conflicts':[r for r in scope if r['candidate_not_turnout']!='[]' or r['turnout_not_candidate']!='[]' or r['candidate_not_status']!='[]' or r['status_not_candidate']!='[]'],'state_clock':state.findtext('Timestamp'),'state_contest_attributes':c.attrib,'status':'pass' if all(r['difference']==0 for r in checks+statechecks+jsonchecks) else 'source disagreement or unresolved label'}
    dump('clarity-2024-summary.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
