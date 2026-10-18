#!/usr/bin/env python3
"""Extract clocks without treating them as adoption/approval evidence."""
import datetime,io,json,zipfile,xml.etree.ElementTree as ET
from acquire import ROOT,original,sha,save_json
def main():
 out=[]
 for key in ['tlc-24g','tlc-26p','tlc-22g','tlc-20g']:
  d=json.loads((ROOT/'sources'/(key+'.json')).read_text());z=zipfile.ZipFile(io.BytesIO(original(d)));members=[]
  for name in z.namelist():
   if not name.endswith('.xml'):continue
   b=z.read(name);xml=ET.fromstring(b);clocks=[]
   for e in xml.iter():
    tag=e.tag.rsplit('}',1)[-1]
    if ('date' in tag.lower() or 'time' in tag.lower()) and e.text and e.text.strip() and len(e.text)<300:clocks.append(dict(tag=tag,literal=e.text.strip(),attributes=e.attrib))
   members.append(dict(member=name,bytes=len(b),sha256=sha(b),literal_clocks=clocks))
  out.append(dict(source_id=key,zip_original_sha256=d['original_sha256'],retrieved_utc=d['retrieved_utc'],http_last_modified=d.get('headers',{}).get('Last-Modified'),zip_member_metadata=members,interpretation='File/processing/retrieval clocks only. Election vintage is catalog identity; current legal approval remains unknown.'))
 for p in sorted((ROOT/'gis').glob('*-audit.json')):
  a=json.loads(p.read_text());item=ROOT/'sources'/('gis-'+a['id']+'-item.json');im={}
  if item.exists():
   d=json.loads(item.read_text())
   try:im=json.loads(original(d))
   except:pass
  clocks={}
  for k in ['created','modified','lastViewed']:
   if isinstance(im.get(k),(int,float)):clocks[k]=dict(milliseconds_since_epoch=im[k],utc=datetime.datetime.fromtimestamp(im[k]/1000,datetime.timezone.utc).isoformat())
  out.append(dict(source_id=a['id'],editingInfo=a.get('editingInfo'),item_clocks=clocks,item_owner=im.get('owner'),item_title=im.get('title'),item_type=im.get('type'),item_access=im.get('access'),item_metadata_error=im.get('error'),interpretation='Item create/edit and service editing clocks are not legal approval. All per-feature edit fields retained in original batch attributes.'))
 save_json(ROOT/'metadata-dates.json',dict(sources=out))
 # Explicit authority chains; only claimed links are those present in retained bytes.
 save_json(ROOT/'authority-chains.json',dict(statewide=dict(authority='Texas Legislative Council',parent='https://data.capitol.texas.gov/dataset/precincts',linked_downloads=['tlc-24g','tlc-26p','tlc-22g','tlc-20g'],scope='County-collected reference precincts; county office controls adoption.'),linked_GIS_chains=[dict(county='Fort Bend',source_ids=['route-fort-bend-1','arcitem-fort-bend-ca30668087cd407a83ad6da187567b3c-data','arcitem-fort-bend-47f2ac69730446098c0e1567efa84dac-data'],layer='fort-bend-2025'),dict(county='Bell',source_ids=['route-bell-1','arcitem-bell-d6d621015b3540c0a0a31f693d700f64-data'],layer='bell-2022'),dict(county='Hays',source_ids=['extra-hays-map-page','arcitem-hays-9827d03c523f424e8d210a772b1003c0-data','arcitem-hays-eeeb1e20d0dc4a7fb8d2769af2f0ccb7-data'],layer='hays-2026'),dict(county='Johnson',source_ids=['route-johnson-1','arcitem-johnson-fc6c7c88e1024b8493d64a554c38db16-data','arcitem-johnson-d0329206d4cd4c2a9746c8cbe26f38e7-data'],layer='johnson-2022')],direct_official_GIS_discovery=['bexar-voter','travis-precincts','brazoria-2024','brazoria-2026'],direct_discovery_limit='County-controlled GIS domains and retained election parent routes establish publisher context; no unobserved app-to-service link is asserted.',PDFs='Exact county/vendor parent URLs and original HTTP metadata in per-source JSON; all failed attempts retained.',source_name_conflict='A name such as proposed/adopted/2025/VTD may conflict with other metadata. Neither title nor clock alone establishes current approval.'))
if __name__=='__main__':main()
