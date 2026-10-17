import inventory as m
import concurrent.futures,json
urls={
'washtenaw-results':'https://www.washtenaw.org/election-results',
'macomb-archive':'https://www.macombgov.org/departments/clerk-register-deeds/elections/past-election-results',
'livingston-results':'https://milivcounty.gov/elections/election-results/',
'muskegon-results':'https://co.muskegon.mi.us/507/Election-Results',
'st-clair-archive':'https://stclaircountyclerk.org/Page/Elections_Historical_Election_Results',
'detroit':'https://detroitmi.gov/departments/elections',
'detroit-2026-notice':'https://detroitmi.gov/news/how-find-detroit-primary-election-results-aug-4-2026',
'sos-results':'https://www.michigan.gov/sos/elections/election-results-and-data',
'sos-early-faq':'https://www.michigan.gov/sos/faqs/elections-and-campaign-finance/early-in-person-voting',
'sos-participation':'https://www.michigan.gov/sos/elections/election-results-and-data/voter-participation-dashboard',
'sos-absentee':'https://www.michigan.gov/sos/elections/voting/absentee-voting',
'sos-election-day':'https://www.michigan.gov/sos/elections/voting/vote-on-election-day',
'genesee-vendor':'https://results.enr.clarityelections.com/MI/Genesee/122430/',
'oakland-vendor':'https://results.enr.clarityelections.com/MI/Oakland/127284/',
'saginaw-vendor':'https://app.enhancedvoting.com/results/public/saginaw-county-mi'}
def one(x):
 n,u=x;r=m.fetch(u);(m.ROOT/(n+'.json')).write_text(json.dumps(r,indent=2));print(n,r.get('http_status'),flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as e:list(e.map(one,urls.items()))
