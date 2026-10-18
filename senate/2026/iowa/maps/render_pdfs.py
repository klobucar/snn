#!/usr/bin/env python3
"""Inspect original PDFs and every ZIP PDF member; render actual pages offline."""
import gzip, io, json, pathlib, re, zipfile
import fitz
from PIL import Image, ImageDraw
from acquire import ROOT, body, sha, write_json

def inspect_pdf(data,key,member=None):
    doc=fitz.open(stream=data,filetype='pdf')
    pages=[];thumbs=[]
    for i,page in enumerate(doc):
        pix=page.get_pixmap(matrix=fitz.Matrix(min(400/page.rect.width,400/page.rect.height),min(400/page.rect.width,400/page.rect.height)),alpha=False)
        im=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB');thumbs.append(im)
        text=page.get_text();textpath=ROOT/'pdf-text'/f'{key}-p{i+1}.txt.gz'
        textpath.write_bytes(gzip.compress(text.encode(),mtime=0))
        pages.append(dict(page=i+1,width_points=page.rect.width,height_points=page.rect.height,text_chars=len(text),text_path=str(textpath.relative_to(ROOT)),images=len(page.get_images()),rotation=page.rotation))
    first=None
    if len(doc):
        page=doc[0];scale=min(1800/page.rect.width,1800/page.rect.height)
        pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
        p=ROOT/'previews'/f'{key}-first.png';pix.save(p);first=str(p.relative_to(ROOT))
    return dict(pdf_key=key,archive_member=member,original_bytes=len(data),original_sha256=sha(data),page_count=len(doc),metadata=doc.metadata,pages=pages,first_page_preview=first,preview_operation='MuPDF rasterization of original pages; fit to 400px contact thumbnails and 1800px first-page PNG; original PDF unchanged'),thumbs
def main():
    for d in ['pdf-text','pdf-audit','previews','contacts']:(ROOT/d).mkdir(exist_ok=True)
    allout=[]
    for path in sorted((ROOT/'raw').glob('*.meta.json')):
        m=json.loads(path.read_text());key=m['source_id']
        if m.get('status')!=200:continue
        # Incidental result/statistical links are retained evidence, never mapbooks.
        if re.search(r'Statistical Reports|Results|Summary|^By Precinct$|Calendar|Worksheet|Instructions',m.get('link_label',''),re.I):continue
        if not (m.get('path','').endswith('.pdf') or key.startswith('polk-all-precincts')):continue
        cache=ROOT/'pdf-audit'/f'{key}.json'
        if cache.exists():allout.append(json.loads(cache.read_text()));continue
        data=body(m);docs=[];thumbs=[];members=[]
        try:
            if data[:5]==b'%PDF-':
                a,t=inspect_pdf(data,key);docs.append(a);thumbs.extend((key,p+1,im) for p,im in enumerate(t))
            elif data[:2]==b'PK':
                z=zipfile.ZipFile(io.BytesIO(data));bad=z.testzip()
                for i,n in enumerate(z.namelist()):
                    if n.endswith('/'):continue
                    b=z.read(n);members.append(dict(name=n,bytes=len(b),sha256=sha(b),crc32=f'{z.getinfo(n).CRC:08x}'))
                    if b[:5]!=b'%PDF-':continue
                    a,t=inspect_pdf(b,key+f'-member{i+1:03}',n);docs.append(a);thumbs.extend((n,p+1,im) for p,im in enumerate(t))
            else:raise ValueError('successful response is not PDF/ZIP')
            contacts=[]
            for start in range(0,len(thumbs),12):
                tile=Image.new('RGB',(1200,1500),'white');dr=ImageDraw.Draw(tile)
                for j,(label,pg,im) in enumerate(thumbs[start:start+12]):
                    col=j%3;row=j//3;im.thumbnail((390,320));tile.paste(im,(col*400+(400-im.width)//2,row*375+25));dr.text((col*400+6,row*375+4),(label.rsplit('/',1)[-1]+f' p{pg}')[:54],fill='black')
                cp=ROOT/'contacts'/f'{key}-{start//12+1:02}.jpg';tile.save(cp,quality=90);contacts.append(str(cp.relative_to(ROOT)))
            out=dict(source_id=key,source_sha256=m['entity_sha256'],source_path=m.get('path'),source_parts=m.get('parts'),zip_members=members,zip_crc_bad_member=bad if data[:2]==b'PK' else None,documents=docs,contact_sheets=contacts,total_pages=sum(d['page_count'] for d in docs))
        except Exception as e:out=dict(source_id=key,error=type(e).__name__+': '+str(e))
        write_json(cache,out);allout.append(out)
    write_json(ROOT/'pdf-audit.json',dict(schema_version=1,renderer='PyMuPDF '+fitz.VersionBind,sources=allout))
    print(json.dumps(dict(sources=len(allout),documents=sum(len(o.get('documents',[])) for o in allout),pages=sum(o.get('total_pages',0) for o in allout),errors=[o for o in allout if o.get('error')])) )
if __name__=='__main__':main()
