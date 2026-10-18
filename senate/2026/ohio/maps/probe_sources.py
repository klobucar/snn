from fetch_maps import *
urls={
'boe-nonwww':'https://boe.ohio.gov/summit/precinct-and-polling-location-info/maps/',
'boe-pdf':'https://www.boe.ohio.gov/fairfield/c/pdf/FairfieldCoVotingPcts.pdf',
'hamilton-www':'https://www.votehamiltoncountyohio.gov/campaign-media/maps/',
'warren':'https://vote.warrencountyohio.gov/doc/Maps/Voter_Precincts1.pdf',
'lorain':'https://www.voteloraincountyohio.gov/maps',
'medina':'https://www.boe.ohio.gov/medina/precinct-and-polling-location-info/maps-of-medina-county/',
'cuyahoga-app':'https://www.arcgis.com/sharing/rest/content/items/c676abf37dfc4f27a23d6258f62b8b11/data?f=json',
'cagis':'https://services.arcgis.com/JyZag7oO4NteHGiq/arcgis/rest/services/Open_Data_Feature_Collection/FeatureServer?f=pjson',
'stark':'https://scgisa.starkcountyohio.gov/arcgis/rest/services/BoardOfElections/PollingLocationsAndPrecincts/MapServer?f=pjson',
'delaware':'https://gis.co.delaware.oh.us/secondary_nav/main-page-links/',
'mahoning':'https://vote.mahoningcountyoh.gov/172/Precinct-Polling-Location-Maps',
'clermont-zip':'https://maps.clermontcountyohio.gov/gis/VotingPrecincts.zip',
'greene-gis':'https://gis.greenecountyohio.gov/webgis2/rest/services/OpenData/OpenData/MapServer/20?f=pjson'}
def work(kv):
 k,u=kv;m,b=fetch('probe/'+k,u,raw=u.endswith(('.pdf','.zip')));print(k,m['status'],len(b),b[:80],flush=True)
 if not u.endswith(('.pdf','.zip')):
  try:
   d=json.loads(b);print(k,json.dumps(d)[:2500],flush=True)
  except:print(k,[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('map|precinct|gis|\.pdf|\.zip',u+' '+t,re.I)][:40],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(work,urls.items()))
