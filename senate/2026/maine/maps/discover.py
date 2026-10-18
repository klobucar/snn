#!/usr/bin/env python3
"""Retain official landing bytes; expose their actual linked map URLs."""
from html.parser import HTMLParser
from urllib.parse import urljoin
from acquire import fetch,ROOT
import json
class Links(HTMLParser):
    def __init__(self):super().__init__();self.href='';self.txt='';self.links=[];self.base=None
    def handle_starttag(self,t,a):
        if t=='base':self.base=dict(a).get('href')
        if t=='a':self.href=dict(a).get('href') or '';self.txt=''
    def handle_data(self,d):self.txt+=d
    def handle_endtag(self,t):
        if t=='a':
            if self.href:self.links.append((self.txt.strip(),self.href))
            self.href='';self.txt=''
def links(body,url):
    p=Links();p.feed(body.decode('utf8','replace'))
    return [(t,urljoin(urljoin(url,p.base or ''),h)) for t,h in p.links]
if __name__=='__main__':
    for x in json.loads((ROOT/'municipal-sources.json').read_text()):
        try:
            body=fetch(x['id']+'-landing',x['landing'])
            print('\n'+x['id'])
            for t,h in links(body,x['landing']):
                if any(w in (t+' '+h).lower() for w in ['ward','district map','voting map','precinct','arcgis']):print(t,h)
        except Exception as e:print(x['id'],str(e))
