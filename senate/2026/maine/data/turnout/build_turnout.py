#!/usr/bin/env python3
"""Offline, stdlib-only extraction and exact Maine volume rankings. Python 3.9+.

Primary unit is the county + MUNICIPALITY label in the current corrected SOS
2024 Senate workbook, with STATE UOCAVA retained outside counties. No geometry
crosswalk is implied. CSV is a requested machine table, not an Excel workbook.
"""
import collections, csv, gzip, hashlib, io, json, re
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote
from xlsx_read import read

ROOT=Path(__file__).resolve().parent
STATE=ROOT.parent.parent
COUNTIES=dict(zip('AND ARO CUM FRA HAN KEN KNO LIN OXF PEN PIS SAG SOM WAL WAS YOR'.split(),
 ['Androscoggin','Aroostook','Cumberland','Franklin','Hancock','Kennebec','Knox','Lincoln','Oxford','Penobscot','Piscataquis','Sagadahoc','Somerset','Waldo','Washington','York']))
FIPS={k:'23'+str(2*i+1).zfill(3) for i,k in enumerate(COUNTIES)}
CONFIG={
 'senate-2024':dict(date='2024-11-05',contest='United States Senator',stage='initial municipal candidate tally; no central RCV elimination',candidate_cols=list('CDEF'),blank='G',ballots='H',expected=[20193,88875,427570,284434,21375,842447],rows=512),
 'president-2024':dict(date='2024-11-05',contest='President and Vice President',stage='initial municipal candidate tally; no central RCV elimination',candidate_cols=list('CDEFGH'),blank='I',ballots='J',expected=[435652,5286,8967,377977,2912,581,11072,842447],rows=513),
 'governor-2022':dict(date='2022-11-08',contest='Governor',stage='plurality final tabulation',candidate_cols=list('CDE'),blank='F',ballots='G',expected=[12581,287304,376934,4090,680909],rows=510),
}
def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def table(path,rows):
    assert rows
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
def native_key(date,county,name):
    return 'ME:SOS:'+date+':'+(county or 'STATE')+':'+quote(name.strip(),safe='')
def labelnorm(s):
    # Lexical normalization only. No slash-combination, inferred township,
    # numerical ID, spatial or cross-year boundary equivalence is introduced.
    s=s.strip().upper().replace("'",'')
    s=re.sub(r'\bPLANTATION\b','PLT',s)
    s=re.sub(r'\bTOWNSHIP\b','TWP',s)
    return re.sub(r'\bSAINT\b','ST',s).replace('ST.','ST')
def columns(row):
    return {re.sub(r'\d','',k):v for k,v in row['cells'].items()}
def ranked(units,field):
    seq=sorted(units,key=lambda x:(-x[field],x['county_code'],x['unit_name'].strip()))
    total=sum(x[field] for x in seq);cum=0
    cutoff=None
    for i,u in enumerate(seq,1):
        cum+=u[field]
        if cutoff is None and 5*cum>=4*total:cutoff=i
    cum=0;result={}
    for i,u in enumerate(seq,1):
        cum+=u[field]
        result[u['native_key']]=dict(rank=i,total=total,cumulative=cum,share=str(Fraction(u[field],total)),
              cumulative_share=str(Fraction(cum,total)),top15=i<=15,minimum80=i<=cutoff)
    return seq,result,cutoff
