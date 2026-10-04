import sys, re, json
from html.parser import HTMLParser
VOID={'input','br','hr','img','meta','link'}
class P(HTMLParser):
    def __init__(s, fname):
        super().__init__(convert_charrefs=True); s.fname=fname
        s.fields={}; s.order=[]; s.section=[]; s.cap=None; s.captext=''
        s.last_label=None; s.last_help=None; s.prev_input_id=None
        s.pending_choice=None; s.select=None; s.opt=None; s.ids={}
        s.header_text=None; s.in_header=False; s.depth=0; s.header_depth=None
    def field(s,name,kind):
        if name not in s.fields:
            s.fields[name]={'name':name,'kind':kind,'label':s.last_label,'help':s.last_help,'section':s.header_text,'choices':[],'file':s.fname}
            s.order.append(name)
        return s.fields[name]
    def handle_starttag(s,tag,attrs):
        a=dict(attrs)
        cls=a.get('class') or ''
        if tag=='div' and 'card-header' in cls:
            s.cap=('header',); s.captext=''
        if tag=='h1' and 'modal-title' in cls:
            s.cap=('title',); s.captext=''
        if tag=='button' and a.get('data-bs-target','').endswith('Modal') and 'Help' in a.get('data-bs-target','') or (tag=='button' and a.get('data-bs-target') and 'question' in ''):
            pass
        if tag=='button' and a.get('data-bs-target'):
            s.pending_help=a['data-bs-target'].lstrip('#')
            s.btn_target=a['data-bs-target'].lstrip('#')
        if tag=='i' and 'bi-question-circle' in cls and getattr(s,'btn_target',None):
            s.last_help=s.btn_target
        if tag=='label':
            s.cap=('label',a.get('for')); s.captext=''
        if tag=='input':
            t=a.get('type','text'); n=a.get('name')
            if a.get('id'): s.ids[a['id']]=n
            if not n or t=='hidden' or t=='submit': return
            if t in('radio','checkbox'):
                f=s.field(n,t)
                f['choices'].append({'value':a.get('value'),'label':None,'id':a.get('id'),'checked':'checked' in a})
            else:
                f=s.field(n,t)
                for k in ('value','min','max','step','id','placeholder'):
                    if k in a: f[k]=a[k]
        if tag=='select':
            n=a.get('name') or a.get('id')
            s.select=s.field(n,'select'); s.select['id']=a.get('id')
        if tag=='option' and s.select is not None:
            s.opt={'value':a.get('value'),'label':'','selected':'selected' in a}; s.cap=('option',); s.captext=''
    def handle_endtag(s,tag):
        if s.cap and ((tag=='div' and s.cap[0]=='header') or (tag=='h1' and s.cap[0]=='title')):
            s.header_text=' '.join(s.captext.split()) if s.cap[0]=='header' else s.header_text
            if s.cap[0]=='title': s.title=' '.join(s.captext.split())
            s.cap=None
        if tag=='label' and s.cap and s.cap[0]=='label':
            txt=' '.join(s.captext.split()); f=s.cap[1]; s.cap=None
            # choice label?
            for fl in s.fields.values():
                for c in fl['choices']:
                    if c.get('id')==f and c['label'] is None:
                        c['label']=txt; return
            s.last_label=txt; s.last_label_for=f
        if tag=='option' and s.opt is not None:
            s.opt['label']=' '.join(s.captext.split()); s.select['choices'].append(s.opt); s.opt=None; s.cap=None
        if tag=='select': s.select=None
    def handle_data(s,d):
        if s.cap: s.captext+=d
def extract_fields(files):
    out={}
    for fn in files:
        txt=open(fn).read()
        p=P(fn); p.feed(txt)
        out[fn]=[p.fields[n] for n in p.order]
    return out
