#!/usr/bin/env python3
"""Offline PDF inspection and all-page contact sheets, preserving original bytes."""
from pathlib import Path
import sys,json,hashlib,gzip,re,math,io
import fitz
from PIL import Image,ImageDraw
import PIL
R=Path(__file__).resolve().parent
(R/'render-environment.json').write_text(json.dumps({'PyMuPDF':fitz.VersionBind,'MuPDF':fitz.VersionFitz,'Pillow':PIL.__version__},indent=2)+'\n')
D=json.loads((R/'documents.json').read_text())
extra=[('wood','Countywide published precinct map','evidence/continued/wood-county-pdf.bin','https://boe.woodcountyohio.gov/232/Maps','published countywide PDF; printed date inspected separately'),('ashtabula','County GIS archived catalog precinct PDF','evidence/continued/ashtabula-pdf.bin','https://gis-ashtabulacounty.opendata.arcgis.com/','catalog created 2016; modified 2018; no current approval'),('trumbull','Countywide precinct map','evidence/late2/trumbull-pdf.bin','https://boe.co.trumbull.oh.gov/boe_maps.html','published BOE PDF; effective date unestablished'),('summit','Historical county council map with precinct lines','evidence/historical/summit-council2010.bin','http://summitcountyboe.com/Maps/County%20CouncilAll.pdf','historical BOE map captured 2010-11-28; not current precincts'),('richland','Truncated historical countywide PDF - excluded','evidence/finaldiscovery/richland-history.bin','https://www.boe.ohio.gov/richland/precinct-and-polling-location-info/','truncated 1MiB CommonCrawl capture - unusable'),('summit','Truncated historical 420 precinct map - excluded','evidence/finish/summit-history0.bin','https://www.boe.ohio.gov/summit/precinct-and-polling-location-info/maps/','truncated 1MiB CommonCrawl capture - unusable')]
for county,label,path,landing,vintage in extra:
 p=R/path
 if p.exists():
  mp=p.with_suffix('.meta.json');m=json.loads(mp.read_text());D.append(dict(county=county,label=label,path=path,landing=landing,vintage=vintage,url=m['requested_url'],status=m['status'],sha256=m['sha256'],is_pdf=p.read_bytes().startswith(b'%PDF')))
cached={d["path"]:d for d in json.loads((R/"pdf-manifest.json").read_text())} if (R/"pdf-manifest.json").exists() else {}
seen=set();out=[]
for d in D:
 if d['path'] in seen:continue
 seen.add(d['path']);b=(R/d['path']).read_bytes()
 old=cached.get(d['path'])
 if old and old.get('complete_pdf') and old.get('sha256')==hashlib.sha256(b).hexdigest() and all((R/old[k]).exists() for k in ['preview_path','contact_path','text_path']):out.append(old);continue
 d['complete_pdf']=False
 if not b.startswith(b'%PDF'):
  d['failure']='response is not a PDF';out.append(d);continue
 meta=json.loads((R/d['path']).with_suffix('.meta.json').read_text());warning=meta.get('headers',{}).get('warning','')
 if 'truncat' in warning.lower() or b'%%EOF' not in b[-2048:]:
  d['failure']='truncated PDF (warning header or missing EOF); excluded from usable asset coverage';out.append(d);continue
 try:
  doc=fitz.open(stream=b,filetype='pdf');assert not doc.is_repaired,'repaired source PDF; requires review'
  d['complete_pdf']=True;d['page_count']=len(doc);d['pdf_metadata']=doc.metadata;d['page_sizes_points']=[list(p.rect) for p in doc]
  key=d['county']+'-'+hashlib.sha256(b).hexdigest()[:12];p=R/'derived/pdf';p.mkdir(parents=True,exist_ok=True)
  text='\n\f\n'.join(pg.get_text() for pg in doc);tp=p/(key+'.txt.gz');tp.write_bytes(gzip.compress(text.encode(),mtime=0));d['text_path']=str(tp.relative_to(R));d['date_lines']=[s.strip() for s in text.splitlines() if re.search(r'20\d\d|19\d\d|adopt|approv|effective|update|prepared|produced',s,re.I)][:60]
  # Every page represented in a contact sheet; original PDFs retain resolution.
  cols=min(5,len(doc));cellw,cellh=240,200;sheet=Image.new('RGB',(cols*cellw,math.ceil(len(doc)/cols)*cellh),'white');dr=ImageDraw.Draw(sheet)
  for i,pg in enumerate(doc):
   sc=min(220/pg.rect.width,175/pg.rect.height);pm=pg.get_pixmap(matrix=fitz.Matrix(sc,sc),alpha=False);im=Image.frombytes('RGB',[pm.width,pm.height],pm.samples);x=(i%cols)*cellw+(cellw-im.width)//2;y=(i//cols)*cellh+20;sheet.paste(im,(x,y));dr.text(((i%cols)*cellw+8,(i//cols)*cellh+3),f'Page {i+1}',fill='black')
  cp=p/(key+'-contact.jpg');sheet.save(cp,quality=87);d['contact_path']=str(cp.relative_to(R))
  pg=doc[0];sc=min(1600/pg.rect.width,1600/pg.rect.height);pm=pg.get_pixmap(matrix=fitz.Matrix(sc,sc),alpha=False);pp=p/(key+'-page1.png');pm.save(pp);d['preview_path']=str(pp.relative_to(R));print(d['county'],d['label'],len(doc),d['date_lines'][-5:],flush=True)
 except Exception as e:d['complete_pdf']=False;d['failure']=str(e)
 out.append(d)
(R/'pdf-manifest.json').write_text(json.dumps(out,indent=2)+'\n')