def extract(source_id):
    cfg=CONFIG[source_id];src='raw/'+source_id+'.xlsx.gz';sheets=read(ROOT/src)
    assert len(sheets)==1
    sheet,rows=next(iter(sheets.items()))
    (ROOT/'extracted').mkdir(exist_ok=True)
    (ROOT/'extracted'/(source_id+'-cells.json.gz')).write_bytes(gzip.compress(json.dumps(sheets,ensure_ascii=False).encode(),mtime=0))
    head=columns(rows[0]);party=columns(rows[2]);cols=cfg['candidate_cols']+[cfg['blank'],cfg['ballots']]
    labels={c:head.get(c,'').strip() for c in cfg['candidate_cols']}
    raw=[]; controls=[];current_county=None; county_sums=collections.defaultdict(lambda:[0]*len(cols));block_counts=[0]*len(cols)
    for r in rows:
        d=columns(r);county=d.get('A','');name=d.get('B','')
        if county in COUNTIES or name=='STATE UOCAVA':
            if county in COUNTIES and current_county is None:current_county=county
            counts=[int(d[c]) for c in cols]
            assert min(counts)>=0
            assert sum(counts[:-1])==counts[-1],(source_id,r,counts)
            key=native_key(cfg['date'],county,name)
            raw.append(dict(native_key=key,source_row_key=source_id+':'+sheet+':row'+str(r['row']),county_code=county,
              county_section_code=current_county if county else '',county_label_conflict=int(bool(county) and county!=current_county),
              county=COUNTIES.get(county,''),county_fips=FIPS.get(county,''),unit_name=name,source_id=source_id,
              source_path=src,source_sheet=sheet,source_row=r['row'],election_date=cfg['date'],contest=cfg['contest'],stage=cfg['stage'],
              voting_method='all methods combined within label; STATE UOCAVA separate',boundary_vintage=cfg['date']+' return labels; 2026 equivalence unverified',
              candidate_votes=sum(counts[:len(cfg['candidate_cols'])]),blank=counts[-2],ballots=counts[-1],counts=counts))
            if county in COUNTIES:
                county_sums[county]=[a+b for a,b in zip(county_sums[county],counts)]
                block_counts=[a+b for a,b in zip(block_counts,counts)]
        elif name and ('total' in name.lower()):
            nums=[int(d[c]) for c in cols]
            statewide='statewide' in name.lower() or (source_id=='governor-2022' and name=='Total')
            expected=[sum(x['counts'][j] for x in raw) for j in range(len(cols))] if statewide else block_counts
            assert nums==expected,(source_id,name,nums,expected)
            controls.append(dict(source_id=source_id,source_sheet=sheet,source_row=r['row'],control_label=name,
                county_code='' if statewide else current_county,columns=cols,published=nums,recomputed_disjoint_section=expected,difference=[a-b for a,b in zip(nums,expected)]))
            if not statewide:current_county=None;block_counts=[0]*len(cols)
    assert len(raw)==cfg['rows']
    assert [sum(x['counts'][j] for x in raw) for j in range(len(cols))]==cfg['expected']
    assert len(controls)==17
    # 2022 repeats Cranberry Isles on two positive rows, neither with a ward ID.
    # Retain their unique row identities above; aggregate only in research view.
    groups=collections.defaultdict(list)
    for u in raw:groups[u['native_key']].append(u)
    units=[]
    for key,part in groups.items():
        u=dict(part[0]);u['source_rows']=[x['source_row'] for x in part]
        u['source_row_keys']=[x['source_row_key'] for x in part]
        u['counts']=[sum(x['counts'][j] for x in part) for j in range(len(cols))]
        for f in ['candidate_votes','blank','ballots']:u[f]=sum(x[f] for x in part)
        units.append(u)
    long=[]
    for u in raw:
        for j,col in enumerate(cols):
            long.append({k:v for k,v in u.items() if k!='counts'}|dict(source_column=col,
                category='candidate' if col in cfg['candidate_cols'] else 'blank' if col==cfg['blank'] else 'ballots',
                candidate_or_category=labels.get(col,'BLANK' if col==cfg['blank'] else 'TBC'),
                party=party.get(col,'') if col in cfg['candidate_cols'] else '',votes=u['counts'][j]))
    table(ROOT/(source_id+'-source-rows.csv'),long)
    seq,ranks,k=ranked(units,'candidate_votes');_,branks,bk=ranked(units,'ballots')
    out=[]
    for u in seq:
        r=ranks[u['native_key']];b=branks[u['native_key']]
        out.append(dict(native_key=u['native_key'],county_code=u['county_code'],county=u['county'],county_fips=u['county_fips'],unit_name=u['unit_name'],
            election_date=u['election_date'],contest=u['contest'],stage=u['stage'],voting_method=u['voting_method'],boundary_vintage=u['boundary_vintage'],candidate_votes=u['candidate_votes'],blank=u['blank'],ballots=u['ballots'],
            candidate_rank=r['rank'],candidate_denominator=r['total'],candidate_weight_exact=r['share'],candidate_cumulative_votes=r['cumulative'],candidate_cumulative_weight_exact=r['cumulative_share'],
            candidate_top15=r['top15'],candidate_minimum80=r['minimum80'],ballot_rank=b['rank'],ballot_denominator=b['total'],ballot_weight_exact=b['share'],
            ballot_cumulative=b['cumulative'],ballot_cumulative_weight_exact=b['cumulative_share'],ballot_top15=b['top15'],ballot_minimum80=b['minimum80'],
            source_path=u['source_path'],source_sheet=u['source_sheet'],source_rows=';'.join(map(str,u['source_rows']))))
    table(ROOT/(source_id+'-ranked.csv'),out)
    summary=dict(raw_unit_rows=len(raw),research_units=len(units),nonempty_worksheet_rows=len(rows),maximum_excel_row=max(x['row'] for x in rows),
        candidate_columns=[dict(column=c,label=labels[c],party=party.get(c,''),total=cfg['expected'][i]) for i,c in enumerate(cfg['candidate_cols'])],
        candidate_total=sum(cfg['expected'][:-2]),blank=cfg['expected'][-2],ballots=cfg['expected'][-1],
        controls=controls,county_code_conflicts=[dict(source_row=u['source_row'],native_name=u['unit_name'],native_county=u['county_code'],section_county=u['county_section_code'],counts=u['counts']) for u in raw if u['county_label_conflict']],
        raw_duplicate_names={key:[x['source_row'] for x in part] for key,part in groups.items() if len(part)>1},
        top15=sum(x['candidate_votes'] for x in seq[:15]),minimum80_count=k,minimum80_votes=sum(x['candidate_votes'] for x in seq[:k]),
        previous_votes=sum(x['candidate_votes'] for x in seq[:k-1]),crossing_key=seq[k-1]['native_key'],ballot_minimum80_count=bk)
    return raw,seq,ranks,branks,summary

