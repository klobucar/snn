"""Enrich SOS inventory with explicitly observed second-level official channels."""
import csv,json,re
from pathlib import Path
P=Path(__file__).resolve().parent
f=P.parent/'official-results-sources.csv';rows=[r for r in csv.DictReader(f.open()) if r.get('scope','county')=='county'];fields=[k for k in rows[0] if k not in ['scope','deep_evidence','archive_2024','archive_2022','voting_method','source_timestamp_timezone','refresh_evidence','remaining_votes','manual_fallback']]+['scope','deep_evidence','archive_2024','archive_2022','voting_method','source_timestamp_timezone','refresh_evidence','remaining_votes','manual_fallback']
extra={'Monroe':['monroe-results'],'Eaton':['eaton-results'],'Lapeer':['lapeer-results'],'Lenawee':['lenawee-archive'],'Calhoun':['calhoun-vendor'],'Macomb':['macomb-archive'],'Washtenaw':['washtenaw-results'],'Livingston':['livingston-results'],'Muskegon':['muskegon-results'],'St. Clair':['st-clair-archive']}
for r in rows:
 r.update(scope='county',deep_evidence='',archive_2024='not individually verified',archive_2022='not individually verified',voting_method='unverified',source_timestamp_timezone='unverified',refresh_evidence='no cadence guarantee verified',remaining_votes='not verified',manual_fallback='Open SOS-linked clerk landing in browser; save dated snapshot or transcribe totals with unit/election/status and reviewer.')
 for n in extra.get(r['county'],[]):
  x=json.loads((P/(n+'.json')).read_text());r['deep_evidence']+='results-sources/'+n+'.json';r['linked_results_urls']+=' | '+' | '.join(y['url'] for y in x.get('links',[]) if re.search('result|clarity|enhanced|2024|2022',y['url']+' '+y['text'],re.I))
 if r['county']=='Kent':
  r['verification']='SOS legacy landing raw HTTP403; current county pages web-rendered; database raw HTTP200'
  r['linked_results_urls']+=' | https://www.kentcountymi.gov/335/Election-Results | https://www.kentcountymi.gov/197/Elections | https://electionstats.kentcountymi.gov/ | https://app.enhancedvoting.com/results/public/kent-county-mi/elections/11032026_20261005115447 | https://app.enhancedvoting.com/results/public/kent-county-mi/elections/08042026'
  r['deep_evidence']='results-sources/kent-wayne-followup.json; kent-current-results.html.meta.json; kent-current-elections.html.meta.json; kent-database.html.meta.json; kent-nov2026-vendor.html.meta.json'
  r['feed_status']='2026 Nov/Aug vendor linkage verified by web click; HTTP200 application shells only; feeds untested'
  r['archive_2024']=r['archive_2022']='official historical database linked; individual contest query untested'
  r['manual_fallback']='Open current /197/Elections or /335/Election-Results in browser; follow election-specific link; raw HTTP403 is not proof of human inaccessibility.'
 if r['county']=='Wayne':
  r['verification']='current official landing/Nov child indexed by web search; web open and raw curl HTTP403'
  r['linked_results_urls']+=' | https://www.waynecountymi.gov/Government/Elected-Officials/Clerk/Elections/Election-Results-Candidates/November-3rd-2026-General-Election'
  r['deep_evidence']='results-sources/kent-wayne-followup.json; wayne-current-followup.html.meta.json'
  r['feed_status']='current Nov2026 child indexed; outbound vendor authority not verified; feed untested'
 if r['county']=='Genesee':r.update(feed_status='2024 Clarity JSON downloaded and reconciled; 2026 untested',deep_evidence='results-sources/genesee-summary.json.meta.json; results-sources/schema-checks.json',archive_2024='linked Clarity 122430 and official PDFs',archive_2022='linked official summary and precinct PDFs',voting_method='not separated in inspected summary/details JSON')
 if r['county'] in ['Macomb','Livingston','St. Clair','Jackson','Kalamazoo','Berrien']:r.update(archive_2024='official archive links observed; see report',archive_2022='official archive links observed; see report')
 if r['county']=='Ottawa':r['linked_results_urls']+=' | https://www.miottawavotes.gov/MI/Ottawa/ | https://miottawa.org/clerk/elections/reports/';r['deep_evidence']='results-sources/ottawa-raw.html (JavaScript button URLs); ottawa-vendor.html.meta.json'
 if r['county']=='Jackson':r['linked_results_urls']+=' | https://www.mijackson.org/1799/Current-Election-Results | https://www.mijackson.org/1798/Election-Results-Archive';r['deep_evidence']='results-sources/jackson-alternate.html; jackson-current.html; jackson-archive.html'
 if r['county']=='Berrien':r['linked_results_urls']+=' | https://app.enhancedvoting.com/results/public/berrien-county-mi/elections/NovemberGeneral11052024';r['deep_evidence']='official-results.md: web retrieval of county archive; direct curl 403'
 if r['county']=='Kalamazoo':r['linked_results_urls']+=' | https://www.kalcounty.gov/454/2024-Election-Results | https://www.kalcounty.gov/520/2022-Election-Results';r['deep_evidence']='official-results.md: official archive web retrieval; direct curl 403'
for name,scope,n in [('Michigan SOS/BOE','state','sos-results'),('Michigan participation (not results)','state','sos-participation'),('Detroit','municipal','detroit-2026-notice')]:
 x=json.loads((P/(n+'.json')).read_text());r={k:'' for k in fields};r.update(county=name,scope=scope,authority_url=x['url'],landing_url=x['url'],resolved_url=x.get('final_url',''),http_status=x.get('http_status',''),verification='official page retrieved',research_date='2026-10-17',evidence_file='results-sources/'+n+'.json',linked_results_urls=' | '.join(y['url'] for y in x.get('links',[]) if re.search('votehistory|enhancedvoting',y['url'])),feed_status='not vote results' if n=='sos-participation' else 'landing/link verified; feed untested');rows.append(r)
with f.open('w') as out:w=csv.DictWriter(out,fieldnames=fields);w.writeheader();w.writerows(rows)
assert len([r for r in rows if r['scope']=='county'])==83
assert len(set(r['county_fips'] for r in rows if r['scope']=='county'))==83
print('83 counties + 3 state/municipal channels; unique FIPS verified')
