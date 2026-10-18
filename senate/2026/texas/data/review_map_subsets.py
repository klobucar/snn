#!/usr/bin/env python3
"""Independent binary audit of all four TLC originals and 136 priority subsets."""
from pathlib import Path
from collections import defaultdict
import datetime,gzip,hashlib,io,json,struct,zipfile

ROOT=Path(__file__).resolve().parent
MAPS=ROOT.parent/'maps'
keys=(ROOT/'coordinator-priority-keys.txt').read_text().splitlines()
assert len(keys)==len(set(keys))==34
fips=[key.split(':',1)[1] for key in keys]
dependencies={}
def sha(body):return hashlib.sha256(body).hexdigest()
def original(vintage):
    path=MAPS/'sources'/('tlc-'+vintage+'.json');meta=json.loads(path.read_text());chunks=[]
    assert meta['status']==200 and meta['retrieved_utc'] and meta['parent_source_url']
    for part in meta['stored_parts']:
        b=(MAPS/part['path']).read_bytes()
        assert len(b)==part['bytes']<40_000_000 and sha(b)==part['sha256']
        dependencies[str((MAPS/part['path']).relative_to(ROOT.parent))]=sha(b);chunks.append(b)
    body=b''.join(chunks)
    if meta['storage_encoding']=='gzip':body=gzip.decompress(body)
    else:assert meta['storage_encoding']=='identity'
    assert len(body)==meta['original_bytes'] and sha(body)==meta['original_sha256']
    dependencies[str(path.relative_to(ROOT.parent))]=sha(path.read_bytes())
    return body
def members(body):
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        assert archive.testzip() is None
        names=archive.namelist();assert len(names)==len(set(names))
        return {ext:archive.read(next(n for n in names if n.lower().endswith('.'+ext))) for ext in ('shp','shx','dbf','prj','cpg')}
def dbf_rows(body):
    count=struct.unpack_from('<I',body,4)[0];header,length=struct.unpack_from('<HH',body,8)
    assert body[header-1]==13 and header>=33 and length>1
    fields=[];offset=1
    for i in range(32,header-1,32):
        field=body[i:i+32];name=field[:11].split(b'\0')[0].decode();width=field[16]
        fields.append((name,offset,width));offset+=width
    assert offset==length
    rows=[body[header+i*length:header+(i+1)*length] for i in range(count)]
    assert all(len(r)==length for r in rows)
    return fields,body[32:header],rows
def shape_rows(body,index):
    assert struct.unpack_from('>I',body)[0]==9994 and struct.unpack_from('<I',body,28)[0]==1000
    assert 2*struct.unpack_from('>I',body,24)[0]==len(body)
    assert struct.unpack_from('>I',index)[0]==9994 and 2*struct.unpack_from('>I',index,24)[0]==len(index)
    position=100;records=[];entries=[];vertices=0;types=defaultdict(int)
    while position<len(body):
        number,words=struct.unpack_from('>II',body,position);start=position+8;end=start+2*words
        assert end<=len(body) and number==len(records)+1
        record=body[start:end];kind=struct.unpack_from('<I',record)[0];types[kind]+=1
        if kind in (5,15,25):
            parts,points=struct.unpack_from('<II',record,36)
            assert len(record)>=44+parts*4+points*16
            vertices+=points
        else:assert kind==0
        records.append(record);entries.append((position//2,words));position=end
    assert position==len(body) and len(index)==100+8*len(records)
    assert [struct.unpack_from('>II',index,100+8*i) for i in range(len(records))]==entries
    return records,vertices,{str(k):v for k,v in types.items()}

audits=[];subsets=0;all_vertices=0;priority_geometry_records=0
for vintage,expected in [('24g',9657),('26p',9614),('22g',9586),('20g',9014)]:
    source=members(original(vintage));fields,descriptors,rows=dbf_rows(source['dbf'])
    geometries,vertices,types=shape_rows(source['shp'],source['shx'])
    assert len(rows)==len(geometries)==expected
    _,offset,width=next(f for f in fields if f[0]=='CNTY')
    grouped=defaultdict(list)
    for i,row in enumerate(rows):
        code=int(row[offset:offset+width].decode().strip())
        grouped[code].append(i)
    # This audits the declared TLC CNTY subset selector, not the unrelated Civix MID.
    assert len(grouped)==254 and set(grouped)==set(range(1,508,2))
    count=0
    for county_fips in fips:
        path=MAPS/'counties'/(county_fips+'-'+vintage+'.zip');body=path.read_bytes()
        assert len(body)<40_000_000
        dependencies[str(path.relative_to(ROOT.parent))]=sha(body)
        subset=members(body);subset_fields,subset_descriptors,subset_rows=dbf_rows(subset['dbf'])
        subset_shapes,subset_vertices,subset_types=shape_rows(subset['shp'],subset['shx'])
        indices=grouped[int(county_fips[2:])]
        assert subset_fields==fields and subset_descriptors==descriptors
        assert subset_rows==[rows[i] for i in indices],(vintage,county_fips,'DBF rows')
        assert subset_shapes==[geometries[i] for i in indices],(vintage,county_fips,'SHP record bodies')
        assert subset['prj']==source['prj'] and subset['cpg']==source['cpg']
        count+=len(indices);subsets+=1
    audits.append({'vintage':vintage,'all_native_features':expected,'all_native_county_codes':254,
                   'original_vertices':vertices,'original_shape_types':types,'priority_features':count,'priority_county_ZIPs':34,
                   'geometry_and_attribute_conservation':'Every subset SHP record body and complete DBF row byte-identical in source order; native PRJ/CPG unchanged; SHX offsets/lengths and ZIP CRCs exact.'})
    all_vertices+=vertices;priority_geometry_records+=count
assert subsets==136
result={'status':'pass','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope':'Independent source/split reconstruction and exact binary county-subset conservation only. Does not establish current approval, reporting-unit crosswalk, valid topology or allocate votes.',
        'all_counties_per_vintage':254,'priority_counties_per_vintage':34,'priority_county_ZIPs':subsets,
        'all_original_vertices':all_vertices,'priority_feature_records_across_vintages':priority_geometry_records,'vintages':audits,'dependencies':dependencies}
output=ROOT/'coordinator-map-subset-checks.json'
if output.exists():
    old=json.loads(output.read_text())
    if {k:v for k,v in old.items() if k!='checked_utc'}=={k:v for k,v in result.items() if k!='checked_utc'}:result['checked_utc']=old['checked_utc']
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='dependencies'},indent=2))