def registrations():
    allrows=[];summaries={};groups={}
    for year in [2024,2022]:
        for status in ['active','inactive']:
            source=f'registration-{year}-{status}';src='raw/'+source+'.txt.gz'
            rows=list(csv.DictReader(io.StringIO(gzip.decompress((ROOT/src).read_bytes()).decode()),delimiter='|'))
            keys=set();agg=collections.defaultdict(list)
            partycols=[k for k in rows[0] if k not in ['COUNTY','MUNICIPALITY','W/P','CG','SS','SR','CC','TOTAL','']]
            for i,r in enumerate(rows,2):
                native=[r[x] for x in ['COUNTY','MUNICIPALITY','W/P','CG','SS','SR','CC']]
                key='ME:CVR:'+str(year)+':'+':'.join(quote(x,safe='') for x in native)
                assert key not in keys;keys.add(key)
                assert sum(int(r[k]) for k in partycols)==int(r['TOTAL'])
                out=dict(registration_key=key,status=status,as_of_date='2024-11-05' if year==2024 else '2022-11-08',
                    county_code=r['COUNTY'],municipality=r['MUNICIPALITY'],ward_precinct=r['W/P'],congressional_district=r['CG'],state_senate=r['SS'],state_house=r['SR'],county_commissioner=r['CC'],
                    total=int(r['TOTAL']),party_counts_json=json.dumps({k:int(r[k]) for k in partycols},separators=(',',':')),
                    source_path=src,source_line=i,boundary_status='historical registration geography; not validated for 2026 or as vote-return precincts')
                allrows.append(out);agg[(r['COUNTY'],labelnorm(r['MUNICIPALITY']))].append(out)
            summaries[source]=dict(rows=len(rows),municipal_labels=len(agg),total=sum(int(r['TOTAL']) for r in rows),party_totals={k:sum(int(r[k]) for r in rows) for k in partycols})
            groups[(year,status)]=agg
    table(ROOT/'registration-native-rows.csv',allrows)
    dump(ROOT/'registration-summary.json',summaries)
    return groups,summaries

