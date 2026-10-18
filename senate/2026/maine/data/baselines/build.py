#!/usr/bin/env python3
"""Offline native-row extraction and conditional pair arithmetic. Python stdlib.

Original response hashes are verified before parsing. No geographic fuzzy join.
The four workbooks are distinct native reporting universes. CSV is a research
extract, not a replacement county table or a calibrated election forecast.
"""
import csv, datetime, gzip, hashlib, io, json, math, re, zipfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as E
from read_xlsx import read

ROOT=Path(__file__).resolve().parent
COUNTIES={k:(name,'23'+f'{2*i+1:03}') for i,(k,name) in enumerate([
 ('AND','Androscoggin'),('ARO','Aroostook'),('CUM','Cumberland'),('FRA','Franklin'),
 ('HAN','Hancock'),('KEN','Kennebec'),('KNO','Knox'),('LIN','Lincoln'),('OXF','Oxford'),
 ('PEN','Penobscot'),('PIS','Piscataquis'),('SAG','Sagadahoc'),('SOM','Somerset'),
 ('WAL','Waldo'),('WAS','Washington'),('YOR','York')])}
CONFIG={
 'senate-2020':dict(date='2020-11-03',contest='U.S. Senate, Class II, same seat as 2026',
  candidates={'C':('collins','Collins, Susan Margaret','R'),'D':('gideon','Gideon, Sara I.','D'),
              'E':('linn','Linn, Max Patrick','IND'),'F':('savage','Savage, Lisa','IND'),
              'G':('others','Others','published aggregate, party unspecified')},blank='H',tbc='I',
  controls=[417645,347223,13508,40579,228,9122,828305],n=517,d='gideon',r='collins'),
 'governor-2022':dict(date='2022-11-08',contest='Governor, statewide midterm; no 2022 U.S. Senate election',
  candidates={'C':('hunkler','Hunkler, Sam','IND-Unenrolled'),'D':('lepage','LePage, Paul R.','R'),
              'E':('mills','Mills, Janet T.','D')},blank='F',tbc='G',
  controls=[12581,287304,376934,4090,680909],n=510,d='mills',r='lepage'),
 'senate-2024':dict(date='2024-11-05',contest='U.S. Senate, Class I, other seat',
  candidates={'C':('cherry','Cherry, Jason S.','IND'),'D':('costello','Costello, David Allen','D'),
              'E':('king','King, Angus S. Jr.','IND'),'F':('kouzounas','Kouzounas, Demi','R')},blank='G',tbc='H',
  controls=[20193,88875,427570,284434,21375,842447],n=512,d='costello',r='kouzounas'),
 'president-2024':dict(date='2024-11-05',contest='President, statewide first choices',
  candidates={'C':('harris','Harris, Kamala D.','D'),'D':('oliver','Oliver, Chase','LIB'),
              'E':('stein','Stein, Jill','Green Independent'),'F':('trump','Trump, Donald J.','R'),
              'G':('west','West, Cornel','Justice For All'),'H':('others','Others','published aggregate, party unspecified')},blank='I',tbc='J',
  controls=[435652,5286,8967,377977,2912,581,11072,842447],n=513,d='harris',r='trump')}

def dump_csv(path,rows):
    if not rows:raise ValueError('empty output '+str(path))
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

def lexical(name):
    # ONLY spelling/token normalization. No constituent, county or geographic inference.
    name=name.strip().casefold().replace("'",'').replace('.','')
    name=re.sub(r'\bplantation\b','plt',name)
    name=re.sub(r'\btownship\b','twp',name)
    name=re.sub(r'^st\b','saint',name)
    return ' '.join(name.split())

def key(date,county,name):
    return f'ME:SOS:{date}:{county or "STATE"}:{quote(name.strip(),safe="")}'

