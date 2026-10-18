#!/usr/bin/env python3
"""Parse official tabular returns and certified PDFs, keeping both vintages.
Stdlib + Poppler pdftotext. All writes are restricted to assigned paths.
"""
import csv, collections, hashlib, io, json, pathlib, re, subprocess, zipfile
BASE=pathlib.Path(__file__).resolve().parent
CONTESTS={2020:'US SENATE',2022:'US SENATE',2024:'US PRESIDENT'}
DATES={2020:'2020-11-03',2022:'2022-11-08',2024:'2024-11-05'}
VERSION='1'

def write_csv(path,rows):
    assert rows,path
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def fips_map():
    rows=csv.DictReader((BASE/'census-national-county2020.txt').open(),delimiter='|')
    out={r['COUNTYNAME'].removesuffix(' County').upper():(r['STATEFP']+r['COUNTYFP'],r['COUNTYNAME'].removesuffix(' County')) for r in rows if r['STATE']=='NC'}
    assert len(out)==100 and len(set(v[0] for v in out.values()))==100
    return out

def canonical_candidate(name):
    return {'Michelle Estelle Lewis':'Michelle Estelle Lewis (Write-In)', 'Claudia De la Cruz':'Claudia De la Cruz (Write-In)'}.get(name,name)

def pdf_parse(year,county=True):
    stem=f'{year}-certified-'+('county' if county else 'contest')
    subprocess.run(['pdftotext','-layout',str(BASE/(stem+'.pdf')),str(BASE/(stem+'.txt'))],check=True)
    data=(BASE/(stem+'.txt')).read_text()
    fmap=fips_map();result={};curcounty=None;curcontest=None;positions=None
    for page_number,page in enumerate(data.split('\f'),1):
        for line in page.splitlines():
            if line.startswith(('County ','Contest ')) and 'Choice' in line and 'Total Votes' in line:
                positions={x:line.index(x) for x in ['Contest','Choice','Party','Total Votes','Election Day']}
                continue
            if not positions:continue
            c=positions
            prefix=line[:c['Choice']].strip()
            choice=line[c['Choice']:c['Party']].strip()
            party=line[c['Party']:c['Total Votes']].strip()
            num=line[c['Total Votes']:c['Election Day']].strip()
            if county:
                countytext=line[:c['Contest']].strip()
                if countytext in fmap:curcounty=countytext
                contesttext=line[c['Contest']:c['Choice']].strip()
            else:contesttext=line[:c['Choice']].strip()
            # All target contests have a one-line title. Other wrapped titles cannot match.
            if contesttext and (contesttext.startswith(('US ','NC ')) or county and countytext in fmap):
                curcontest=contesttext
            if curcontest!=CONTESTS[year]:continue
            if not re.fullmatch(r'[0-9][0-9,]*',num):continue
            assert choice and (not county or curcounty),(year,page_number,line)
            candidate=canonical_candidate(choice)
            key=(curcounty if county else 'STATE',candidate,party)
            assert key not in result,(year,key)
            # Every source row carries total and four disjoint methods.
            values=[int(x.replace(',','')) for x in re.findall(r'\d[\d,]*',line[c['Total Votes']:])]
            assert len(values)==5,(year,line,values)
            assert values[0]==sum(values[1:]),(year,line)
            result[key]={'votes':values[0],'election_day':values[1],'early_voting':values[2],'absentee_by_mail':values[3],'provisional':values[4],'pdf_page':page_number,'pdf_printed_page':page_number-(1 if year==2024 else 0)}
    if county:assert {k[0] for k in result}==set(fmap),(year,len(result),set(fmap)-{k[0] for k in result})
    return result

def zip_parse(year):
    contest=CONTESTS.get(year,'US SENATE');c=collections.defaultdict(collections.Counter);n=0;keys=set();ids=set();allrows=0;negative=0;fmap=fips_map()
    with zipfile.ZipFile(BASE/f'{year}-results.zip') as z:
        assert len(z.namelist())==1
        with z.open(z.namelist()[0]) as f:
            for row in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig'),delimiter='\t'):
                allrows+=1
                if row['Contest Name']!=contest:continue
                n+=1;ids.add(row['Contest Group ID']);county=row['County'];party=row['Choice Party'].strip().strip('\x00');candidate=row['Choice']
                if year==2014:candidate={'BARRY GURNEY (Write-In)':'Barry Gurney (Write-In)','DAVID WADDELL (Write-In)':'David Waddell (Write-In)','JOHN RHODES (Write-In)':'John Rhodes (Write-In)'}.get(candidate,candidate)
                key=(county,row['Precinct'],row['Contest Group ID'],candidate,party)
                assert key not in keys,(year,key)
                keys.add(key)
                assert county in fmap,(year,county)
                early='Early Voting' if 'Early Voting' in row else 'One Stop'
                vals=[int(row[x]) for x in ['Total Votes','Election Day',early,'Absentee by Mail','Provisional']]
                assert vals[0]==sum(vals[1:]),(year,row)
                if any(v<0 for v in vals):
                    assert year==2014,(year,row)
                    negative+=1
                c[(county,candidate,party)].update(dict(zip(['votes','election_day','early_voting','absentee_by_mail','provisional'],vals)))
    assert len(ids)==1,(year,ids)
    return c,{'year':year,'contest':contest,'all_source_rows':allrows,'selected_rows':n,'contest_group_id':next(iter(ids)),'county_count':len({k[0] for k in c}),'duplicate_selected_rows':0,'method_total_errors':0,'negative_count_rows':negative}

