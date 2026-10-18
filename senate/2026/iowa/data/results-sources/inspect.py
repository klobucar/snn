#!/usr/bin/env python3
"""Reconstruct PDFs, embedded ArcGIS HTML, and observed vendor assets."""
import json,re,subprocess,sys
from urllib.parse import unquote,parse_qs,urlparse,urljoin,urldefrag
import research as r

def embedded():
 out=[];tasks=[]
 for a in r.ledger():
  if not a.get('view_path') or a.get('status')!=200:continue
  b=r.raw(a).decode('utf-8',errors='replace')
  for i,m in enumerate(re.finditer(r'"(%7[Bb][^"\n]+)"',b)):
   try:o=json.loads(unquote(m[1]))
   except ValueError:continue
   if 'site' not in str(o).lower():continue
   def walk(x,p=''):
    if isinstance(x,dict):
     for k,v in x.items():yield from walk(v,p+'/'+k.replace('~','~0').replace('/','~1'))
    elif isinstance(x,list):
     for j,v in enumerate(x):yield from walk(v,p+'/'+str(j))
    elif isinstance(x,str) and '<a ' in x:yield p,x
   for pointer,s in walk(o):
    v=r.view(s.encode(),a['final_url']);out.append({'source_id':a['id'],'source_encoded_char_position':m.start(),'source_json_pointer':pointer,**v})
  if 'viewer.html?' in a.get('final_url',''):
   f=parse_qs(urlparse(a['final_url']).query).get('file',[])
   if f:tasks.append((a['id']+'-payload',urljoin(a['final_url'],f[0]),a['final_url'],'Actual PDF.js file query parameter'))
 r.dump(r.ROOT/'embedded-views.json',out)
 for f in ['19061']:
  links={}
  for v in out:
   if v['source_id'].startswith('county-'+f+'-'):
    for l in v['links']:
     if any(s in l['url'] for s in ['/pages/election-results','/pages/election-upcoming','/pages/sample-ballots']):links[l['url']]=l
  for j,(u,l) in enumerate(links.items()):tasks.append(('county-'+f+'-embedded'+str(j),u,'embedded JSON in '+next(v['source_id'] for v in out if v['source_id'].startswith('county-'+f+'-')),l['text']))
 r.acquire(tasks)

def pdfs():
 n=0
 for a in r.ledger():
  if a.get('status')!=200 or not a.get('parts'):continue
  b=r.raw(a)
  if not b.startswith(b'%PDF'):continue
  p=r.ROOT/'extracts'/(a['id']+'.txt')
  if p.exists():continue
  t=subprocess.run(['pdftotext','-layout','-','-'],input=b,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout.decode();p.write_text(t);n+=1
 print('New full PDF text extractions',n)

def app():
 m=r.ledger();tasks=[]
 for a in sorted(m,key=lambda x:0 if x['id']=='county-19153-linked6' else 1):
  if a.get('status')!=200 or not a.get('view_path'):continue
  if 'electionresults.iowa.gov' not in a.get('final_url',''):continue
  for x in json.loads((r.ROOT/a['view_path']).read_text())['resources']:
   if re.search(r'/main\.[^/]+\.js$',x['url']):tasks.append(('vendor-current-main',x['url'],a['final_url'],'Actual script src'));break
  if tasks:break
 r.acquire(tasks)
 m=r.ledger();a=next((x for x in m if x['id']=='vendor-current-main'),None)
 if not a or a.get('status')!=200:return
 js=r.raw(a).decode()
 assert '"web.json"' in js and '"current_ver.txt"' in js
 shell=next(x for x in m if x.get('final_url')==a['parent_url'])
 baseurl=shell['final_url'];r.acquire([('vendor-current-webconfig',urljoin(baseurl,'web.json'),a['url'],'Observed WebConfig enum and ./web.json')])
 cfg=json.loads(r.raw(next(x for x in r.ledger() if x['id']=='vendor-current-webconfig')))
 base=cfg['jsonUri'].rstrip('/')+'/'+cfg['State']+'/'+cfg['EID']
 r.acquire([('vendor-current-version',base+'/current_ver.txt',a['url'],'Observed getBaseUri/FileName.Version')])
 ver=r.raw(next(x for x in r.ledger() if x['id']=='vendor-current-version')).decode().strip()
 r.acquire([('vendor-current-config',base+'/'+ver+'/json/config.json',a['url'],'Observed getUri/FileName.Config')])
 cfg2=json.loads(r.raw(next(x for x in r.ledger() if x['id']=='vendor-current-config')))
 lang=cfg2['lang']
 r.acquire([('vendor-current-'+key,base+'/'+ver+'/'+suffix,a['url'],'Observed client filename/getUri template; native config EID and version') for key,suffix in [('settings','json/'+lang+'/electionsettings.json'),('status','json/status.json'),('xml','reports/detailxml.zip')]])
 r.dump(r.ROOT/'current-app-observation.json',{'base':base,'version':ver,'config':cfg,'observation_scope':'Actual linked existing election; election identity must be checked, never assumed November2026'})
if __name__=='__main__':globals()[sys.argv[1]]()
