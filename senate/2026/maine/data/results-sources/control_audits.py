from research import *
from collections import Counter
# Derivatives use the complete retained source tables, with source-row provenance.
p=ROOT/'extracted';r=json.loads((p/'ea9168a83a2208b62e32.json').read_text())['Dem CG2'];rr=[]
for row in r:
 n=row['row'];c={re.sub(r'\d+','',k):v for k,v in row['cells'].items()}
 if c.get('D') and all(c.get(k,'').isdigit() for k in 'FGHIJK'):
  vals=[int(c[x]) for x in 'FGHIJK'];assert sum(vals[:5])==vals[5]
  rr.append({'source_row':n,'office':c.get('A'),'district':c.get('B'),'county':c.get('C'),'town':c['D'],'ward_precinct':c.get('E'),'Baldacci':vals[0],'Dunlap':vals[1],'Loud':vals[2],'Wood':vals[3],'BLANK':vals[4],'TBC':vals[5]})
sums={k:sum(v[k] for v in rr) for k in ['Baldacci','Dunlap','Loud','Wood','BLANK','TBC']}
assert sums=={'Baldacci':24944,'Dunlap':22920,'Loud':8182,'Wood':22678,'BLANK':4756,'TBC':83480}
cvr=json.loads((p/'3e8ead0ae70c94422366.json').read_text());cv=next(iter(cvr.values()))[1:];ids=[x['cells']['A'+str(x['row'])] for x in cv];assert len(cv)==345 and len(set(ids))==342
first=Counter(x['cells'].get('D'+str(x['row'])) for x in cv)
assert first=={'Baldacci, Joseph M.':95,'Dunlap, Matthew G.':78,'Loud, Paige':80,'Wood, Jordan':76,'undervote':16}
rounds=[{'round':1,'Baldacci':24966,'Dunlap':22933,'Wood':22712,'Loud':8194,'exhausted':4675,'eliminated':'Loud, Paige'}, {'round':2,'Baldacci':25923,'Dunlap':25681,'Wood':25377,'Loud':0,'exhausted':6499,'eliminated':'Wood, Jordan'}, {'round':3,'Baldacci':32555,'Dunlap':35924,'Wood':0,'Loud':0,'exhausted':15001,'elected':'Dunlap, Matthew G.'}]
for x in rounds:assert sum(x[k] for k in ['Baldacci','Dunlap','Wood','Loud','exhausted'])==83480
# Round values manually transcribed from downloaded summary, not fabricated transfer data.
textpdf=(p/'266a08d91013335ab173.txt').read_text()
for n in [24966,22933,22712,8194,4675,25923,25681,25377,6499,32555,35924,15001,34240]:assert str(n) in textpdf
out={'election':'2026-06-09 Democratic Congressional District 2 primary; NOT November Senate','first_choice_workbook_request_id':'ea9168a83a2208b62e32','raw_nonempty_rows':len(r),'disjoint_data_rows':len(rr),'source_excel_row_range':[rr[0]['source_row'],rr[-1]['source_row']],'all_row_identities_pass':True,'blank_office_and_district_source_rows':[92,353],'sums':sums,'cvr_request_id':'3e8ead0ae70c94422366','cvr_rows':len(cv),'cvr_unique_record_ids':len(set(ids)),'cvr_first_rank':dict(first),'cvr_duplicate_record_ids':{k:v for k,v in Counter(ids).items() if v>1},'cvr_exact_duplicate_source_row_pairs':[[215,218],[216,219],[217,220]],'cvr_minus_initial_UOCAVA':{'Baldacci':0,'Dunlap':0,'Loud':0,'Wood':2,'undervote_or_BLANK':-2,'TBC':0},'cvr_duplicate_policy':'Retain every source row. Do not deduplicate, allocate or explain the mismatch without further primary evidence.','cvr_scope':'Only UOCAVA export, 345 ballots; local numeric precinct codes have no approved crosswalk to 2024/2026 polygons or newsroom VCU IDs','summary_request_id':'266a08d91013335ab173','rounds':rounds,'round_plus_exhausted_controls':83480,'initial_to_round1_candidate_difference':{'Baldacci':22,'Dunlap':13,'Loud':12,'Wood':34,'BLANK_or_exhausted':-81},'difference_explanation':'Stages differ. Complete local CVRs/auxiliaries were not downloaded; do not infer mechanism or fabricate transfers from this delta.','summary_date_field':'empty','summary_timezone':None,'summary_test_flag':None,'summary_completion_flag':None,'no_november_contest_id_or_cadence_claim':True}
(ROOT/'rcv-audit.json').write_text(json.dumps(out,indent=2)+'\n');(ROOT/'rcv-initial-source-rows.json').write_text(json.dumps(rr,indent=2)+'\n')
# Candidate workbook and PDF controls, all current linked artifacts, every row inspected.
cand=json.loads((p/'faa16009e9a48f60f351.json').read_text());cr=next(iter(cand.values()));us=[x for x in cr if x['cells'].get('A'+str(x['row']))=='US'];assert len(us)==2
names=['Susan M. Collins','Troy D. Jackson'];writeins=[('Brent Andrews','Unaffiliated','York'),('Sigrid Ann Olson','Democratic','Cape Elizabeth'),('Gina Oswald','Independent','Strong'),('Joseph Steinberger','Faith in Humanity','Rockland'),('Michael Turcotte','Un-enrolled','Burnham'),('Ashley J. Webb','Democratic','Farmington')]
wi=(p/'bac6a7f3e0a72ffb3fdb.txt').read_text()
for n,party,town in writeins:assert n in wi and party in wi and town in wi
for n in ['Collins, Susan M.','Jackson, Troy D.'] :assert n in (p/'18776dca67c4bad130cf.txt').read_text()
assert 'Graham C. Platner' in (p/'d1e0c78931c9adc5d6de.txt').read_text()
ca={'election_date':'2026-11-03','office_code':'US','office':'United States Senator','stage':'current pre-election published roster, not an election-night feed','printed_candidates':[{'name':n,'party':party,'residence':town,'source_excel_row':row} for n,party,town,row in [('Susan M. Collins','R','Bangor',2),('Troy D. Jackson','D','Allagash',3)]],'declared_write_ins':[{'name':n,'party_label_exact':party,'residence':town,'source_pdf_page':1} for n,party,town in writeins],'withdrawals':[{'name':'Graham C. Platner','party':'D','withdrawn':'2026-07-10','replacement':'Troy D. Jackson','replacement_received':'2026-07-27','late_excluded_candidate_under_723A':False}],'excluded_senate_candidates_identified':[],'negative_exclusions_certification_claim':False,'exclusions_gap':'No separate current exhaustive Senate death/disqualification/late-withdrawal bulletin established. Recheck before live ingestion. July withdrawal predates 70-day deadline and is removed from ballot, not a late excluded candidate.','candidate_ids':None,'sample_ballot_scope':'SOS linked sample CUM 0492111, CG1/SS25/SR110/Cumberland3, three ranking columns and one generic write-in row; not all ballot styles','source_request_ids':['faa16009e9a48f60f351','bac6a7f3e0a72ffb3fdb','d1e0c78931c9adc5d6de','18776dca67c4bad130cf'],'published_writein_date':'2026-10-15','published_withdrawal_date':'2026-09-22','landing_anchor_date_warning':'Upcoming index write-in label date remained 08/25/26; linked current document explicitly dated10/15/26. Use document vintage.'}
(ROOT/'candidates-2026.json').write_text(json.dumps(ca,indent=2)+'\n')
print('RCV',len(rr),sums,'CVR',len(cv),'candidate roster',len(us)+len(writeins))
