"""Small standard-library helpers. All mutations are confined to this assignment."""
import csv, gzip, hashlib, io, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATE = ROOT.parent.parent
TURNOUT = ROOT.parent/'turnout'
def sha(b): return hashlib.sha256(b).hexdigest()
def dump(name, value):
    (ROOT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
def csvout(name, rows, fields=None):
    rows=list(rows)
    path=ROOT/name
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def records(name):
    with (ROOT/name).open() as f:return list(csv.DictReader(f))
def sources():return json.loads((ROOT/'sources.json').read_text())
def raw(meta):
    stored=(ROOT/meta['path']).read_bytes()
    assert sha(stored)==meta['stored_sha256'] and len(stored)==meta['stored_bytes'],meta['id']
    b=gzip.decompress(stored)
    assert sha(b)==meta['original_sha256'] and len(b)==meta['original_bytes'],meta['id']
    return b
def pdftext(b):return subprocess.check_output(['pdftotext','-layout','-','-'],input=b).decode()
def gzwrite(path,b):
    result=gzip.compress(b,mtime=0)
    assert len(result)<40000000
    (ROOT/path).parent.mkdir(parents=True,exist_ok=True)
    (ROOT/path).write_bytes(result)

SPECS={
 '2020-senate':{'year':2020,'title':'United States Senator','seat':'Class II; same seat as 2026',
   'labels':['Joni Ernst','Theresa Greenfield','Rick Stewart','Suzanne Herzog','Write-in'],
   'parties':['REP','DEM','LIB','',''],'d':1,'r':0},
 '2022-senate':{'year':2022,'title':'United States Senator','seat':'Class III; other seat; midterm',
   'labels':['Chuck Grassley','Michael Franken','Write-in'],'parties':['REP','DEM',''],'d':1,'r':0},
 '2024-president':{'year':2024,'title':'President and Vice President','seat':'President; no 2024 Iowa Senate contest',
   'labels':['Kamala D. Harris and Tim Walz','Donald J. Trump and JD Vance','Chase Oliver and Mike ter Maat','Shiva Ayyadurai and Crystal Ellis','Claudia De la Cruz and Karina Garcia','William P. Stodden and Stephanie H. Cholensky','Robert F. Kennedy Jr and Nicole Shanahan','Write-in'],
   'parties':['DEM','REP','LIB','','PSL','SOC','WTP',''],'d':0,'r':1}}
def fipsmap():
    meta=next(r for r in sources() if r['id']=='census-county-codes')
    return {r['COUNTYNAME'].removesuffix(' County'):r['STATEFP']+r['COUNTYFP'] for r in csv.DictReader(io.StringIO(raw(meta).decode()),delimiter='|') if r['STATE']=='IA'}
