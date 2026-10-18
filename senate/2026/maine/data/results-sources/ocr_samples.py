from research import *
import subprocess,tempfile
p=ROOT/'requests';out=ROOT/'ocr';out.mkdir(exist_ok=True)
recs=json.loads((ROOT/'priority-inspections.json').read_text());jobs={}
for r in recs:
 for d in r['downloads']:
  if not d.get('request_id'):continue
  id=d['request_id'];m=json.loads((p/f'{id}.json').read_text());b=gzip.decompress((ROOT/m['body_path']).read_bytes());f=ROOT/'extracted'/f'{id}.txt'
  if m.get('status')==200 and b.startswith(b'%PDF') and (not f.exists() or len(f.read_text().strip())<40):jobs[id]=(m,r['rank'])
print('bounded scanned PDF first-page tests',len(jobs),flush=True)
def go(job):
 id,(m,rank)=job;target=out/f'{id}.txt';meta=out/f'{id}.json'
 if meta.exists():return json.loads(meta.read_text())
 b=gzip.decompress((ROOT/m['body_path']).read_bytes());pdf=out/f'.{id}.pdf';pdf.write_bytes(b);pngbase=out/f'{id}-page1'
 a=subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','2200','-png',str(pdf),str(pngbase)],capture_output=True);png=Path(str(pngbase)+'.png');info={'request_id':id,'source_sha256':m['entity_sha256'],'page':1,'scope':'bounded first-page OCR only; other pages not OCRd','pdftoppm_exit':a.returncode,'rank':rank}
 if png.exists():
  o=subprocess.run(['tesseract',str(png),'stdout','--psm','3'],capture_output=True,timeout=55);target.write_bytes(o.stdout);info.update(tesseract_exit=o.returncode,text_chars=len(o.stdout),png_sha256=digest(png.read_bytes()),ocr_text_sha256=digest(o.stdout))
  if rank in (4,8,23,46,110):info['preview_path']=str(png.relative_to(ROOT))
  else:png.unlink()
 else:info.update(error=a.stderr.decode(errors='replace'))
 pdf.unlink();meta.write_text(json.dumps(info,indent=2)+'\n');return info
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 rows=[]
 for i,x in enumerate(ex.map(go,jobs.items())):
  rows.append(x)
  if (i+1)%20==0:print('OCR tested',i+1,flush=True)
(ROOT/'ocr-audit.json').write_text(json.dumps(rows,indent=2)+'\n');print('done',len(rows),flush=True)
