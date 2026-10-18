#!/usr/bin/env python3
"""Read-only PDF inspection with PyMuPDF and Poppler page-count cross-check.
Run with host python3 (fitz/Pillow available), no PDF authoring.
"""
import datetime,gzip,hashlib,json,re,subprocess
from pathlib import Path
import fitz
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 out=[];seen={};previewpaths=[]
 prior=json.loads((ROOT/'pdf/inspection.json').read_text())['sources'] if (ROOT/'pdf/inspection.json').exists() else []
 cached={p['original_sha256']:p for p in prior}
 for p in sorted((ROOT/'sources').glob('*.json')):
  d=json.loads(p.read_text())
  if not d.get('stored_parts'):continue
  # Only PDF sources, including sources whose URL lacks a PDF suffix.
  first=(ROOT/d['stored_parts'][0]['path']).read_bytes()
  if not first.startswith((b'%PDF',b'\x1f\x8b')):continue
  b=b''.join((ROOT/x['path']).read_bytes() for x in d['stored_parts'])
  if d['storage_encoding']=='gzip':b=gzip.decompress(b)
  if not b.startswith(b'%PDF'):continue
  assert sha(b)==d['original_sha256'] and len(b)==d['original_bytes']
  if d['original_sha256'] in seen:continue
  if d['original_sha256'] in cached:
   item=cached[d['original_sha256']];item['county']=d.get('county');out.append(item);seen[d['original_sha256']]=d['id']
   previewpaths.extend((ROOT/q,d['id']+' p'+str(int(q.rsplit('-p',1)[1].split('.')[0]))+'/'+str(item['pages'])) for q in item['preview_paths'])
   continue
  seen[d['original_sha256']]=d['id'];doc=fitz.open(stream=b,filetype='pdf')
  texts=[];pages=[]
  for i,page in enumerate(doc):
   txt=page.get_text();texts.append(txt);pages.append(dict(page=i+1,text_characters=len(txt),raster_image_count=len(page.get_images()),width_points=page.rect.width,height_points=page.rect.height))
  text='\n\n'.join(f'--- PAGE {i+1} ---\n{t}' for i,t in enumerate(texts));folder=ROOT/'pdf';folder.mkdir(exist_ok=True)
  tp=folder/(d['id']+'.txt.gz');tp.write_bytes(gzip.compress(text.encode(),mtime=0))
  # Poppler verifies the same unmodified bytes; temporary reconstruction outside repository.
  import tempfile
  with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
   tmp.write(b);tmp.flush();r=subprocess.run(['pdfinfo',tmp.name],capture_output=True,text=True)
   count=re.search(r'^Pages:\s*(\d+)',r.stdout,re.M)
   assert count and int(count.group(1))==len(doc),(d['id'],r.stdout,r.stderr)
  selected=sorted({0,len(doc)//2,len(doc)-1});renders=[]
  for i in selected:
   page=doc[i];scale=min(1500/page.rect.width,1500/page.rect.height);pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
   path=folder/(d['id']+f'-p{i+1:04d}.png');pix.save(path);renders.append(str(path.relative_to(ROOT)));previewpaths.append((path,d['id']+f' p{i+1}/{len(doc)}'))
  dates=[line.strip() for line in text.splitlines() if re.search(r'adopt|effective|revised|printed|created|\bdate\b|2026',line,re.I)]
  out.append(dict(source_id=d['id'],county=d.get('county'),status=d.get('status'),requested_url=d['requested_url'],original_sha256=d['original_sha256'],original_bytes=len(b),pages=len(doc),metadata=doc.metadata,page_diagnostics=pages,text_path=str(tp.relative_to(ROOT)),literal_date_legal_lines=dates[:100],preview_paths=renders,preview_scope='First, middle, last source pages rendered without editing. Mapbooks retained complete; only selected page previews.',poppler_page_count_check=True,legal_interpretation='Printed text is evidence of its stated date/scope only; no blanket November2026 boundary approval inferred.'))
  print(d['id'],len(doc),'pages',flush=True)
 for start in range(0,len(previewpaths),12):
  items=previewpaths[start:start+12];sheet=Image.new('RGB',(1200,4*330),'white');draw=ImageDraw.Draw(sheet)
  for k,(p,title) in enumerate(items):
   im=Image.open(p);im.thumbnail((390,290));x=(k%3)*400;y=(k//3)*330;sheet.paste(im,(x+(400-im.width)//2,y));draw.text((x+8,y+295),title[:50],fill='black')
  sheet.save(ROOT/'pdf'/f'contact-{start//12+1:02d}.jpg',quality=88)
 (ROOT/'pdf/inspection.json').write_text(json.dumps(dict(inspected_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=out,visual_review='Representative actual maps reviewed separately in visual-review.json; generated contact sheets are derivatives.'),indent=2)+'\n')
if __name__=='__main__':main()
