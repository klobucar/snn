#!/usr/bin/env python3
"""Read the turnout worker's outputs and reconcile inside assigned paths only."""
import collections,csv,datetime,hashlib,json,pathlib
BASE=pathlib.Path(__file__).resolve().parent
ROOT=BASE.parent.parent
TURNOUT=BASE.parent/'turnout'
def read(path):
 with path.open() as f:return list(csv.DictReader(f))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    theirs_path=BASE.parent/'county-turnout.csv';theirs=read(theirs_path);ours=read(BASE.parent/'county-baselines.csv');out=[]
    t={r['county_fips']:r for r in theirs};assert len(t)==100 and len(theirs)==100
    b={(r['year'],r['county_fips']):r for r in ours}
    for y,prefix in [(2024,'president_2024'),(2022,'senate_2022')]:
        assert {f for year,f in b if year==str(y)}==set(t)
        for f,r in t.items():
            br=b[(str(y),f)];row={'year':y,'contest':br['contest'],'county':br['county'],'county_fips':f}
            for of,tf in [('dem_votes',prefix+'_d'),('rep_votes',prefix+'_r'),('other_votes',prefix+'_other'),('contest_votes',prefix+'_total')]:
                a=int(br[of]);c=int(r[tf]);row[of+'_partisanship']=a;row[of+'_turnout']=c;row[of+'_difference']=a-c
                assert a==c,(y,f,of,a,c)
            out.append(row)
    with (BASE/'turnout-reconciliation.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
    # Compare all candidate and method values from independent PDF parsers.
    cc=read(BASE/'county-candidates.csv');tc=read(TURNOUT/'certified-candidate-extract.csv')
    ours_candidates={(r['year'],r['county'].upper(),r['candidate'],r['party']):r for r in cc if r['year'] in ['2022','2024']}
    their_candidates={(r['year'],r['county_native'],r['candidate'],r['party']):r for r in tc if r['county_native']!='STATE'}
    assert len(ours_candidates)==1285 and set(ours_candidates)==set(their_candidates)
    comparisons=0
    for k,r in ours_candidates.items():
        for a,c in [('votes','total_votes'),('election_day','election_day'),('early_voting','early_voting'),('absentee_by_mail','absentee_by_mail'),('provisional','provisional')]:
            assert int(r[a])==int(their_candidates[k][c]),(k,a)
            comparisons+=1
        assert int(r['pdf_page'])==int(their_candidates[k]['pdf_page'])
    state_rows=read(BASE/'certified-state-candidates.csv')
    shared_state=[r for r in state_rows if r['year'] in ['2022','2024']]
    other_state={(r['year'],r['candidate'],r['party']):r for r in tc if r['county_native']=='STATE'}
    assert len(shared_state)==15 and len(other_state)==15
    for r in shared_state:
        tr=other_state[(r['year'],r['candidate'],r['party'])]
        for a,c in [('votes','total_votes'),('election_day','election_day'),('early_voting','early_voting'),('absentee_by_mail','absentee_by_mail'),('provisional','provisional')]:
            assert int(r[a])==int(tr[c])
    # Source vintage is proven by original-byte equality, not filename/date.
    their_manifest=json.loads((TURNOUT/'input-manifest.json').read_text())['sources']
    our_manifest={s['file']:s for s in json.loads((BASE/'manifest.json').read_text())['sources']}
    matches=[]
    for y in [2022,2024]:
        for kind in ['county','contest']:
            ourname=f'{y}-certified-{kind}.pdf';theirname=f'certified-{y}-{kind}.pdf'
            a=our_manifest[ourname];c=their_manifest[theirname]
            assert a['sha256']==c['sha256']==digest(TURNOUT/theirname)
            matches.append({'partisanship_file':ourname,'turnout_file':str((TURNOUT/theirname).relative_to(ROOT)),'sha256':a['sha256'],'same_original_bytes':True,'partisanship_retrieved_at_utc':a['retrieved_at_utc'],'turnout_retrieved_at_utc':c['retrieved_utc'],'url':a['url']})
    # Independently recover the all-choice 2024 volume priority from our baseline.
    ranked=sorted([r for r in ours if r['year']=='2024'],key=lambda r:-int(r['contest_votes']));state=sum(int(r['contest_votes']) for r in ranked);cum=0;priority=[]
    for r in ranked:
        if cum*5>=state*4:break
        priority.append(r['county_fips']);cum+=int(r['contest_votes'])
    assert len(priority)==38 and cum==4576486 and state==5699145
    assert set(priority)=={r['county_fips'] for r in theirs if r['smallest_80pct_set']=='1'}
    dependencies=[theirs_path,TURNOUT/'certified-candidate-extract.csv',TURNOUT/'input-manifest.json']
    result={'compared_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':True,'counties_per_shared_election':100,'shared_elections':['2024 US PRESIDENT','2022 US SENATE'],'county_rows_compared':len(out),'county_d_r_other_total_cells_compared':len(out)*4,'county_count_differences':0,'candidate_rows_compared':len(ours_candidates),'candidate_total_and_method_cells_compared':comparisons,'candidate_cell_differences':0,'state_candidate_rows_compared':15,'state_candidate_total_and_method_cells_compared':75,'candidate_pdf_page_differences':0,'same_primary_pdf_vintages':matches,'statewide_2024_president_contest_votes':state,'statewide_2024_president_d':2715378,'statewide_2024_president_r':2898424,'statewide_2024_president_other':85343,'top80_county_count_2024':len(priority),'top80_contest_votes_2024':cum,'top80_share_pct_2024':100*cum/state,'top80_county_fips':priority,'dependency_snapshots':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p),'bytes':p.stat().st_size} for p in dependencies],'writes':'only data/baselines/turnout-reconciliation.csv and turnout-reconciliation.json; turnout files read only'}
    (BASE/'turnout-reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['same_primary_pdf_vintages','top80_county_fips','dependency_snapshots']},indent=2))
if __name__=='__main__':main()
