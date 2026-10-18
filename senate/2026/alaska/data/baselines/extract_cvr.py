#!/usr/bin/env python3
"""Lossless Senate-only pattern aggregate of the original 2022 DOE CVR archive.
Keep Original/Modified IsCurrent adjudication, source native units and methods.
IsVote is the scanner first-choice flag, not eligibility for later RCV ranks.
"""
import collections,csv,gzip,hashlib,io,json,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parent

def main():
    parts=json.loads((ROOT/'cvr2022-parts.json').read_text())
    chunks=[]
    for x in parts['parts']:
        b=(ROOT/x['file']).read_bytes();assert hashlib.sha256(b).hexdigest()==x['sha256'];chunks.append(b)
    data=b''.join(chunks);assert hashlib.sha256(data).hexdigest()==parts['original_sha256']
    stats=collections.Counter(); patterns=collections.Counter(); first=collections.Counter();first_by_unit=collections.defaultdict(collections.Counter);seen=set()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        units={v['Id']:v for v in json.loads(z.read('PrecinctPortionManifest.json'))['List']}
        names={v['Id']:v['Description'] for v in json.loads(z.read('CandidateManifest.json'))['List'] if v['ContestId']==3}
        precincts={v['Id']:v['Description'] for v in json.loads(z.read('PrecinctManifest.json'))['List']}
        methods={v['Id']:v['Description'] for v in json.loads(z.read('CountingGroupManifest.json'))['List']}
        files=[x for x in z.namelist() if x.startswith('CvrExport_')]
        for filename in files:
            for s in json.loads(z.read(filename))['Sessions']:
                stats['sessions']+=1
                key=(s['TabulatorId'],s['BatchId'],s['RecordId']); assert key not in seen;seen.add(key)
                current=[s[k] for k in ['Original','Modified'] if k in s and s[k]['IsCurrent']]
                assert len(current)==1
                c=current[0];stats['modified_current']+=int('Modified' in s and s['Modified']['IsCurrent'])
                contests=[v for card in c['Cards'] for v in card['Contests'] if v['Id']==3]
                if not contests:stats['no_senate_contest']+=1;continue
                assert len(contests)==1
                con=contests[0];stats['senate_contests']+=1
                # Marks explicitly deemed ambiguous and not votes are excluded.
                marks=[m for m in con['Marks'] if not m['IsAmbiguous'] or m['IsVote']]
                pattern=tuple(sorted((m['Rank'],m['CandidateId']) for m in marks))
                u=units[c['PrecinctPortionId']]
                patterns[(c['PrecinctPortionId'],s['CountingGroupId'],pattern)]+=1
                stats['first_undervotes']+=con['Undervotes'];stats['first_overvotes']+=con['Overvotes']
                for m in con['Marks']:
                    if m['IsVote']:
                        first[names[m['CandidateId']]]+=1
                        first_by_unit[precincts[u['PrecinctId']]][names[m['CandidateId']]]+=1
        stats['source_files']=len(files)
    with gzip.GzipFile(filename=str(ROOT/'cvr2022-senate-patterns.csv.gz'),mode='wb',mtime=0) as out:
        text=io.TextIOWrapper(out,encoding='utf-8',newline='');w=csv.writer(text)
        w.writerow(['precinct_portion_id','precinct_id','source_external_id','unit_name','precinct_name','counting_group_id','voting_method','rank_candidate_pairs','ballots'])
        for (uid,method,pattern),n in sorted(patterns.items()):
            u=units[uid];w.writerow([uid,u['PrecinctId'],u['ExternalId'],u['Description'],precincts[u['PrecinctId']],method,methods[method],json.dumps(pattern,separators=(',',':')),n])
        text.flush();text.detach()
    with (ROOT/'cvr2022-scanner-first-choices.csv').open('w',newline='') as out:
        w=csv.writer(out);w.writerow(['unit_name','candidate','votes'])
        for u in sorted({precincts[units[k[0]]['PrecinctId']] for k in patterns}):
            for c in names.values():w.writerow([u,c,first_by_unit[u][c]])
    result=dict(stats=stats,scanner_first_choices=first,pattern_rows=len(patterns),native_portions=len({k[0] for k in patterns}),native_precincts=len({units[k[0]]['PrecinctId'] for k in patterns}),original_sha256=parts['original_sha256'])
    (ROOT/'cvr-extraction-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