def extract():
    manifest={x['source_id']:x for x in json.loads((ROOT/'manifest.json').read_text())}
    universes={};controls=[];candidates=[];sections=[];metadata=[];outputs=[]
    for source,cfg in CONFIG.items():
        m=manifest[source];path=ROOT/m['saved_path'];saved=path.read_bytes();body=gzip.decompress(saved)
        assert hashlib.sha256(saved).hexdigest()==m['saved_sha256']
        assert hashlib.sha256(body).hexdigest()==m['original_sha256']
        sheets=read(path);assert len(sheets)==1
        sheet,rows=next(iter(sheets.items()))
        (ROOT/'extracted'/(source+'-cells.json')).write_text(json.dumps(sheets,indent=2)+'\n')
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            core=z.read('docProps/core.xml');meta=E.fromstring(core)
            metadata.append(dict(source_id=source,**{x.tag.split('}')[-1]:x.text for x in meta}))
        units=[];section=[];section_code='';cols=list(cfg['candidates'])+[cfg['blank'],cfg['tbc']]
        for row in rows:
            v=row['values'];county=v.get('A','');name=v.get('B','')
            numeric=all(re.fullmatch(r'\d+',v.get(c,'')) for c in cols)
            if numeric and (county in COUNTIES or name=='STATE UOCAVA'):
                if county and not section:section_code=county
                counts={cid:int(v[c]) for c,(cid,_,_) in cfg['candidates'].items()}
                blank=int(v[cfg['blank']]);tbc=int(v[cfg['tbc']]);total=sum(counts.values())
                assert total+blank==tbc,(source,row['row'])
                unit=dict(source_id=source,election_date=cfg['date'],contest=cfg['contest'],
                    source_row_id=f'{source}:{sheet}:R{row["row"]}',native_key=key(cfg['date'],county,name).rstrip(),
                    source_sheet=sheet,source_row=row['row'],native_county_code=county,
                    county_section_code=section_code if county else '',
                    parent_county=COUNTIES.get(county,('',''))[0],county_fips=COUNTIES.get(county,('',''))[1],
                    native_unit_name=name,unit_name=name.strip(),native_numeric_unit_id='',
                    ward_precinct_id='',unit_type='administrative STATE UOCAVA' if not county else
                    'native composite label' if '/' in name else 'native municipal/plantation/township label',
                    stage='initial municipal candidate tally; no central elimination',
                    votes=counts,contest_votes=total,blank=blank,tbc=tbc,source_url=m['source_url'],
                    source_path=m['saved_path'],source_original_sha256=m['original_sha256'])
                units.append(unit)
                if county:section.append(row)
                for column,(cid,cname,party) in cfg['candidates'].items():
                    candidates.append({k:unit[k] for k in ['source_id','election_date','source_row_id','native_key','source_sheet','source_row','native_county_code','county_section_code','native_unit_name']}|
                        dict(candidate_id=cid,candidate_name=cname,party=party,votes=counts[cid],source_cell=column+str(row['row']),category='published Others aggregate' if cid=='others' else 'named candidate'))
            elif numeric and re.search('total',name,re.I):
                statewide=name.casefold() in ['state total','total','statewide totals','statewide total']
                if statewide:
                    statevalues=[int(v[c]) for c in cols]
                    assert statevalues==cfg['controls'],(source,statevalues,cfg['controls'])
                else:
                    for c in cols:
                        native_sum=sum(int(x['values'][c]) for x in section)
                        assert native_sum==int(v[c]),(source,name,c,native_sum,v[c])
                        sections.append(dict(source_id=source,county_section_code=section_code,footer_row=row['row'],footer_label=name,column=c,native_rows_sum=native_sum,cached_footer=int(v[c]),difference=0))
                    section=[];section_code=''
        assert len(units)==cfg['n']
        assert len({u['source_row_id'] for u in units})==len(units)
        state_total=sum(u['contest_votes'] for u in units)
        pair_total=sum(u['votes'][cfg['d']]+u['votes'][cfg['r']] for u in units)
        for col,expected in zip(cols,cfg['controls']):
            cid=cfg['candidates'][col][0] if col in cfg['candidates'] else 'blank' if col==cfg['blank'] else 'tbc'
            observed=sum(u['votes'][cid] if cid in u['votes'] else u[cid] for u in units)
            assert observed==expected
            controls.append(dict(source_id=source,category=cid,all_native_row_sum=observed,cached_statewide_control=expected,difference=observed-expected))
        for u in units:
            d=u['votes'][cfg['d']];r=u['votes'][cfg['r']];pair=d+r
            winner=max(u['votes'],key=u['votes'].get)
            maxvote=u['votes'][winner];winners=[k for k,x in u['votes'].items() if x==maxvote]
            raw={k:v for k,v in u.items() if k!='votes'}
            raw.update({cid+'_votes':n for cid,n in u['votes'].items()})
            raw.update(d_votes=d,r_votes=r,other_votes=u['contest_votes']-d-r,
                d_minus_r_votes=d-r,d_r_pair_votes=pair,
                d_r_pair_d_share_pct=100*d/pair if pair else '',
                d_r_pair_margin_pp=100*(d-r)/pair if pair else '',
                d_r_pair_weight_exact=str(Fraction(pair,pair_total)),
                d_r_pair_weight=pair/pair_total,contest_weight_exact=str(Fraction(u['contest_votes'],state_total)),
                contest_weight=u['contest_votes']/state_total,
                initial_leader='/'.join(winners),d_r_historical_label='D' if d>r else 'R' if r>d else 'tie',
                d_r_closeness='undefined zero pair' if not pair else 'within 5 margin pp' if abs(100*(d-r)/pair)<=5 else '5 to 10 margin pp' if abs(100*(d-r)/pair)<=10 else 'over 10 margin pp',
                net_votes_per_plus_1pp_d_pair_share=.02*pair,
                geography_status='source-native historical label; no 2026 boundary equivalence established',
                source_status='current SOS corrected FINAL 20241205' if source.endswith('2024') else 'current official SOS historical workbook')
            outputs.append(raw)
        universes[source]=units
    dump_csv(ROOT.parent/'county-baselines.csv',outputs)
    dump_csv(ROOT/'candidate-votes.csv',candidates)
    dump_csv(ROOT/'state-controls.csv',controls)
    dump_csv(ROOT/'county-section-checks.csv',sections)
    (ROOT/'workbook-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return universes

def priority_check(units):
    ordered=sorted(units,key=lambda x:(-x['contest_votes'],x['native_county_code'],x['unit_name']))
    total=sum(u['contest_votes'] for u in ordered);cumulative=0;rows=[];priority=[]
    for rank,u in enumerate(ordered,1):
        before=cumulative;cumulative+=u['contest_votes'];flag=5*before<4*total
        if flag:priority.append(u['native_key'])
        rows.append(dict(rank=rank,native_key=u['native_key'],native_county_code=u['native_county_code'],native_unit_name=u['native_unit_name'],source_row=u['source_row'],contest_votes=u['contest_votes'],cumulative_votes=cumulative,priority=int(flag),top15=int(rank<=15)))
    blob=('\n'.join(priority)+'\n').encode();digest=hashlib.sha256(blob).hexdigest()
    assert len(priority)==164 and digest=='086b400b77792d763e93a5083c9ec8c92c71e44016743fc4e7f54bb2008db407'
    assert sum(x['contest_votes'] for x in rows[:15])==215627
    assert rows[162]['cumulative_votes']==656778 and rows[163]['cumulative_votes']==658029
    assert rows[163]['native_unit_name']=='Pownal' and rows[163]['contest_votes']==1251
    dump_csv(ROOT/'independent-priority-ranking.csv',rows)
    (ROOT/'priority-keys.txt').write_bytes(blob)
    worker=ROOT.parent/'county-turnout.csv'
    comparison=dict(independent_units=len(units),ordered_priority_count=len(priority),ordered_priority_sha256=digest,
        top15_votes=215627,first163_votes=656778,first164_votes=658029,crossing_unit='Pownal',crossing_votes=1251,
        all_unit_candidate_differences=[],priority_file_exact=False,source_original_hashes={})
    if worker.exists():
        other=list(csv.DictReader(worker.open()));assert len(other)==512
        for u,r in zip(ordered,other):
            assert u['native_key']==r['native_key']
            for cid,field in [('cherry','cherry_independent_2024'),('costello','costello_democratic_2024'),('king','king_independent_2024'),('kouzounas','kouzounas_republican_2024')]:
                assert u['votes'][cid]==int(r[field]),(u['native_key'],cid)
            assert u['contest_votes']==int(r['senate_votes_2024']) and u['tbc']==int(r['ballots_cast_2024']) and u['blank']==int(r['blank_senate_2024'])
            assert str(u['source_row'])==r['source_rows']
        comparison['all512_keys_order_candidates_blank_tbc_source_rows_exact']=True
        priority_path=ROOT.parent/'turnout/priority-keys.txt'
        assert priority_path.read_bytes()==blob;comparison['priority_file_exact']=True
        mine={x['source_id']:x for x in json.loads((ROOT/'manifest.json').read_text())}
        theirs={x['source_id']:x for x in json.loads((ROOT.parent/'turnout/manifest.json').read_text())}
        for s in ['senate-2024','president-2024','governor-2022']:
            assert mine[s]['original_sha256']==theirs[s]['original_sha256']
            comparison['source_original_hashes'][s]=mine[s]['original_sha256']
    (ROOT/'turnout-reconciliation.json').write_text(json.dumps(comparison,indent=2)+'\n')

def main():
    (ROOT/'extracted').mkdir(exist_ok=True)
    universes=extract();priority_check(universes['senate-2024'])
    print('Extracted', {s:len(u) for s,u in universes.items()},'; independent priority and all512 row comparison PASS')
    return universes

if __name__=='__main__':main()
