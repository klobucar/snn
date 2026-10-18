from research import *
import subprocess
sys.path.insert(0,str(ROOT.parent/'turnout'));from xlsx_read import read
p=ROOT/'requests';out=ROOT/'extracted';out.mkdir(exist_ok=True)
for f in sorted(p.glob('*.json')):
 if f.name.endswith('.links.json'):continue
 m=json.loads(f.read_text());b=gzip.decompress((ROOT/m['body_path']).read_bytes());id=m['id']
 if b.startswith(b'%PDF'):
  if (out/f'{id}.txt').exists() or (out/f'{id}.txt.gz').exists():continue
  pdf=out/f'{id}.pdf';pdf.write_bytes(b);subprocess.run(['pdftotext','-layout',str(pdf),str(out/f'{id}.txt')],check=True)
  if id=='18776dca67c4bad130cf':subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1400','-png',str(pdf),str(out/id)],check=True)
  pdf.unlink()
 elif b.startswith(b'PK'):
  try:x=read(ROOT/m['body_path']);(out/f'{id}.json').write_text(json.dumps(x,indent=2)+'\n')
  except Exception:pass
 elif 'html' in dict(m.get('headers',[])).get('Content-Type','').lower() or b'<a ' in b[:2000] or b'<html' in b[:3000].lower():
  par=Parser(m.get('final_url',m['request_url']))
  try:par.feed(b.decode('utf-8',errors='replace'))
  except Exception:pass
  (p/f'{id}.links.json').write_text(json.dumps({'links':par.links,'scripts':par.scripts},indent=2)+'\n')
  (p/f'{id}.txt').write_text(re.sub(r'\n[ \t\n]+','\n',re.sub(r'[ \t]+',' ',''.join(par.text))))
