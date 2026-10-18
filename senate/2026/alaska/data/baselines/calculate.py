#!/usr/bin/env python3
"""Offline Alaska DOE baseline reconciliation and explicitly conditional scenarios.
Python standard library plus system pdftotext. No network calls or Git operations.
"""
import argparse,collections,csv,gzip,json,math,pathlib,re,subprocess
ROOT=pathlib.Path(__file__).resolve().parent
NAMES22=['Chesbro, Patricia R.','Kelley, Buzz A.','Murkowski, Lisa','Tshibaka, Kelly C.','Write-in']
PARTY22=['DEM','REP','REP','REP','']
NAMES20=['Gross, Al','Howe, John Wayne','Sullivan, Dan','Write-in']
PARTY20=['DEM','AIP','REP','']
STATES={2020:[146068,16806,191112,601],2022:[27145,7557,113495,111480,2028],2024:[140026,5670,3040,702,2342,812,184458,1127]}
BALLOTS={2020:361400,2022:267047,2024:340981}
METHODS=['Election Day','Absentee','Early Voting','Question','Remote']
CHECKS=[]

def write(name,rows):
    rows=list(rows);assert rows,name
    with (ROOT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def check(name,actual,expected):
    ok=abs(actual-expected)<1e-7
    CHECKS.append(dict(check=name,actual=actual,expected=expected,difference=actual-expected,passed=ok));assert ok,(name,actual,expected)

def hd(name):
    if name.strip().startswith('HD99'):return 99
    m=re.match(r'(\d\d)-\d',name) or re.match(r'District\s+(\d+)',name)
    assert m,('unallocated native unit',name)
    return int(m[1])

def method(name):
    for m in METHODS[1:]:
        if m in name:return m
    return 'Election Day'

def extract_pdf(path):
    out=path.with_suffix('.extracted.txt')
    subprocess.run(['pdftotext','-layout',str(path),str(out)],check=True)
    return out.read_text()

def rowbase(year,n,stage='first_choices'):
    return dict(election_year=year,contest='U.S. President / Vice President' if year==2024 else 'U.S. Senator',stage=stage,unit_key=f'AK-{year}-HD{n:02}',source_unit_id=str(n),unit_name=f'House District {n}' if n!=99 else 'HD99 Fed Overseas Absentee',unit_type='house_district' if n!=99 else 'nongeographic_federal_overseas_administration',county_fips='',boundary_vintage=f'{year} election reporting units; '+('pre-2022 redistricting' if year==2020 else '2022-era redistricting; no cross-year number join'),status='Official DOE publication; derived aggregation')

def firstchoices():
    native=[];groups={};names={};parties={};byunit22={}
    # The 2020 text lacks ALL write-in rows. Complete district statements supply them.
    old=collections.defaultdict(collections.Counter);oldstats=collections.defaultdict(dict)
    alias={'Gross  Al':'Gross, Al','Howe  John Wayne':'Howe, John Wayne','Sullivan  Dan':'Sullivan, Dan'}
    for r in csv.reader((ROOT/'precinct2020.txt').open()):
        if len(r)<8 or r[1].strip('"')!='U.S. Senator' or r[6]!='Total':continue
        u=r[0].strip();label=r[4].strip('"');v=int(r[7]);n=hd(u)
        if label in alias:
            cand=alias[label];assert r[5].strip('"')==dict(zip(NAMES20,PARTY20))[cand];old[n][cand]+=v
            native.append(dict(election_year=2020,contest='U.S. Senator',stage='first_choices',source_unit_id=u,unit_name=u,house_district=n,voting_method=method(u),candidate=cand,party_source=r[5].strip('"'),votes=v,source_file='precinct2020.txt',coverage_note='Named candidates complete; write-ins not in text export, recovered at district level from PDFs'))
        elif label=='Times Counted':oldstats[n][u]=v
    g={}
    for n in list(range(1,41))+[99]:
        text=extract_pdf(ROOT/f'hd{n}-2020.pdf');a=text.index('U.S. Senator');b=text.index('U.S. Representative',a);section=text[a:b]
        candidates=[]
        for line in section.splitlines():
            if 'State of Alaska - Total' in line:
                nums=[int(x.replace(',','')) for x in re.findall(r'(?<!\S)[\d,]+(?!\S)',line.split('State of Alaska - Total')[-1])]
                if len(nums)>=5:candidates.append(nums[-5:])
        # Some district statements have multiple pages: the last total is the full district.
        vals=candidates[-1];check(f'2020-HD{n}-pdf-candidate-total',sum(vals[:4]),vals[4])
        for i,c in enumerate(NAMES20[:3]):check(f'2020-HD{n}-{c}-text-v-pdf',old[n][c],vals[i])
        g[n]=dict(zip(NAMES20,vals[:4]))
    groups[2020]=g;names[2020]=NAMES20;parties[2020]=PARTY20
    # All published 2022 precinct and district-method units, including HD99.
    rows=list(csv.reader((ROOT/'precinct2022.txt').read_text(encoding='utf-16').splitlines(),delimiter='\t'))
    start=next(i for i,r in enumerate(rows) if r and r[0]=='Precinct')
    for i,(cand,party) in enumerate(zip(NAMES22,PARTY22),1):assert rows[start][i]==(f'{cand} - {party}' if party else cand)
    g=collections.defaultdict(collections.Counter)
    for r in rows[start+1:]:
        if not r or not r[0]:break
        if r[0]=='Total':
            assert [int(x) for x in r[1:]]==STATES[2022];break
        assert len(r)==6
        u=r[0];n=hd(u);byunit22[u]=dict(zip(NAMES22,map(int,r[1:])))
        for cand,party,v in zip(NAMES22,PARTY22,r[1:]):
            g[n][cand]+=int(v)
            native.append(dict(election_year=2022,contest='U.S. Senator',stage='first_choices',source_unit_id=u.split()[0] if re.match(r'\d\d-',u) else u,unit_name=u,house_district=n,voting_method=method(u),candidate=cand,party_source=party,votes=int(v),source_file='precinct2022.txt',coverage_note='Original precinct export says Unofficial; every candidate reconciles to official summary'))
    groups[2022]=g;names[2022]=NAMES22;parties[2022]=PARTY22
    # 2024 has an explicit native ID and candidate ID and separate method columns.
    g=collections.defaultdict(collections.Counter);cands={};records=[];ballots={};methods24=collections.Counter()
    for r in csv.DictReader((ROOT/'precinct2024.csv').open()):
        if r['Contest_Id']!='4':continue
        u=r['Precinct_name'];n=hd(u);cand=r['candidate_name'];idx=int(r['cand_seq_nbr']);v=int(r['total_votes'])
        cands[idx]=(cand,r['Party_Code']);g[n][cand]+=v;ballots[u]=int(r['total_ballots']);records.append(r)
        check(f'2024-{r["Pct_Id"]}-{cand}-method-sum',sum(int(r[f'{m}_votes']) for m in METHODS),v)
        for m in METHODS:methods24[m,cand]+=int(r[f'{m}_votes'])
        native.append(dict(election_year=2024,contest=r['Contest_title'],stage='first_choices',source_unit_id=r['Pct_Id'],unit_name=u,house_district=n,voting_method='all methods; split in official source columns',candidate=cand,party_source=r['Party_Code'],votes=v,source_file='precinct2024.csv',coverage_note=f'Contest_Id=4; candidate_id={r["candidate_id"]}; Pct_seq_nbr={r["Pct_seq_nbr"]}; all methods sum exactly'))
    check('2024-native-units',len(ballots),523)
    check('2024-candidate-unit-rows',len(records),523*8)
    assert len({(r['Pct_seq_nbr'],r['candidate_id']) for r in records})==len(records)
    check('2024-deduplicated-unit-ballots',sum(ballots.values()),BALLOTS[2024])
    check('2024-pres-contest-plus-under-over',sum(sum(g[n].values()) for n in g)+sum(int(r['total_under_votes'])+int(r['total_over_votes']) for r in records[::8]),BALLOTS[2024])
    names[2024]=[cands[k][0] for k in sorted(cands)];parties[2024]=[cands[k][1] for k in sorted(cands)];groups[2024]=g
    state_rows=[];base=[]
    for year in [2020,2022,2024]:
        check(f'{year}-district-count',len(groups[year]),41)
        assert set(groups[year])==set(range(1,41))|{99}
        for c,expected in zip(names[year],STATES[year]):
            actual=sum(v.get(c,0) for v in groups[year].values());check(f'{year}-{c}-state',actual,expected)
            state_rows.append(dict(year=year,stage='first_choices',candidate=c,computed_votes=actual,official_statewide_votes=expected,difference=actual-expected,official_source='summary2024.pdf' if year==2024 else f'summary{year}.pdf'))
        for n in sorted(groups[year]):
            vals=groups[year][n];total=sum(vals.values())
            for c,party in zip(names[year],parties[year]):
                r=rowbase(year,n);r.update(candidate=c,party_source=party,candidate_identity='Independent / Nonpartisan' if year==2020 and c=='Gross, Al' else party,votes=vals[c],candidate_vote_denominator=total,ballot_scope='full published first-choice returns',candidate_share=vals[c]/total,source_file=f'hd{n}-2020.pdf' if year==2020 else f'precinct{year}.'+('csv' if year==2024 else 'txt'));base.append(r)
    for r in native:r['source_unit_key']=f'AK-{r["election_year"]}-native:{r["unit_name"]}'
    for y,expected in [(2020,580),(2022,522),(2024,523)]:check(f'{y}-native-unit-count',len({r['source_unit_key'] for r in native if r['election_year']==y}),expected)
    write('native-first-choices.csv',native);write('statewide-candidate-checks.csv',state_rows)
    # Method comparison: unique report cells; never add duplicate rendering rows.
    methods22={}
    for r in csv.reader((ROOT/'summary2022.txt').read_text(encoding='utf-16').splitlines(),delimiter='\t'):
        if len(r)>25 and r[4].strip()=='U.S. Senator' and r[20].strip() in NAMES22 and r[23] in METHODS:
            k=(r[23],r[20].strip());v=int(r[24].replace(',',''));assert k not in methods22 or methods22[k]==v;methods22[k]=v
    method_rows=[]
    for m in METHODS:
        for c in NAMES22:
            actual=sum(row['votes'] for row in native if row['election_year']==2022 and row['candidate']==c and row['voting_method']==m)
            check(f'2022-{m}-{c}-method',actual,methods22[m,c]);method_rows.append(dict(year=2022,method=m,candidate=c,votes=actual,official_comparator=methods22[m,c],difference=actual-methods22[m,c]))
    for (m,c),v in sorted(methods24.items()):method_rows.append(dict(year=2024,method=m,candidate=c,votes=v,official_comparator='source method-column sum',difference=0))
    write('method-checks.csv',method_rows)
    return groups,names,parties,base,byunit22

# Source RCV rules: unresolved write-ins skip without a gap, repeated rankings
# count only once (later repetitions become empty); test overvotes BEFORE removing
# repeated candidates. Two consecutive empty ranks terminate later preferences.
def choose(pairs,active):
    by=collections.defaultdict(set)
    for rank,cand in pairs:by[rank].add(cand)
    seen=set();skipped=0
    for rank in range(1,6):
        ids=by[rank]
        if len(ids)>1:return 'Overvotes'
        if ids and next(iter(ids)) in seen:ids=set()
        seen.update(ids)
        if not ids:
            skipped+=1
            if skipped==2:return 'Blanks'
            continue
        skipped=0;c=next(iter(ids))
        if c in active:return c
    return 'Blanks'

def rcv(base,byunit22):
    official={};oflow={};rows=list(csv.reader((ROOT/'senate-rcv2022.txt').read_text(encoding='utf-16').splitlines(),delimiter='\t'))
    for r in rows:
        if len(r)>3 and re.fullmatch(r'Round [123]',r[1]) and r[2]:official[int(r[1][-1]),r[2]]=int(r[3].replace(',',''))
        if len(r)>24 and r[20] in NAMES22 and r[21] and r[24]:
            oflow[r[20],r[21]]=int(r[24].replace(',',''))
    ids={271:NAMES22[0],272:NAMES22[1],273:NAMES22[2],274:NAMES22[3]}
    units=collections.defaultdict(collections.Counter);flows=collections.defaultdict(collections.Counter);ballots=collections.Counter();methodballots=collections.Counter();scanner=collections.defaultdict(collections.Counter)
    for r in csv.DictReader(gzip.open(ROOT/'cvr2022-senate-patterns.csv.gz','rt')):
        u=r['precinct_name'];n=hd(u);assert u in byunit22,(u,'not in full firstchoice export')
        pairs=json.loads(r['rank_candidate_pairs']);v=int(r['ballots']);ballots[n]+=v;methodballots[r['voting_method']]+=v
        seq=[choose(pairs,a) for a in [{271,272,273,274},{271,273,274},{273,274}]]
        seq=[ids.get(c,c) for c in seq]
        for i,c in enumerate(seq):
            if i>0 and c=='Blanks' and seq[0] in ids.values():seq[i]='Exhausted'
        for i,c in enumerate(seq):units[(n,i+1)][c]+=v
        for i in [0,1]:
            if seq[i] in [NAMES22[1],NAMES22[0]] and seq[i]!=seq[i+1]:flows[(n,i+1,seq[i])][seq[i+1]]+=v
    scanner={(r['unit_name'],r['candidate']):int(r['votes']) for r in csv.DictReader((ROOT/'cvr2022-scanner-first-choices.csv').open())}
    cvr_names={k[0] for k in scanner};missing=set(byunit22)-cvr_names;check('2022-CVR-missing-native-units',len(missing),5)
    gaps=[]
    for u,values in sorted(byunit22.items()):
        for c,v in values.items():
            cv=scanner.get((u,c),0);diff=v-cv
            assert diff>=0,(u,c,diff)
            if u not in missing and u!='37-730 Levelock':check(f'CVR-scanner-first-{u}-{c}',cv,v)
            gaps.append(dict(unit_name=u,house_district=hd(u),candidate=c,full_first_choices=v,cvr_scanner_first_choices=cv,difference=diff,unit_present_in_cvr=u in cvr_names))
    check('CVR-full-firstchoice-vote-gap',sum(r['difference'] for r in gaps),237)
    cvr_unit_ballots=collections.Counter()
    for r in csv.DictReader(gzip.open(ROOT/'cvr2022-senate-patterns.csv.gz','rt')):cvr_unit_ballots[r['precinct_name']]+=int(r['ballots'])
    ballotgaps=[]
    for u in sorted({r['unit_name'] for r in gaps if r['difference']}):
        text=extract_pdf(ROOT/f'hd{hd(u)}-2022.pdf')
        line=next(x for x in text.splitlines() if x.strip().startswith(u))
        nums=re.findall(r'[\d,]+',line.split(u)[1]);full=int(nums[1].replace(',',''))
        ballotgaps.append(dict(unit_name=u,house_district=hd(u),full_ballots=full,cvr_ballots=cvr_unit_ballots[u],missing_ballots=full-cvr_unit_ballots[u],missing_candidate_votes=sum(x['difference'] for x in gaps if x['unit_name']==u),source_file=f'hd{hd(u)}-2022.pdf'))
    check('CVR-missing-ballots-localized',sum(x['missing_ballots'] for x in ballotgaps),250)
    write('cvr-ballot-coverage-gaps.csv',ballotgaps)
    write('cvr-coverage-gaps.csv',gaps)
    # Include every HD even if CVR is absent, as zero-on-CVR-scope only.
    out=[];state=[]
    for roundnum in [1,2,3]:
        for c in list(ids.values())+['Blanks','Exhausted','Overvotes','Remainder Points']:
            actual=sum(units[n,roundnum][c] for n in list(range(1,41))+[99]);expected=official[roundnum,c]
            check(f'RCV-round{roundnum}-{c}',actual,expected)
            state.append(dict(round=roundnum,category=c,votes=actual,official_votes=expected,difference=actual-expected))
        check(f'RCV-round{roundnum}-conservation',sum(x['votes'] for x in state if x['round']==roundnum),266797)
        for n in list(range(1,41))+[99]:
            total=sum(units[n,roundnum][c] for c in ids.values())
            for c in list(ids.values())+['Blanks','Exhausted','Overvotes']:
                b=rowbase(2022,n,f'rcv_round_{roundnum}');party=dict(zip(NAMES22,PARTY22)).get(c,'');b.update(candidate=c,party_source=party,candidate_identity=party,votes=units[n,roundnum][c],candidate_vote_denominator=total,ballot_scope='266797 CVR ballots statewide; 250 ballots fewer than full first-choice publication',candidate_share=units[n,roundnum][c]/total if c in ids.values() and total else '',source_file='cvr2022-senate-patterns.csv.gz; senate-rcv2022.txt');base.append(b)
                out.append(dict(round=roundnum,house_district=n,category=c,votes=units[n,roundnum][c],continuing_votes=total,cvr_ballots=ballots[n],scope='CVR only; derived state-elimination-order contributions, not separate district elections'))
    flowrows=[]
    for source in [NAMES22[1],NAMES22[0]]:
        rnd=1 if source==NAMES22[1] else 2
        destinations=[c for s,c in oflow if s==source and c!=source]
        for c in destinations:
            total=sum(flows[n,rnd,source][c] for n in list(range(1,41))+[99]);check(f'RCV-transfer-{source}-{c}',total,oflow[source,c])
            for n in list(range(1,41))+[99]:flowrows.append(dict(after_round=rnd,house_district=n,source_candidate=source,destination=c,votes=flows[n,rnd,source][c],statewide_official_total=oflow[source,c]))
    write('rcv-district-rounds.csv',out);write('rcv-statewide-round-checks.csv',state);write('rcv-district-transfers.csv',flowrows)
    return units,ballots,methodballots,official,oflow

def targets(groups,names):
    rows=[];states=[];summary=[]
    for year,pair in [(2020,('Gross, Al','Sullivan, Dan')),(2024,('Harris/Walz','Trump/Vance'))]:
        g=groups[year];opp,rep=pair;T0=sum(v[opp]+v[rep] for v in g.values());M0=sum(v[opp]-v[rep] for v in g.values())
        for mix,volume in [('low_2022_statewide_ballots',267047),('base_2024_statewide_ballots',340981),('high_2020_statewide_ballots',361400),('historical_actual',BALLOTS[year])]:
            scale=volume/BALLOTS[year];T=T0*scale;M=M0*scale
            for target in [0,.01]:
                delta=(target-M/T)/2;contrib=[]
                for n in sorted(g):
                    v=g[n];tc=(v[opp]+v[rep])*scale;s=v[opp]/(v[opp]+v[rep]);q=s+delta;net=tc*(2*q-1);contrib.append(net)
                    other=M-tc*(2*s-1);cond=(tc+target*T-other)/(2*tc)
                    r=dict(scenario=f'{year}_{mix}',baseline_year=year,boundary_vintage='2020 pre-redistricting' if year==2020 else '2024 election native units',house_district=n,unit_type='house_district' if n!=99 else 'nongeographic_administration',opposition_candidate=opp,republican_candidate=rep,opposition_votes=v[opp],republican_votes=v[rep],other_votes=sum(v.values())-v[opp]-v[rep],baseline_opposition_pair_share=s,baseline_margin_pp=100*(2*s-1),baseline_net_votes=v[opp]-v[rep],scenario_statewide_ballots=volume,expected_pair_votes=tc,weight=tc/T,target_statewide_margin_pp=100*target,uniform_share_shift_pp=100*delta,target_opposition_share=q,target_margin_pp=100*(2*q-1),target_net_votes=net,net_gain_for_one_share_pp=.02*tc,conditional_selected_unit_share=cond,conditional_status='already secured at zero' if cond<0 else 'impossible even at 100%' if cond>1 else 'feasible',uniform_feasible=0<=q<=1)
                    rows.append(r)
                check(f'{year}-{mix}-{target}-weights',sum(x['weight'] for x in rows[-41:]),1)
                check(f'{year}-{mix}-{target}-target-net',sum(contrib),target*T)
                assert all(x['uniform_feasible'] for x in rows[-41:])
                states.append(dict(scenario=f'{year}_{mix}',baseline_year=year,opposition_candidate=opp,republican_candidate=rep,scenario_statewide_ballots=volume,expected_pair_votes=T,fixed_share_net_votes=M,fixed_share_margin_pp=100*M/T,target_margin_pp=100*target,uniform_opposition_share_shift_pp=100*delta,target_net_votes=sum(contrib),turnout_assumption='Historical statewide ballot-volume envelope scaled within this election own unit mix; no cross-year geographic weights'))
        for n in sorted(g):
            v=g[n];total=v[opp]+v[rep];s=v[opp]/total;net=v[opp]-v[rep]
            summary.append(dict(baseline_year=year,house_district=n,opposition=opp,republican=rep,opposition_votes=v[opp],republican_votes=v[rep],other_votes=sum(v.values())-total,pair_share=s,margin_pp=100*(2*s-1),net_votes=net,weight=total/T0,winner=opp if net>0 else rep if net<0 else 'Tie',closeness_band='within 5 pp' if abs(200*s-100)<=5 else '5–10 pp' if abs(200*s-100)<=10 else 'over 10 pp'))
    write('unit-target-scenarios.csv',rows);write('state-target-scenarios.csv',states);write('two-candidate-unit-summary.csv',summary)

def rcv_scenarios(official,flow):
    C,K,M,T=NAMES22[:4];a=official[1,C];k=official[1,K];m=official[1,M];t=official[1,T]
    c2=official[2,C];c_transfer=flow[C,M]+flow[C,T];inactive=flow[C,'Exhausted']+flow[C,'Overvotes'];actual_fraction=flow[C,M]/c_transfer
    rows=[]
    settings=[('published_replay',actual_fraction,0,1),('chesbro_pool_50_50_continuing',.5,0,1),('chesbro_pool_40pct_to_M',.4,0,1),('5000_M_first_preferences_switch_to_T',actual_fraction,-5000,1),('10000_M_first_preferences_switch_to_T',actual_fraction,-10000,1)]
    for label,cf,shift,scale in settings:
        assert 0<=cf<=1 and m+shift>=0 and t-shift>=0
        assert k<min(a,m+shift,t-shift) and c2<min(m+shift+flow[K,M],t-shift+flow[K,T])
        assert max(a,k,m+shift,t-shift)<(a+k+m+t)/2
        fm=(m+shift+flow[K,M]+cf*c_transfer)*scale;ft=(t-shift+flow[K,T]+(1-cf)*c_transfer)*scale;blank=3271*scale;ex=(flow[K,'Exhausted']+flow[C,'Exhausted'])*scale;ov=(499+flow[K,'Overvotes']+flow[C,'Overvotes'])*scale
        check(f'RCV-scenario-{label}-conservation',fm+ft+blank+ex+ov,266797*scale)
        rows.append(dict(scenario=label,scope_ballots=266797*scale,first_preference_switch_T_to_M=shift,chesbro_pool_continuing_to_M_fraction=cf,chesbro_pool_inactive=inactive,murkowski_final=fm,tshibaka_final=ft,continuing_votes=fm+ft,murkowski_minus_tshibaka=fm-ft,murkowski_continuing_share=fm/(fm+ft),blanks=blank,exhausted=ex,overvotes=ov,winner=M if fm>ft else T if fm<ft else 'tie',assumptions='Fixed observed round1 K/C pools; fixed Kelley transfers; fixed Chesbro inactive count; C pool includes901 transfers from K; final two REP; no probability'))
    write('rcv-state-scenarios.csv',rows)
    threshold=(official[2,T]-official[2,M]+c_transfer)/(2*c_transfer)
    (ROOT/'rcv-transfer-threshold.json').write_text(json.dumps(dict(chesbro_round2_pool=c2,continuing_transfers=c_transfer,inactive=inactive,actual_murkowski_fraction=actual_fraction,tie_murkowski_fraction=threshold,scope='Conditional on same round2 candidates, totals and inactive count; not a 2026 threshold'),indent=2)+'\n')

def rcv_turnout_scenarios(units,ballots):
    rows=[];unitrows=[];ns=list(range(1,41))+[99];C,K,M,T=NAMES22[:4]
    for label,tm,mm in [('published_replay',1,1),('Tshibaka_won_districts_plus10_Murkowski_won_minus10',1.1,.9),('Tshibaka_won_districts_minus10_Murkowski_won_plus10',.9,1.1)]:
        totals=collections.Counter();r1=collections.Counter();r2=collections.Counter();B=0
        for n in ns:
            mult=1 if n==99 else tm if units[n,3][T]>units[n,3][M] else mm
            B+=ballots[n]*mult
            for c,v in units[n,3].items():totals[c]+=v*mult
            for c,v in units[n,1].items():r1[c]+=v*mult
            for c,v in units[n,2].items():r2[c]+=v*mult
            unitrows.append(dict(scenario=label,house_district=n,cvr_ballots=ballots[n],turnout_multiplier=mult,expected_cvr_ballots=ballots[n]*mult,murkowski_final=units[n,3][M]*mult,tshibaka_final=units[n,3][T]*mult,net_contribution=(units[n,3][M]-units[n,3][T])*mult))
        check(f'RCV-turnout-{label}-conservation',sum(totals.values()),B)
        assert r1[K]<min(r1[C],r1[M],r1[T]) and r2[C]<min(r2[M],r2[T])
        assert max(r1[c] for c in [C,K,M,T])<sum(r1[c] for c in [C,K,M,T])/2
        rows.append(dict(scenario=label,expected_cvr_ballots=B,murkowski_final=totals[M],tshibaka_final=totals[T],continuing_votes=totals[M]+totals[T],net_murkowski_minus_tshibaka=totals[M]-totals[T],margin_pp=100*(totals[M]-totals[T])/(totals[M]+totals[T]),winner=M if totals[M]>totals[T] else T,assumptions='2022 CVR own HD profiles only; all41 units retained; HD99 fixed; same elimination order verified; arbitrary10percent composition sensitivity, not researched2026 turnout'))
    write('rcv-native-turnout-scenarios.csv',rows);write('rcv-native-turnout-contributions.csv',unitrows)

def selected(args,groups):
    year=args.year;g=groups[year];pair=('Gross, Al','Sullivan, Dan') if year==2020 else ('Harris/Walz','Trump/Vance');opp,rep=pair;n=args.unit;assert n in g
    tc=(g[n][opp]+g[n][rep])*args.selected_turnout_scale
    assert tc>0
    others=0;T=tc
    for j,v in g.items():
        if j==n:continue
        tj=v[opp]+v[rep];q=v[opp]/tj+args.others_share_shift_pp/100
        if not 0<=q<=1:raise ValueError('Others share shift creates an out-of-range share')
        T+=tj;others+=tj*(2*q-1)
    q=(tc+args.target_margin_pp/100*T-others)/(2*tc)
    return dict(baseline_year=year,unit=n,opposition=opp,republican=rep,expected_selected_pair_votes=tc,total_expected_pair_votes=T,others_net_votes=others,target_margin_pp=args.target_margin_pp,required_opposition_pair_share=q,required_share_percent=100*q,status='already secured even at zero' if q<0 else 'impossible even at 100%' if q>1 else 'feasible',baseline_pair_share=g[n][opp]/(g[n][opp]+g[n][rep]),note='All other units included, using their own historical weights; third candidates fixed outside named pair. Conditional history, not RCV/2026 forecast')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--year',type=int,choices=[2020,2024],default=2024);ap.add_argument('--unit',type=int);ap.add_argument('--selected-turnout-scale',type=float,default=1);ap.add_argument('--others-share-shift-pp',type=float,default=0);ap.add_argument('--target-margin-pp',type=float,default=0);args=ap.parse_args()
    groups,names,parties,base,byunit22=firstchoices();units,ballots,methodballots,official,flow=rcv(base,byunit22);targets(groups,names);rcv_scenarios(official,flow);rcv_turnout_scenarios(units,ballots)
    write('../county-baselines.csv',base);write('validation-checks.csv',CHECKS)
    if args.unit is not None:print(json.dumps(selected(args,groups),indent=2))
    else:print(json.dumps(dict(validation_checks=len(CHECKS),all_passed=True,baseline_rows=len(base),native_hd_groups_per_election=41,rcv_ballots=sum(ballots.values()),rcv_method_ballots=dict(methodballots)),indent=2))
if __name__=='__main__':main()
