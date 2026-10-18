#!/usr/bin/env python3
"""Inspect retained HTML without executing a publisher application."""
from html.parser import HTMLParser
from urllib.parse import urljoin
from fetch import read,ROOT
import json,re,sys
class Page(HTMLParser):
    def __init__(self,body,base):
        super().__init__();self.base=base;self.links=[];self.texts=[];self.current=None;self.skip=0
        self.feed(body.decode('utf-8',errors='replace'))
    def handle_starttag(self,t,a):
        d=dict(a)
        if t=='base' and d.get('href'):self.base=urljoin(self.base,d['href'])
        if t in ['script','style']:self.skip+=1
        if t in ['a','iframe','script','link']:
            v=d.get('href') or d.get('src')
            if v:
                self.current={'tag':t,'url':urljoin(self.base,v),'text':''};self.links.append(self.current)
    def handle_endtag(self,t):
        if t in ['script','style']: self.skip=max(0,self.skip-1)
        if t=='a':self.current=None
    def handle_data(self,s):
        s=' '.join(s.split())
        if s and not self.skip:self.texts.append(s)
        if self.current and self.current['tag']=='a':self.current['text']+=s+' '
def page(sid):
    m=json.loads((ROOT/'raw'/f'{sid}.json').read_text());return Page(read(sid),m['final_url'])
if __name__=='__main__':
    p=page(sys.argv[1]);pat=sys.argv[2] if len(sys.argv)>2 else '.*'
    print('\n'.join(json.dumps(x) for x in p.links if re.search(pat,x['url']+' '+x['text'],re.I)))
    if len(sys.argv)>3: print('\n'.join(p.texts))
