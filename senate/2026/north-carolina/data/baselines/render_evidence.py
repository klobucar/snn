#!/usr/bin/env python3
"""Render fixed PDF evidence pages without altering downloaded originals."""
import hashlib,json,pathlib,subprocess
BASE=pathlib.Path(__file__).resolve().parent
JOBS=[(f'{y}-certified-contest.pdf',2 if y==2024 else 1,1500,f'{y}-certified-contest-preview.png') for y in [2024,2022,2020]]+[
 ('2024-certified-county.pdf',162,1600,'2024-mitchell-certified-preview.png'),
 ('2024-certified-county.pdf',211,1600,'2024-rowan-certified-preview.png'),
 ('house-2014-statistics.pdf',38,1600,'2014-anchor-preview.png')]
def main():
    records=[]
    for source,page,scale,out in JOBS:
        args=['pdftoppm','-f',str(page),'-singlefile','-scale-to',str(scale),'-png',str(BASE/source),str((BASE/out).with_suffix(''))]
        subprocess.run(args,check=True)
        records.append({'input':source,'input_sha256':hashlib.sha256((BASE/source).read_bytes()).hexdigest(),'physical_pdf_page_one_based':page,'scale_to_pixels':scale,'output':out,'output_sha256':hashlib.sha256((BASE/out).read_bytes()).hexdigest(),'transformation':'pdftoppm -f PAGE -singlefile -scale-to SCALE -png INPUT OUTPUT_PREFIX'})
    (BASE/'preview-provenance.json').write_text(json.dumps({'renderer':subprocess.run(['pdftoppm','-v'],capture_output=True,text=True).stderr.splitlines()[0],'previews':records},indent=2)+'\n')
if __name__=='__main__':main()
