from fetch_maps import *
urls={
'cuyahoga-webmap':'https://www.arcgis.com/sharing/rest/content/items/42065a3a00e84159854273743e38b807/data?f=pjson',
'columbiana':'https://columbiana.boe.ohio.gov/link-resources/maps/',
'wood':'https://boe.woodcountyohio.gov/231/Maps',
'geauga':'https://recorder.co.geauga.oh.us/document/voting-precincts/',
'miami':'https://www.boe.ohio.gov/miami/precinct-and-polling-location-info/',
'mahoning-home':'https://vote.mahoningcountyoh.gov/',
'wayne':'https://www.waynecountyoh.gov/',
'butler':'https://elections.bcohio.gov/voter_tools/maps.php',
'warren-home':'https://vote.warrencountyohio.gov/',
'portage':'https://www.portagecounty-oh.gov/board-elections/pages/maps',
'clark-gis':'https://ago.clarkcountyohio.gov/ccoarcgis/rest/services/WMAS/VotingPrecincts/MapServer?f=pjson',
'delaware-layer':'https://services2.arcgis.com/ziXVKVy3BiopMCCU/arcgis/rest/services/Precincts/FeatureServer?f=pjson',
'fairfield-layer':'https://services2.arcgis.com/L7YSCDUQyC7Biss6/arcgis/rest/services/Precincts/FeatureServer?f=pjson',
'portage-layer':'https://services3.arcgis.com/USPCOVt8MExYdEzE/arcgis/rest/services/Voting_Precincts/FeatureServer?f=pjson',
'lucas-layer':'https://services3.arcgis.com/T8dczfwPixv79EgZ/arcgis/rest/services/Lucas_County_Wards_and_Precincts/FeatureServer?f=pjson',
'muskingum-layer':'https://services5.arcgis.com/N1ybEAKiuuUIL8Mz/arcgis/rest/services/VotingPrecincts/FeatureServer?f=pjson',
'montgomery-gis':'https://www.mcrealestate.org/forms/htmlframe.aspx?mode=content/GISDownloads.htm',
'summit-gis':'https://data-summitcounty.opendata.arcgis.com/',
'licking':'https://lickingcounty.gov/menu_depts/mapping_gis/'}
def work(kv):
 k,u=kv;m,b=fetch('more/'+k,u);print(k,m['status'],len(b),flush=True)
 try:
  d=json.loads(b);print(k,[(x.get('id'),x.get('name'),x.get('url')) for x in d.get('layers',d.get('operationalLayers',[]))],flush=True)
 except:print(k,[(u,t) for u,t in links(b,m.get('final_url',u)) if re.search('map|precinct|gis|\.pdf|\.zip',u+' '+t,re.I)][-40:],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:list(ex.map(work,urls.items()))
