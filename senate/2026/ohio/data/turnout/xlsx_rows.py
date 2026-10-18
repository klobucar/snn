"""Read cached scalar values from source XLSX with Python's standard library."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def sheets(path, names=None, columns=None):
    with ZipFile(path) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            strings = ["".join(t.itertext()) for t in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        rels = {r.attrib["Id"]: r.attrib["Target"].lstrip("/") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        for sheet in ET.fromstring(z.read("xl/workbook.xml")).findall("s:sheets/s:sheet", NS):
            name = sheet.attrib["name"]
            if names is not None and name not in names:
                continue
            rel = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rels[rel]
            if not target.startswith("xl/"):
                target = "xl/" + target
            rows = []
            for _, row in ET.iterparse(z.open(target), events=("end",)):
                if row.tag != "{" + NS["s"] + "}row":
                    continue
                cells = {}
                for cell in row:
                    address = cell.attrib["r"]
                    col = "".join(c for c in address if c.isalpha())
                    if columns is not None and col not in columns:
                        continue
                    val = cell.find("s:v", NS)
                    typ = cell.attrib.get("t")
                    value = val.text if val is not None else None
                    if typ == "s" and value is not None:
                        value = strings[int(value)]
                    elif typ == "inlineStr":
                        value = "".join(cell.find("s:is", NS).itertext())
                    elif value is not None and typ != "str":
                        value = float(value) if "." in value or "E" in value.upper() else int(value)
                    if value is not None:
                        cells[col] = value
                if cells:
                    rows.append((int(row.attrib["r"]), cells))
                row.clear()
            yield name, rows

if __name__ == "__main__":
    import sys
    for name, rows in sheets(sys.argv[1]):
        print(name, len(rows))
        print(*rows[:6], sep="\n")
