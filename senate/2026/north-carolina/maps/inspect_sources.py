"""Reproduce supplemental source observations; reads only retained evidence."""
from pathlib import Path
import io
import json
import sys
import zipfile
from source_io import ROOT, read, sha
sys.path.insert(0,str(ROOT/'.runtime'))
import shapefile
import shapely
from shapely.geometry import shape
from shapely.validation import explain_validity

def main():
    notes=dict(measurement_attribute_examples={},county_alternatives={})
    for vintage,base in [('2024-07-23','SBE_PRECINCTS_20240723'),('2026-08-24','SBE_PRECINCTS_20260824')]:
        z=zipfile.ZipFile(io.BytesIO(read('raw/'+base+'.zip')))
        r=shapefile.Reader(shp=io.BytesIO(z.read(base+'.shp')),shx=io.BytesIO(z.read(base+'.shx')),dbf=io.BytesIO(z.read(base+'.dbf')))
        sr=r.shapeRecord(0)
        g=shape(sr.shape.__geo_interface__)
        props=sr.record.as_dict()
        notes['measurement_attribute_examples'][vintage]=dict(source_row=1,properties=props,
            native_geometry_area_square_us_survey_feet=g.area,native_geometry_length_us_survey_feet=g.length,
            source_area_divided_by_native_computed_area=props['Shape_Area']/g.area,
            source_length_divided_by_native_computed_length=props['Shape_Leng']/g.length,
            interpretation='Source attributes preserved; units not inferred from field names.')
    wake=json.loads(read('raw/wake-attributes.json'))['features']
    notes['county_alternatives']['wake']=dict(features=len(wake),
        satellite_ids_found=[f['attributes']['PRECINCT'] for f in wake if f['attributes']['PRECINCT'] in ['01-07A','07-07A']],
        max_last_edited_epoch_ms=max(f['attributes']['LAST_EDITED_DATE'] for f in wake if f['attributes']['LAST_EDITED_DATE']))
    union=json.loads(read('raw/union-alias-alternative.geojson.gz'))
    notes['county_alternatives']['union']=[dict(properties=f['properties'],valid=shape(f['geometry']).is_valid,
        validity_reason=explain_validity(shape(f['geometry']))) for f in union['features']]
    notes['runtime']=dict(pyshp=shapefile.__version__,shapely=shapely.__version__,geos=shapely.geos_version_string)
    notes['manually_inspected_pdf_pages']=[
        dict(path='raw/wake-2021-07-20-minutes.pdf',page=1,sha256=sha((ROOT/'raw/wake-2021-07-20-minutes.pdf').read_bytes()),
            finding='County minutes describe approval of satellite resolutions for 01-07A and 07-07A; historical evidence, not current election approval.'),
        dict(path='raw/henderson-2025-08-19-minutes.pdf',page=9,sha256=sha((ROOT/'raw/henderson-2025-08-19-minutes.pdf').read_bytes()),
            finding='Carolina Village described as satellite within Hendersonville 2; county chair signature dated 2025-08-19; state executive director approval line blank.')]
    (ROOT/'source-inspection.json').write_text(json.dumps(notes,indent=2)+'\n')
    print('Supplemental source observations recorded; no source geometry modified.')

if __name__=='__main__':
    main()
