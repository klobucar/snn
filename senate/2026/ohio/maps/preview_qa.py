#!/usr/bin/env python3
"""Build two review contact sheets showing each of the32 actual index previews."""
from pathlib import Path
import io,json,subprocess
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent;C=[c for c in json.loads((R/'county-inventory.json').read_text()) if c['priority']]
for block in range(2):
 sheet=Image.new('RGB',(1120,960),'white');draw=ImageDraw.Draw(sheet)
 for n,c in enumerate(C[block*16:(block+1)*16]):
  p=R/c['index_preview_path']
  if p.suffix=='.svg':b=subprocess.run(['rsvg-convert','-w','260','-h','200',str(p)],check=True,capture_output=True).stdout;im=Image.open(io.BytesIO(b)).convert('RGB')
  else:im=Image.open(p).convert('RGB');im.thumbnail((260,200))
  x=(n%4)*280;y=(n//4)*240;sheet.paste(im,(x+(280-im.width)//2,y+30+(200-im.height)//2));draw.text((x+9,y+6),str(c['rank'])+' '+c['county']+' / '+c['county_fips'],fill='black')
 sheet.save(R/'derived'/f'priority-preview-review-{block+1}.jpg',quality=90)
print('32 index previews represented in two contact sheets')