def main():
    data={};summaries={}
    for name in CONFIG:
        raw,units,ranks,branks,summary=extract(name)
        data[name]=dict(raw=raw,units=units,ranks=ranks,branks=branks);summaries[name]=summary
    regs,regsummary=registrations()
    base=data['senate-2024'];rows=[];coverage=[];crosswalk=[]
    compare={sid:{(u['county_code'],labelnorm(u['unit_name'])):u for u in data[sid]['units']} for sid in ['president-2024','governor-2022']}
    for u in base['units']:
        key=u['native_key'];r=base['ranks'][key];b=base['branks'][key]
        row=dict(rank=r['rank'],native_key=key,state='ME',state_fips='23',native_state_numeric_unit_id='',
            county_code=u['county_code'],county=u['county'],county_fips=u['county_fips'],unit_name=u['unit_name'],
            unit_type='state-administered UOCAVA' if not u['county_code'] else 'combined native reporting label' if '/' in u['unit_name'] else 'native municipal/plantation/township/voting-district label',
            election_date='2024-11-05',contest='United States Senator',stage=CONFIG['senate-2024']['stage'],voting_method='all methods combined; STATE UOCAVA separate',
            source_status='SOS corrected FINAL 20241205; final-results notice 2024-12-18',boundary_vintage='2024 election return labels; 2026 equivalence unverified',
            cherry_independent_2024=u['counts'][0],costello_democratic_2024=u['counts'][1],king_independent_2024=u['counts'][2],kouzounas_republican_2024=u['counts'][3],
            senate_votes_2024=u['candidate_votes'],vote_denominator=r['total'],weight_exact=r['share'],weight_decimal=f"{u['candidate_votes']/r['total']:.12f}",
            cumulative_votes=r['cumulative'],cumulative_share_exact=r['cumulative_share'],cumulative_share_decimal=f"{r['cumulative']/r['total']:.12f}",
            top15=int(r['top15']),minimum80=int(r['minimum80']),priority=int(r['top15'] or r['minimum80']),
            blank_senate_2024=u['blank'],ballots_cast_2024=u['ballots'],ballot_rank_2024=b['rank'],
            ballot_denominator_2024=b['total'],ballot_weight_exact=b['share'],ballot_cumulative_votes=b['cumulative'],ballot_cumulative_share_exact=b['cumulative_share'],ballot_top15=int(b['top15']),ballot_minimum80=int(b['minimum80']),
            source_path=u['source_path'],source_sheet=u['source_sheet'],source_rows=';'.join(map(str,u['source_rows'])))
        entry=dict(native_key=key,native_name=u['unit_name'],county_code=u['county_code'],county_fips=u['county_fips'],rank=r['rank'],senate_votes=u['candidate_votes'],priority=bool(row['priority']),
            top15=r['top15'],minimum80=r['minimum80'],source_path=u['source_path'],source_sheet=u['source_sheet'],source_rows=u['source_rows'],
            source_native_numeric_unit_id=None,results_ward_precinct_ids=[],results_ward_precinct_status='not published in selected statewide workbook',
            registration_constituents=[],registration_join='unmatched',boundary_vintage='2024; no 2026 boundary equivalence established')
        for sid,prefix in [('president-2024','president_2024'),('governor-2022','governor_2022')]:
            match=compare[sid].get((u['county_code'],labelnorm(u['unit_name'])))
            status='matching county and lexically normalized source name; boundary equivalence unverified' if match else 'unmatched; retained in independent all-unit comparator ranking'
            row.update({prefix+'_native_key':match['native_key'] if match else '',prefix+'_votes':match['candidate_votes'] if match else '',prefix+'_rank':data[sid]['ranks'][match['native_key']]['rank'] if match else '',
                prefix+'_ballots':match['ballots'] if match else '',prefix+'_source_rows':';'.join(map(str,match['source_rows'])) if match else '',prefix+'_join_status':status})
            crosswalk.append(dict(senate_native_key=key,comparator=sid,comparator_native_key=match['native_key'] if match else '',status=status))
        for year in [2024,2022]:
            for status in ['active','inactive']:
                match=regs[(year,status)].get((u['county_code'],labelnorm(u['unit_name'])))
                row[f'registered_{status}_{year}']=sum(x['total'] for x in match) if match else ''
                if year==2024 and status=='active' and match:
                    entry['registration_join']='county + lexically normalized name only; not a boundary crosswalk'
                    entry['registration_constituents']=[dict(native_key=x['registration_key'],native_municipality=x['municipality'],ward_precinct=x['ward_precinct'],congressional_district=x['congressional_district'],state_senate=x['state_senate'],state_house=x['state_house'],county_commissioner=x['county_commissioner'],source_path=x['source_path'],source_line=x['source_line']) for x in match]
        rows.append(row);coverage.append(entry)
    table(STATE/'data/county-turnout.csv',rows)
    table(ROOT/'comparator-label-crosswalk.csv',crosswalk)
    priority=[u for u in coverage if u['priority']];remainder=[u for u in coverage if not u['priority']]
    keybytes=('\n'.join(x['native_key'] for x in priority)+'\n').encode()
    (ROOT/'priority-keys.txt').write_bytes(keybytes)
    dump(ROOT/'priority-set.json',dict(schema_version=1,state='Maine',baseline='2024-11-05 United States Senator',
      source='current SOS corrected FINAL 20241205',denominator=821072,stage=CONFIG['senate-2024']['stage'],
      source_paths_relative_to='senate/2026/maine/data/turnout',
      key_definition='ME:SOS:date:native county code (STATE when absent):percent-encoded trimmed exact source municipality',
      tie_order='candidate votes descending, native county code ascending (empty string for STATE UOCAVA), trimmed source municipality ascending; Python Unicode order',
      arithmetic='5*cumulative >= 4*statewide; exact integers; fractions reduced with Fraction',
      all_unit_count=len(coverage),priority_count=len(priority),nonpriority_count=len(remainder),top15_votes=summaries['senate-2024']['top15'],
      minimum80_votes=summaries['senate-2024']['minimum80_votes'],previous_votes=summaries['senate-2024']['previous_votes'],
      ordered_priority_keys_sha256=hashlib.sha256(keybytes).hexdigest(),hash_encoding='UTF-8 keys in exact order, LF after every key including final',
      ward_precinct_warning='registration constituents are historical CVR district intersections, not demonstrated vote-reporting precincts or current polygons',
      priority=priority,nonpriority_remainder=remainder,all_unit_coverage=coverage))
    # Context only. County labels are the SOS reporting county, which need not
    # place every township component of a combined label inside that county.
    contextual=[]
    for sid,d in data.items():
        for c in list(COUNTIES)+['']:
            us=[u for u in d['units'] if u['county_code']==c]
            contextual.append(dict(source_id=sid,county_code=c,county=COUNTIES.get(c,'STATE UOCAVA (unallocated)'),county_fips=FIPS.get(c,''),units=len(us),candidate_votes=sum(u['candidate_votes'] for u in us),ballots=sum(u['ballots'] for u in us),blank=sum(u['blank'] for u in us)))
    table(ROOT/'county-context.csv',contextual)
    dump(ROOT/'checks.json',dict(elections=summaries,registration=regsummary,priority_count=len(priority),nonpriority_count=len(remainder),priority_key_hash=hashlib.sha256(keybytes).hexdigest(),
        comparator_label_matches={sid:sum(x['comparator']==sid and bool(x['comparator_native_key']) for x in crosswalk) for sid in compare},
        priority_registration_unmatched=[x['native_key'] for x in priority if not x['registration_constituents']],
        exact_weights_sum=str(sum(Fraction(x['weight_exact']) for x in rows)),
        minimum80_integer_check=5*summaries['senate-2024']['minimum80_votes']>=4*821072,
        previous_integer_check=5*summaries['senate-2024']['previous_votes']<4*821072))
    print(json.dumps({k:{j:v for j,v in s.items() if j not in ['controls','candidate_columns']} for k,s in summaries.items()},indent=2))
    print('priority key SHA256',hashlib.sha256(keybytes).hexdigest())

if __name__=='__main__':main()
