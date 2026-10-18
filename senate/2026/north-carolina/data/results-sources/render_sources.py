#!/usr/bin/env python3
"""Recreate retained PDF text and page images from downloaded bodies.

All temporary files stay in this owned folder and are removed after use.
Read-only source PDFs are never altered. Requires Poppler.
"""
import subprocess
from build import ROOT,body

PAGES={'wake-2024-summary':(1,1600),'wake-2022-summary':(1,2500),
       'catawba-2024-summary':(1,1600),'catawba-2022-summary':(1,1600),
       'candidate-guide':(16,1600),'forsyth-coming-soon':(1,1200),
       'guilford-2024-official':(1,1600),'county-092-early':(1,1600)}

def main():
    for key,(page,size) in PAGES.items():
        tmp=ROOT/(key+'.render-input.pdf')
        try:
            tmp.write_bytes(body(key))
            subprocess.run(['pdftotext','-layout',str(tmp),str(ROOT/(key+'.txt'))],check=True)
            name=key+'-page'+str(page)
            if key=='wake-2022-summary':name+='-large'
            subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to',str(size),'-png','-singlefile',str(tmp),str(ROOT/name)],check=True)
        finally:tmp.unlink(missing_ok=True)

if __name__=='__main__':main()
