#!/usr/bin/env python3
"""Compare every cell in official library 2024 originals with live SOS files."""
import json,re
from pathlib import Path
from xlsx_read import read
ROOT=Path(__file__).resolve().parent
out={}
for contest in ['senate','president']:
    old=read(ROOT/f'raw/legislature-2024-{contest}-archive.xlsx.gz')
    current=read(ROOT/f'raw/{contest}-2024.xlsx.gz')
    assert list(old)==list(current)
    diffs=[]
    for sheet in old:
        a={k:v for r in old[sheet] for k,v in r['cells'].items()}
        b={k:v for r in current[sheet] for k,v in r['cells'].items()}
        for cell in sorted(set(a)|set(b),key=lambda k:(int(re.sub(r'\D','',k)),re.sub(r'\d','',k))):
            if a.get(cell)!=b.get(cell):diffs.append(dict(sheet=sheet,cell=cell,archived=a.get(cell),current=b.get(cell)))
    expected_rows={517,545,549} if contest=='senate' else {518,546,550}
    assert {int(re.sub(r'\D','',d['cell'])) for d in diffs}==expected_rows
    assert all(re.sub(r'\d','',d['cell']) in ('CDEFG' if contest=='senate' else 'CDEFGI') for d in diffs)
    state_row=549 if contest=='senate' else 550
    columns='CDEFGH' if contest=='senate' else 'CDEFGHIJ'
    archived_state=[int(a[f'{c}{state_row}']) for c in columns]
    current_state=[int(b[f'{c}{state_row}']) for c in columns]
    clerk=[20222,88891,427331,284338,21665,842447] if contest=='senate' else [435351,5304,8973,377837,2943,581,11458,842447]
    # Clerk prints candidate/category integers and total ballots can be summed;
    # do not treat its BLANK category as candidate votes.
    assert archived_state==clerk
    out[contest]=dict(archived_source=f'raw/legislature-2024-{contest}-archive.xlsx.gz',current_source=f'raw/{contest}-2024.xlsx.gz',
      all_cell_differences=diffs,affected_unit='YOR / Alfred',unaffected_ballots=2076,
      statewide_columns=list(columns),archived_statewide=archived_state,current_statewide=current_state,clerk_page29_control=clerk,archived_clerk_exact=True,
      interpretation='Every count difference localized to Alfred and its York/state totals. Mechanism and timing of correction not established. Library copy is archival, not the current SOS download.')
(ROOT/'source-vintage-diff.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS: all cell differences confined to Alfred and York/state footer counts')
