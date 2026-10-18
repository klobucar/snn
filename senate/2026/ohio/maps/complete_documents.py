from fetch_maps import *
D=json.loads((ROOT/'documents.json').read_text());known={d['url'] for d in D};targets=[]
for key,url in [('cities','https://boe.woodcountyohio.gov/233/Cities'),('townships','https://boe.woodcountyohio.gov/234/Townships')]:
 m,b=fetch('last/wood-'+key,url)
 for u,t in links(b,url):
  if '/DocumentCenter/View/' in u and u not in known:targets.append((u,t));known.add(u)
def work(ut):
 u,t=ut;k='wood-'+u.split('/View/')[1].split('/')[0];m,b=fetch('pdf/wood/'+k,u,raw=True)
 return dict(county='wood',label=t,url=u,landing='https://boe.woodcountyohio.gov/232/Maps',vintage='currently published municipal/township map; printed effective date inspected separately',path=m['stored_path'],status=m['status'],is_pdf=b.startswith(b'%PDF'),sha256=m['sha256'])
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:D.extend(ex.map(work,targets))
(ROOT/'documents.json').write_text(json.dumps(D,indent=2)+'\n');print('new Wood published PDFs',len(targets))
# Last current/historical primary alternatives; complete bytes required for usability.
urls={
 'summit-current-site':'https://www.summitcountyboe.gov/',
 'summit-old-precinct-pdf':'https://www.summitcountyboe.gov/wordpress/wp-content/uploads/2017/06/Ak-1-A.pdf',
 'tusc-one-archive':'https://web.archive.org/web/20230101if_/http://boe.co.tuscarawas.oh.us/pctmaps/Pre-1.pdf',
 'richland-one-archive':'https://web.archive.org/web/20200101if_/http://www.boe.co.richland.oh.us/pdf/MapRCPrecincts.pdf'}
def work2(kv):
 k,u=kv;m,b=fetch('last/'+k,u,raw='pdf' in k or 'archive' in k);print(k,m['status'],len(b),flush=True);return k,m
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:out=dict(ex.map(work2,urls.items()))
(ROOT/'last-current-attempts.json').write_text(json.dumps(out,indent=2)+'\n')
