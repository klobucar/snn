from acquire import *
service('geauga',('https://gcgis.geauga.oh.gov/arcgis/rest/services/Voting_Precincts/MapServer/0','Geauga County GIS official .gov service; county organization app ec316... → webmap 56cdd...','webmap layer titled Voting Precincts 2026; legal November approval not independently established'))
urls={'tusc-http-pdf':'http://boe.co.tuscarawas.oh.us/pctmaps/Pre-1.pdf','tusc-gov-pdf':'https://boe.co.tuscarawas.oh.gov/pctmaps/Pre-1.pdf','richland-old-packet':'https://web.archive.org/web/20220124071430if_/https://www.boe.ohio.gov/richland/c/pdf/PrecinctMaps.pdf'}
for k,u in urls.items():
 m,b=fetch('late7/'+k,u,raw=True);print(k,m['status'],len(b),b[:15],flush=True)
