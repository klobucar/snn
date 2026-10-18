#!/usr/bin/env python3
"""Reproduce read-only PDF text/render derivatives from retained compressed bytes."""
import gzip,pathlib,subprocess,tempfile,json
ROOT=pathlib.Path(__file__).resolve().parent
versions={x:subprocess.run([x,'-v'],capture_output=True,text=True).stderr.splitlines()[0] for x in ['pdftotext','pdftoppm']}
for key in ['sample-hd1','enr-summary','law15-pdf','ballot-placement','measure-language','measure-bill','oep-region1','bts-dmp','govinfo-time-2003']:
 with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
  f.write(gzip.decompress((ROOT/(key+'.body.gz')).read_bytes()));f.flush()
  out=subprocess.run(['pdftotext','-layout',f.name,'-'],check=True,capture_output=True).stdout
  (ROOT/(key+'.extracted.txt')).write_bytes(out)
  render=('sample-hd1-page1',1) if key=='sample-hd1' else ('oep-schedule',5) if key=='oep-region1' else None
  if render:
   name,page=render;subprocess.run(['pdftoppm','-f',str(page),'-singlefile','-scale-to','1600','-png',f.name,str(ROOT/name)],capture_output=True,check=True)
(ROOT/'pdf-derivatives.json').write_text(json.dumps({'tools':versions,'rendered_pages':{'sample-hd1-page1.png':1,'oep-schedule.png':5},'note':'Printed ballot and current November schedule visually reviewed; two image-only PDFs have empty extracted text and are not treated as parsed text evidence.'},indent=2)+'\n')
