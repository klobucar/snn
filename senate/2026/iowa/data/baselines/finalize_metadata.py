#!/usr/bin/env python3
"""Pin final read-only review/priority contracts; preserve source clock scopes."""
import json,re
from common import *
def main():
    files=['coordinator-baseline-reconciliation.json','coordinator-historical-clarity-checks.json','coordinator-native-contract-checks.json','coordinator-priority-keys.txt']
    refs=[]
    for name in files:
        p=ROOT.parent/name
        assert p.exists(),p
        refs.append({'path':'../'+name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    p=TURNOUT/'priority-set.json';refs.append({'path':'../turnout/priority-set.json','sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    for name in ['source-manifest.json','SCHEMA.md','full-peer-reconciliation.json']:
        p=TURNOUT/name
        refs.append({'path':'../turnout/'+name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    p=ROOT.parent/'county-turnout.csv';refs.append({'path':'../county-turnout.csv','sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
    dump('review-evidence.json',{'status':'coordinator accepted county and source-scoped historical native research contract; no spatial/current geography approval','scope':'13558 constituent source-context objects plus99county rosters retained in read-only peer priority contract; no unit or geographic merging','references':refs})
    priority=json.loads((ROOT/'priority.json').read_text());priority['status']='independently extracted, full worker reconciliation passed; coordinator accepted county research priority and source-scoped native inventory only';priority['accepted_contract_reference']='review-evidence.json';priority['current_geography_approval']=False;dump('priority.json',priority)
    ms={r['id']:r for r in sources()};dates=[]
    for contest,spec in SPECS.items():
        sid=f"sos-{spec['year']}-canvass";text=gzip.decompress((ROOT/f'text/{sid}.txt.gz').read_bytes()).decode();date=re.search(r'Canvass date:\s*(\d+/\d+/\d+)',text)
        dates.append({'contest':contest,'source_id':sid,'printed_canvass_date':date[1] if date else None,'date_missing_status':'not located in this source' if not date else None,'original_sha256':ms[sid]['original_sha256'],'headers':ms[sid]['headers'],'transport_date_scope':'HTTP Last-Modified/Date are transport metadata, not election/canvass timestamps'})
    dump('source-vintages.json',{'primary_canvasses':dates,'native_2024_individual_clocks':'clarity-2024-source-metadata.json','native_2020_2022_document_properties':'retained original ZIP/XML/PDF bytes; timezone unknown unless printed','statistics_clocks':'read-only ../turnout/statistics-rows.csv.gz source_date plus original PDF text, independently verified in statistics-verification.json','source_status':'historical official SOS publication; preserves exact linked local source internal statuses separately'})
    cass=next(r for r in records('county-contests.csv') if r['contest']=='2024-president' and r['county_fips']=='19029')
    assert int(cass['candidate_writein_votes'])==7217
    dump('cass-local-source-context.json',{'source_id':'cass-2024-local-canvass','original_sha256':ms['cass-2024-local-canvass']['original_sha256'],'source_page':1,'method':'manual transcription from rendered original page; inspected preview review/cass-page1.png','printed_status':'Unofficial Final Results','printed_date':'11/12/2024','printed_time':'1:04:10 PM CST','printed_heading':'Election Day','scope_note':'heading accompanies countywide totals; not interpreted as candidate method scope','candidate_votes_in_source_order':[['Kamala D. Harris Tim Walz','DEM',2077],['Donald J. Trump JD Vance','REP',5007],['Chase Oliver Mike ter Maat','LIB',30],['Claudia De la Cruz Karina Garcia','PSL',1],['William P. Stodden Stephanie H. Cholensky','SOC',3],['Robert F. Kennedy Jr Nicole Shanahan','WTP',76],['Shiva Ayyadurai Crystal Ellis','',1],['Write-in vote, if any','',22]],'candidate_generic_total':7217,'under':62,'over':13,'ballots':7292,'registration':9661,'units_reported':12,'units_total':12,'separate_sos_contest_match':True,'registration_vintage_not_substituted':True})
    print('Pinned final review, native contract and source-vintage evidence')
if __name__=='__main__':main()
