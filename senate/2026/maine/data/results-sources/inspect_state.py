from research import *
import subprocess,sys
sys.path.insert(0,str(ROOT.parent/'turnout'))
from xlsx_read import read
p=ROOT/'requests';out=ROOT/'extracted';out.mkdir(exist_ok=True)
for r in json.loads((ROOT/'state-assets.json').read_text()):
 m=json.loads((p/f"{r['request_id']}.json").read_text());b=gzip.decompress((ROOT/m['body_path']).read_bytes());id=m['id']
 if b.startswith(b'%PDF'):
  pdf=out/f'{id}.pdf';pdf.write_bytes(b)
  subprocess.run(['pdftotext','-layout',str(pdf),str(out/f'{id}.txt')],check=True)
  subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1400','-png',str(pdf),str(out/id)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  pdf.unlink()
  print('\n',r['label']);print((out/f'{id}.txt').read_text()[:8000])
 elif b.startswith(b'PK'):
  # Temporary compressed source name uses content-addressed object, preserving source bytes.
  x=read(ROOT/m['body_path']);(out/f'{id}.json').write_text(json.dumps(x,indent=2)+'\n');print(r['label'],list(x));print(str(x)[:5000])
