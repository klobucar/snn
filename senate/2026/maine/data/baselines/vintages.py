#!/usr/bin/env python3
"""Exact row/cell comparison of independently retained official source vintages."""
import gzip, io, json, re, zipfile
from xml.etree import ElementTree as E
from build import ROOT, CONFIG, dump_csv
from read_xlsx import read

CLERK={
 'senate-2024':{'cherry':20222,'costello':88891,'king':427331,'kouzounas':284338,'blank':21665,'tbc':842447},
 'president-2024':{'harris':435351,'oliver':5304,'stein':8973,'trump':377837,'west':2943,'others':581,'blank':11458,'tbc':842447},
 'senate-2020':{'collins':417645,'gideon':347223,'linn':13508,'savage':40579,'others':228,'blank':9122,'tbc':828305}}
NARA={'harris':435652,'oliver':5286,'stein':8967,'trump':377977,'west':2912}

def main():
    diffs=[];controls=[];metadata=[];summary=[]
    for source,archive in [('senate-2024','legislature-2024-b'),('president-2024','legislature-2024-a')]:
        cfg=CONFIG[source];old=next(iter(read(ROOT/'raw'/(archive+'.xlsx.gz')).values()));new=next(iter(read(ROOT/'raw'/(source+'.xlsx.gz')).values()))
        oldmap={r['row']:r['values'] for r in old};newmap={r['row']:r['values'] for r in new}
        assert set(oldmap)==set(newmap),(source,'row universe differs')
        changed=[];changed_native=[]
        for row in oldmap:
            a,b=oldmap[row],newmap[row]
            assert a.get('A','')==b.get('A','') and a.get('B','')==b.get('B','')
            if a==b:continue
            changed.append(row)
            if a.get('A'):changed_native.append((row,a['B']))
            for col in set(a)|set(b):
                if a.get(col)!=b.get(col):
                    category=cfg['candidates'][col][0] if col in cfg['candidates'] else 'blank' if col==cfg['blank'] else 'tbc'
                    diffs.append(dict(contest_source_id=source,archive_source_id=archive,row=row,native_county_code=a.get('A',''),native_unit_name=a.get('B',''),
                        cell=f'{col}{row}',category=category,archive_value=int(a[col]),current_sos_value=int(b[col]),current_minus_archive=int(b[col])-int(a[col]),
                        row_type='native disjoint reporting row' if a.get('A') else 'subtotal or statewide control'))
        assert changed_native==([(517,'Alfred')] if source=='senate-2024' else [(518,'Alfred')])
        for col,cid in [(col,t[0]) for col,t in cfg['candidates'].items()]+[(cfg['blank'],'blank'),(cfg['tbc'],'tbc')]:
            a=int(old[-1]['values'][col]);b=int(new[-1]['values'][col])
            assert a==CLERK[source][cid]
            nara=NARA.get(cid) if source=='president-2024' else None
            if nara is not None:assert b==nara
            controls.append(dict(source_id=source,category=cid,current_sos=b,legislature_archive=a,house_clerk_2024=a,sos_minus_clerk=b-a,nara_dec9=nara if nara is not None else '',
                nara_comparison='exact' if nara is not None else 'not provided in certificate'))
        summary.append(dict(source_id=source,archive_source_id=archive,numeric_changed_rows=changed,only_native_changed_unit='YOR Alfred',
            native_row=changed_native[0][0],labels_and_native_row_universe_unchanged=True,
            inference='Alfred replacement accounts for every statewide candidate/blank difference; underlying correction cause and publication sequence unproved'))
        for sid in [source,archive]:
            z=zipfile.ZipFile(io.BytesIO(gzip.decompress((ROOT/'raw'/(sid+'.xlsx.gz')).read_bytes())))
            meta=E.fromstring(z.read('docProps/core.xml'))
            metadata.append(dict(source_id=sid,**{x.tag.split('}')[-1]:x.text for x in meta}))
    # Clerk 2020 is an independent publication, not a competing count here.
    cfg=CONFIG['senate-2020'];state=next(iter(read(ROOT/'raw/senate-2020.xlsx.gz').values()))[-1]['values']
    for col,(cid,_,_) in cfg['candidates'].items():assert int(state[col])==CLERK['senate-2020'][cid]
    summary.append(dict(chronology_limits=[
        'Legislature directory lists a.xlsx at 2024-12-09 09:04 and b.xlsx at 09:05; timezone unspecified, not proven first publication.',
        'Current SOS links label both files FINAL-Corrected 20241205; filename is not proof of publication on Dec5.',
        'Current president OOXML modified 2024-12-06T14:55:08Z; archived president modified 2024-12-09T13:04:33Z. Embedded clocks do not establish chronological order.',
        'Current Senate modified 2024-12-09T15:31:56Z; archive modified 2024-12-09T13:05:30Z.',
        'Dec9 signed presidential certificate agrees with corrected SOS five named-candidate statewide totals.',
        'Dec18 SOS final-results notice in Jan8 legislature record points to state tabulations but supplies no candidate correction explanation.',
        'House Clerk PDF publication date March10 2025 is later; it agrees with retained archive rather than current SOS. Transmission history unverified.',
        'No municipal amended return, correction memorandum or causal audit record obtained; no claim of fraud, machine error or ballot change follows from this comparison.']))
    dump_csv(ROOT/'source-vintage-cell-differences.csv',diffs)
    dump_csv(ROOT/'source-vintage-state-controls.csv',controls)
    (ROOT/'source-vintage-investigation.json').write_text(json.dumps(dict(comparisons=summary,workbook_metadata=metadata),indent=2)+'\n')
    print('Official archive = Clerk controls; only Alfred native row changed in each contest; corrected named president = NARA PASS')

if __name__=='__main__':main()