def main():
    fmap=fips_map();manifest=json.loads((BASE/'manifest.json').read_text());sources={m['file']:m for m in manifest['sources']}
    for m in manifest['sources']:
        assert hashlib.sha256((BASE/m['file']).read_bytes()).hexdigest()==m['sha256'],m['file']
    checks=[];candidate_rows=[];reconciliation=[];diffs=[];baselines=[];zipchecks=[];allstates=[];countychecks=[]
    for year,contest in CONTESTS.items():
        cert=pdf_parse(year);state=pdf_parse(year,False);raw,zcheck=zip_parse(year);zipchecks.append(zcheck)
        assert len(state) in [4,6,9],(year,state)
        statekeys={(cand,party) for _,cand,party in state}
        assert {(c,p) for _,c,p in cert}==statekeys,(year,'county candidates')
        assert {(c,p) for _,c,p in raw}==statekeys,(year,'raw candidates')
        for (_,cand,party),values in state.items():
            computed={field:sum(v[field] for (county,c,p),v in cert.items() if c==cand and p==party) for field in ['votes','election_day','early_voting','absentee_by_mail','provisional']}
            assert computed=={f:values[f] for f in computed},(year,cand,computed,values)
            rawtotal=sum(v['votes'] for (county,c,p),v in raw.items() if c==cand and p==party)
            reconciliation.append({'year':year,'contest':contest,'candidate':cand,'party':party,'certified_county_sum':computed['votes'],'certified_statewide_total':values['votes'],'county_minus_state':computed['votes']-values['votes'],'election_results_zip_sum':rawtotal,'zip_minus_certified':rawtotal-values['votes'],'certified_state_pdf_page':values['pdf_page'],'state_source_url':sources[f'{year}-certified-contest.pdf']['url']})
            allstates.append({'year':year,'contest':contest,'candidate':cand,'party':party,**values,'source_file':f'{year}-certified-contest.pdf'})
        for county in sorted(fmap):
            local={k:v for k,v in cert.items() if k[0]==county}
            assert len([1 for _,c,p in local if p=='DEM'])==1 and len([1 for _,c,p in local if p=='REP'])==1
            for (cty,cand,party),v in local.items():
                candidate_rows.append({'year':year,'election_date':DATES[year],'contest':contest,'contest_group_id':zcheck['contest_group_id'],'county':fmap[county][1],'county_fips':fmap[county][0],'candidate':cand,'party':party,**v,'source_status':'NCSBE certified-results archive PDF','source_file':f'{year}-certified-county.pdf','source_url':sources[f'{year}-certified-county.pdf']['url'],'retrieved_at_utc':sources[f'{year}-certified-county.pdf']['retrieved_at_utc']})
            D=sum(v['votes'] for k,v in local.items() if k[2]=='DEM');R=sum(v['votes'] for k,v in local.items() if k[2]=='REP');total=sum(v['votes'] for v in local.values());other=total-D-R;T=D+R;net=D-R
            ss=sum(v['votes'] for v in cert.values());st=sum(v['votes'] for k,v in cert.items() if k[2] in ['DEM','REP'])
            baselines.append({'year':year,'election_date':DATES[year],'contest':contest,'contest_group_id':zcheck['contest_group_id'],'county':fmap[county][1],'county_fips':fmap[county][0],'dem_candidate':next(k[1] for k in local if k[2]=='DEM'),'rep_candidate':next(k[1] for k in local if k[2]=='REP'),'dem_votes':D,'rep_votes':R,'other_votes':other,'contest_votes':total,'major_party_votes':T,'dem_two_party_share':D/T,'d_minus_r_two_party_margin':net/T,'d_minus_r_all_vote_margin':net/total,'net_d_minus_r':net,'winner':('D' if D>R else 'R' if R>D else 'tie'),'margin_band':('within_5pp' if abs(net/T)<=.05 else 'over_5_to_10pp' if abs(net/T)<=.10 else 'over_10pp'),'contest_turnout_weight':total/ss,'major_party_turnout_weight':T/st,'other_contest_share':other/total,'other_candidates_json':json.dumps([{'candidate':k[1],'party':k[2],'votes':v['votes']} for k,v in local.items() if k[2] not in ['DEM','REP']],separators=(',',':')),'source_status':'NCSBE certified-results archive PDF','source_file':f'{year}-certified-county.pdf','source_url':sources[f'{year}-certified-county.pdf']['url'],'retrieved_at_utc':sources[f'{year}-certified-county.pdf']['retrieved_at_utc'],'ballots_cast':'','undervotes':'','overvotes':'','registered_voters':''})
            countychecks.append({'year':year,'county':fmap[county][1],'county_fips':fmap[county][0],'certified_contest_votes':total,'zip_contest_votes':sum(v['votes'] for k,v in raw.items() if k[0]==county),'dem_plus_rep_plus_other_minus_contest':D+R+other-total})
        for k in sorted(set(cert)|set(raw)):
            cv=cert.get(k,{}).get('votes',0);rv=raw.get(k,{}).get('votes',0)
            if cv!=rv:diffs.append({'year':year,'county':fmap[k[0]][1],'county_fips':fmap[k[0]][0],'candidate':k[1],'party':k[2],'zip_votes':rv,'certified_votes':cv,'zip_minus_certified':rv-cv,'certified_pdf_page':cert.get(k,{}).get('pdf_page','not listed')})
    supplemental,zcheck=zip_parse(2014);zipchecks.append(zcheck)
    low=collections.Counter()
    for (county,cand,party),v in supplemental.items():low[(cand,party)]+=v['votes']
    write_csv(BASE/'2014-senate-state-zip-extract.csv',[{'year':2014,'contest':'US SENATE','candidate':c,'party':p,'votes':v,'source_status':'NCSBE Election Results ZIP; statewide-only sensitivity anchor'} for (c,p),v in sorted(low.items())])
    # Independently reconcile the supplemental 2014 anchor to House Clerk's primary publication.
    subprocess.run(['pdftotext','-layout',str(BASE/'house-2014-statistics.pdf'),str(BASE/'house-2014-statistics.txt')],check=True)
    house=(BASE/'house-2014-statistics.txt').read_text().split('NORTH CAROLINA',1)[1].split('FOR UNITED STATES REPRESENTATIVE',1)[0]
    house_names={'Kay Hagan':'Kay R. Hagan','Write-In (Miscellaneous)':'Write-in (Miscellaneous)'}
    low_checks=[]
    for (cand,party),votes in sorted(low.items()):
        name=house_names.get(cand,cand.removesuffix(' (Write-In)'))
        hit=next(line for line in house.splitlines() if name in line)
        official=int(re.search(r'([0-9][0-9,]*)\s*$',hit).group(1).replace(',',''))
        assert votes==official,(cand,votes,official)
        low_checks.append({'year':2014,'candidate':cand,'party':party,'ncsbe_zip_sum':votes,'house_clerk_total':official,'difference':votes-official})
    write_csv(BASE/'2014-anchor-reconciliation.csv',low_checks)
    by_fips=collections.defaultdict(dict)
    for b in baselines:by_fips[b['county_fips']][b['year']]=b['winner']
    for b in baselines:
        outcomes=by_fips[b['county_fips']]
        b['cross_election_winner_pattern']='2020_senate:'+outcomes[2020]+';2022_senate:'+outcomes[2022]+';2024_president:'+outcomes[2024]
        b['cross_election_classification']='D_all_three' if set(outcomes.values())=={'D'} else 'R_all_three' if set(outcomes.values())=={'R'} else 'mixed_winners'
    write_csv(BASE.parent/'county-baselines.csv',baselines)
    write_csv(BASE/'county-candidates.csv',candidate_rows)
    write_csv(BASE/'certified-state-candidates.csv',allstates)
    write_csv(BASE/'candidate-reconciliation.csv',reconciliation)
    write_csv(BASE/'county-reconciliation.csv',countychecks)
    write_csv(BASE/'zip-certified-differences.csv',diffs)
    (BASE/'extraction-checks.json').write_text(json.dumps({'parser_version':VERSION,'zip_files':zipchecks,'certified_baseline_rows':len(baselines),'certified_candidate_rows':len(candidate_rows),'state_candidate_reconciliations':len(reconciliation),'county_state_candidate_mismatches':sum(r['county_minus_state']!=0 for r in reconciliation),'raw_zip_certified_different_candidate_county_rows':len(diffs),'geography':'100 Census county FIPS in each of three contests; exact name join; no precinct geography inferred','missing_zero_rule':'Certified PDFs omit some zero write-in entries. No synthetic candidate rows are added; zero is used only for raw-vs-certified comparison of identified candidates in complete county contest tables.'},indent=2)+'\n')
    print('baseline rows',len(baselines),'candidate rows',len(candidate_rows),'reconciliation',len(reconciliation),'zip differences',diffs)
if __name__=='__main__':main()
