"""Recreate the retained PDF and map PNG checks using Poppler and librsvg."""
from pathlib import Path
import subprocess
import json
from source_io import ROOT, sha

JOBS = [
    ("raw/henderson-2025-08-19-minutes.pdf", "previews/henderson-satellite-resolution.png", ["pdftoppm", "-f", "9", "-l", "9", "-scale-to", "1600", "-singlefile", "-png"]),
    ("raw/wake-2021-07-20-minutes.pdf", "previews/wake-satellite-minutes.png", ["pdftoppm", "-f", "1", "-l", "1", "-scale-to", "1500", "-singlefile", "-png"]),
    ("2026-08-24/wake.svg", "previews/wake-current.png", ["rsvg-convert", "-w", "1000"]),
    ("2024-07-23/union.svg", "previews/union-historical.png", ["rsvg-convert", "-w", "1000"]),
]

def main():
    (ROOT/"previews").mkdir(exist_ok=True)
    records=[]
    for source, target, command in JOBS:
        if command[0] == "pdftoppm":
            cmd=command+[str(ROOT/source),str((ROOT/target).with_suffix(""))]
        else:
            cmd=command+[str(ROOT/source),"-o",str(ROOT/target)]
        subprocess.run(cmd,check=True)
        records.append(dict(input=source,input_sha256=sha((ROOT/source).read_bytes()),output=target,
            output_sha256=sha((ROOT/target).read_bytes()),command=cmd))
    source="raw/wake-2021-07-20-minutes.pdf"
    target="raw/wake-2021-07-20-minutes.txt"
    cmd=["pdftotext","-layout",str(ROOT/source),str(ROOT/target)]
    subprocess.run(cmd,check=True)
    records.append(dict(input=source,input_sha256=sha((ROOT/source).read_bytes()),output=target,
        output_sha256=sha((ROOT/target).read_bytes()),command=cmd))
    (ROOT/"preview-provenance.json").write_text(json.dumps(records,indent=2)+"\n")

if __name__ == "__main__":
    main()
