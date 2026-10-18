#!/usr/bin/env python3
"""Fetch primary Alaska evidence with curl's default TLS verification.

Usage: fetch_evidence.py NAME URL [NAME URL ...]. Never disables TLS checks.
Original response bytes, response headers, curl metadata and SHA-256 retained.
"""
import datetime
import gzip
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent


def fetch(name, url):
    assert pathlib.Path(name).name == name and not name.startswith('.')
    target = ROOT / name
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    proc = subprocess.run([
        'curl', '--location', '--fail', '--silent', '--show-error',
        '--connect-timeout', '20', '--max-time', '120',
        '--dump-header', str(target) + '.headers',
        '--output', str(target), '--write-out', '%{json}', url,
    ], capture_output=True, text=True)
    record = dict(url=url, started_utc=started,
                  retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  curl_exit_code=proc.returncode, tls_verification='curl default; no insecure override',
                  error=proc.stderr, file=name)
    try:
        record['http'] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        record['curl_stdout'] = proc.stdout
    if target.exists():
        data = target.read_bytes()
        record.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if proc.returncode == 0 and target.suffix in {'.html', '.csv', '.txt'}:
            packed = gzip.compress(data, mtime=0)
            archive = pathlib.Path(str(target) + '.gz')
            archive.write_bytes(packed)
            record.update(stored_file=archive.name, storage='gzip; original bytes recovered by decompression',
                          stored_sha256=hashlib.sha256(packed).hexdigest(), stored_bytes=len(packed))
            target.unlink()
    headers = pathlib.Path(str(target) + '.headers')
    if headers.exists():
        record['headers_sha256'] = hashlib.sha256(headers.read_bytes()).hexdigest()
    (ROOT / (name + '.retrieval.json')).write_text(json.dumps(record, indent=2) + '\n')
    records = [json.loads(p.read_text()) for p in sorted(ROOT.glob('*.retrieval.json'))]
    (ROOT / 'evidence-manifest.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps({k: record.get(k) for k in ['file', 'url', 'retrieved_utc', 'curl_exit_code', 'bytes', 'sha256']}))
    if proc.returncode:
        raise RuntimeError(proc.stderr)


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--refresh']:
        manifest = json.loads((ROOT / 'evidence-manifest.json').read_text())
        args = [item for r in manifest if not r['curl_exit_code'] for item in [r['file'], r['url']]]
    if len(args) % 2:
        raise SystemExit(__doc__)
    for i in range(0, len(args), 2):
        fetch(args[i], args[i + 1])
