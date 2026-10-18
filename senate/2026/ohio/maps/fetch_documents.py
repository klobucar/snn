from fetch_maps import *
def read(key):
 return gzip.decompress((ROOT/'evidence'/key).with_suffix('.gz').read_bytes())
jobs=[]
def add(county,label,url,vintage,landing):jobs.append(dict(county=county,label=label,url=url,vintage=vintage,landing=landing))
# Embedded PDF URLs on the official Lake page; retain all 21 precinct maps, excluding legislative district maps.
for u in re.findall(r'(?:src|href)=["\']([^"\']*\.pdf[^"\']*)',read('sources/lake').decode(),re.I):
 if not re.search('House-Districts|SenateDistrict',u):add('lake',urllib.parse.unquote(u.rsplit('/',1)[-1]),u,'mixed dates in individual PDF, uploads not effective dates','https://www.lakecountyohio.gov/boe/precinct-maps/')
ls=links(read('probe/lorain'),'https://www.voteloraincountyohio.gov/maps');start=next(i for i,(_,t) in enumerate(ls) if t=='Lorain County');end=next(i for i,(_,t) in enumerate(ls[start:],start) if t=='Ohio Court of Appeals District Maps')
for u,t in ls[start:end]:
 if '.pdf' in u:add('lorain',t,u,'published map; printed date to inspect','https://www.voteloraincountyohio.gov/maps')
for u,t in links(read('remaining/wayne-maps'),'https://www.waynecountyoh.gov/precincts-voter-ward-precinct-maps/'):
 if '.pdf' in u and ('Map' in u or 'map' in u):add('wayne',urllib.parse.unquote(u.rsplit('/',1)[-1]),u,'Map-0426 filename; verify printed date; no approval assumed','https://www.waynecountyoh.gov/precincts-voter-ward-precinct-maps/')
add('warren','Warren County precincts','https://vote.warrencountyohio.gov/doc/Maps/Voter_Precincts1.pdf','printed 2025-04-14','https://vote.warrencountyohio.gov/')
add('allen','Allen precinct maps','https://gis.allencountyohio.com/img/GIS/Precinct%20Maps.pdf','download page says updated 2023-05-01','https://gis.allencountyohio.com/GIS/Downloads.html')
add('geauga','Geauga recorder precincts','https://recorder.co.geauga.oh.us/wp-content/uploads/sites/21/2021/06/Voting-Precincts.pdf','printed 2020-08-19 historical','https://recorder.co.geauga.oh.us/document/voting-precincts/')
add('geauga','Geauga BOE 2025 precincts','https://www.boe.ohio.gov/geauga/c/upload/PrecinctPollingLocationMaps.pdf','printed 2025-09-09 per web inspection; raw may be blocked','https://www.boe.ohio.gov/geauga/precinct-and-polling-location-info/')
add('muskingum','Muskingum countywide precincts','https://www.muskingumcountyoh.gov/Media/Muskingum-County-Voting-Precincts.pdf','printed date to inspect','https://www.muskingumcountyoh.gov/Muskingum-County-Maps/')
add('miami','Miami countywide precincts','https://ftp.miamicountyohio.gov/BOE/2014%202016%20Precinct%20Maps/Precinct%20Maps/Miami%20Countywide%20Precinct%20Map.pdf','printed 2013-03-21 historical','https://www.boe.ohio.gov/miami/precinct-and-polling-location-info/')
add('miami','Miami 2017 precinct packet','https://ftp.miamicountyohio.gov/GIS/Board%20Of%20Elections-Precinct%20Maps/Finished%20PDF%20Precinct%20Maps/2017%20Precinct%20Maps.pdf','printed 2017-10-11 historical','https://www.boe.ohio.gov/miami/precinct-and-polling-location-info/')
# Exact same URLs retained once, regardless of number of landing-page appearances.
jobs=list({x['url']:x for x in jobs}.values())
def work(x):
 k='pdf/'+x['county']+'/'+re.sub('[^a-zA-Z0-9.-]+','-',x['label'])
 m,b=fetch(k,x['url'],raw=True);x.update(path=m['stored_path'],status=m['status'],is_pdf=b.startswith(b'%PDF'),sha256=m['sha256']);print(x['county'],x['label'],x['status'],len(b),x['is_pdf'],flush=True);return x
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=list(ex.map(work,jobs))
(ROOT/'documents.json').write_text(json.dumps(out,indent=2)+'\n')
