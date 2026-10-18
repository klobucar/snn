#!/usr/bin/env python3
"""Recreate a contact sheet of successful municipal map PDF page1 previews."""
import json,pathlib
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parent
pa=json.loads((ROOT/'pdf-audit.json').read_text());sources=json.loads((ROOT/'municipal-sources.json').read_text())
keys=[]
for s in sources:
    for a in s.get('assets',[]):
        if a['id'] not in ['island-registry','lewiston-ordinance'] and pa.get(a['id'],{}).get('page_count') and not pa[a['id']].get('same_bytes_as'):keys.append(a['id'])
canvas=Image.new('RGB',(1200,280*((len(keys)+2)//3)),'white');draw=ImageDraw.Draw(canvas)
for i,k in enumerate(keys):
    im=Image.open(ROOT/pa[k]['pages'][0]['preview']).convert('RGB');im.thumbnail((390,245));x=(i%3)*400;y=(i//3)*280
    canvas.paste(im,(x+(400-im.width)//2,y+22));draw.text((x+8,y+3),k,fill='black')
canvas.save(ROOT/'previews/municipal-contact-sheet.jpg',quality=88)
