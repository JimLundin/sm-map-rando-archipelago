import sys, re, json, glob, html
from html.parser import HTMLParser
class P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True)
        s.modals={}; s.stack=[]; s.cur=None; s.mode=None
    def handle_starttag(s,tag,attrs):
        a=dict(attrs); cls=a.get('class') or ''
        if tag in ('br','hr','img','input','meta','link','source'): 
            if s.cur and s.mode=='body' and tag=='br': s.cur['body']+='\n'
            return
        s.stack.append((tag,cls,a.get('id')))
        if tag=='div' and cls.split()[:1]==['modal'] and a.get('id'):
            s.cur={'id':a['id'],'title':'','body':'','depth':len(s.stack)}
        if s.cur:
            if 'modal-title' in cls: s.mode='title'
            if 'modal-body' in cls: s.mode='body'; s.bodydepth=len(s.stack)
            if 'modal-footer' in cls: s.mode=None
            if s.mode=='body':
                if tag=='li': s.cur['body']+='\n- '
                elif tag in ('p','h5','h4','h6','div','ul','ol','table','tr'): s.cur['body']+='\n'
                elif tag in ('td','th'): s.cur['body']+=' | '
    def handle_endtag(s,tag):
        while s.stack:
            t,c,i=s.stack.pop()
            if s.cur and len(s.stack)+1==s.cur['depth'] :
                s.modals[s.cur['id']]=s.cur; s.cur=None; s.mode=None
            if s.cur and s.mode=='title' and 'modal-title' in c: s.mode=None
            if t==tag: break
        if s.cur and s.mode=='body' and tag in ('p','h5','li'): s.cur['body']+='\n'
    def handle_data(s,d):
        d=re.sub(r'\s+',' ',d)
        if s.cur and s.mode=='title': s.cur['title']+=d
        elif s.cur and s.mode=='body': s.cur['body']+=d
def clean(t):
    lines=[]
    for l in t.split('\n'):
        l=' '.join(l.split())
        if l in ('','|'): 
            continue
        if lines and lines[-1]=='-': lines[-1]='- '+l; continue
        lines.append(l)
    return '\n'.join(lines)
def extract_modals(files):
    out={}
    for fn in files:
        p=P(); p.feed(re.sub(r'\{%.*?%\}','',open(fn).read()))
        for k,v in p.modals.items():
            out[k]={'file':fn,'title':' '.join(v['title'].split()),'body':clean(v['body'])}
    return out
