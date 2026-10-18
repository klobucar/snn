#!/usr/bin/env python3
"""Independent offline coverage, original-byte, dependency and artifact checks.

Rebuild SHA256SUMS after a reviewed change; does not refetch any URL.
"""
import csv
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo
from build import ROOT,DATA,body,meta,obj,save

PRIORITY='Wake,Mecklenburg,Guilford,Forsyth,Durham,Buncombe,Cumberland,Union,New Hanover,Johnston,Cabarrus,Gaston,Iredell,Brunswick,Davidson,Alamance,Orange,Pitt,Catawba,Onslow,Randolph,Rowan,Henderson,Harnett,Moore,Craven,Lincoln,Wayne,Nash,Chatham,Cleveland,Rockingham,Robeson,Burke,Carteret,Caldwell,Franklin,Wilson'.split(',')

def main():
    inv=list(csv.DictReader((DATA/'official-results-sources.csv').open()))
    counties=[r for r in inv if r['scope']=='county']
    assert len(inv)==104 and len(counties)==100
    assert len({r['source_id'] for r in inv})==104
    assert len({r['county_fips'] for r in counties})==100
    assert {int(r['ncsbe_county_id']) for r in counties}==set(range(1,101))
    assert [r['county'] for r in counties if r['priority']=='1']==PRIORITY
    coverage=list(csv.DictReader((ROOT/'coverage.csv').open()))
    assert len(coverage)==100 and {r['county_fips'] for r in coverage}=={r['county_fips'] for r in counties}
    assert sum(int(r['certified_2024_president']) for r in coverage)==5699145
    assert sum(int(r['certified_2022_senate']) for r in coverage)==3773924
    assert sum(int(r['historical_dashboard_2024_president']) for r in coverage)==5699141
    assert sum(int(r['historical_dashboard_2022_senate']) for r in coverage)==3773924
    manifest=json.loads((ROOT/'source-manifest.json').read_text())
    for k,m in manifest['sources'].items():
        assert hashlib.sha256(body(k)).hexdigest()==m['sha256']
        assert len(body(k))==m['bytes']
        assert (ROOT/m['headers_file']).is_file()
        if k.startswith('results-2024-') or k.startswith('results-2022-') or k.startswith('results-2026-'):
            assert m['http_status']==200 and m['complete']
    for name,sha in manifest['read_only_dependencies'].items():assert hashlib.sha256((DATA/name).read_bytes()).hexdigest()==sha
    normalized=list(csv.DictReader((ROOT/'dashboard-candidates.csv').open()))
    assert len(normalized)==1286
    assert len({(r['year'],r['county_fips'],r['candidate']) for r in normalized})==1286
    cchecks=list(csv.DictReader((ROOT/'historical-candidate-checks.csv').open()))
    assert len(cchecks)==75
    assert all(r['county_dashboard_sum']==r['state_dashboard'] for r in cchecks)
    assert all(r['dashboard_minus_certified']=='0' for r in cchecks if r['year']=='2022')
    local=json.loads((ROOT/'local-summary-checks.json').read_text());assert local['candidate_method_checks']==115 and local['differences']==0
    assert meta('absentee-counts-county-range')['http_status']==206
    assert meta('absentee-counts-county-range')['full_resource'] is False
    assert len(body('absentee-counts-county-range'))==65536
    assert not meta('absentee-counts-county')['complete']
    close=datetime.datetime(2026,11,3,19,30,tzinfo=ZoneInfo('America/New_York')).astimezone(datetime.timezone.utc)
    assert close.isoformat()=='2026-11-04T00:30:00+00:00'
    report=DATA.parent/'official-results.md';text=report.read_text();missing=[]
    assert 'G.S. 163-182.15(d)' in text
    rule=json.loads((ROOT/'rule-plurality.page.json').read_text())['text']
    assert '(d) Determining Results.' in rule and 'individuals having the highest number of votes' in rule
    for link in re.findall(r'\]\(([^)]+)\)',text):
        target=link.split('#')[0]
        generated_here={'data/results-sources/artifact-checks.json','data/results-sources/SHA256SUMS'}
        if target and not re.match(r'^[a-zA-Z]+:',target) and not (report.parent/target).exists() and target not in generated_here:missing.append(target)
    assert not missing,missing
    files=[f for f in ROOT.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name not in ('SHA256SUMS','artifact-checks.json')]
    assert all(f.stat().st_size<40_000_000 for f in files)
    hashes=[(f.relative_to(ROOT).as_posix(),hashlib.sha256(f.read_bytes()).hexdigest()) for f in files]
    hashes.append(('../official-results-sources.csv',hashlib.sha256((DATA/'official-results-sources.csv').read_bytes()).hexdigest()))
    hashes.append(('../../official-results.md',hashlib.sha256(report.read_bytes()).hexdigest()))
    (ROOT/'SHA256SUMS').write_text(''.join(f'{sha}  {name}\n' for name,sha in sorted(hashes)))
    save('artifact-checks.json',dict(passed=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_responses=len(manifest['sources']),county_inventory=100,shared_state_channels=4,priority_counties=38,
        historical_candidate_rows=1286,historical_candidate_method_checks=75,local_pdf_candidate_method_checks=115,
        original_body_checksums=True,read_only_dependency_checksums=True,missing_relative_links=missing,
        ordinary_poll_close_utc=close.isoformat(),hash_manifest_entries=len(hashes),maximum_stored_file_bytes=max(f.stat().st_size for f in files)))
    print('PASS: 100 counties; 38 priority; source/dependency hashes; candidate/method checks; local PDFs; links; bounds.')

if __name__=='__main__':main()
