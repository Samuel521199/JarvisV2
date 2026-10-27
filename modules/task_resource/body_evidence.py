"""Pure checks for explicitly requested source-excerpt documents, not free prose truth."""
from sdk.protocol import CoreError

VERSION='body-evidence-1'


def validate(reference):
    if not isinstance(reference,dict) or set(reference)!={'sources','facts','plans'}:
        raise CoreError('trial_invalid','Expected bounded body evidence reference')
    sources=reference['sources']
    if not isinstance(sources,dict) or not 1<=len(sources)<=30:
        raise CoreError('trial_invalid','Expected source excerpt registry')
    for key,text in sources.items():
        if (not isinstance(key,str) or not key or len(key)>30 or not key.isascii()
                or not all(c.isalnum() or c in '-_' for c in key)
                or not isinstance(text,str) or not text.strip() or len(text)>1200
                or any(c in text for c in '\r\n\x00')):
            raise CoreError('trial_invalid','Invalid source ID or single-line excerpt')
    for kind in ('facts','plans'):
        ids=reference[kind]
        if (not isinstance(ids,list) or any(not isinstance(x,str) or x not in sources for x in ids)
                or len(ids)!=len(set(ids))):
            raise CoreError('trial_invalid','Unknown or duplicate required source')
    if set(reference['facts'])&set(reference['plans']):
        raise CoreError('trial_invalid','A fact and a confirmed plan must not share an identity')
    return reference


def render(value):
    """Render already shape-checked evidence, escaping source text as Markdown text."""
    def escape(text):
        for char in '\\`*_{}[]<>#!|':text=text.replace(char,'\\'+char)
        return text
    blocks=[]
    for field,title in [('facts','事实'),('plans','已确认计划'),('suggestions','建议（未采纳）')]:
        lines=[('- '+escape(x)) if field=='suggestions' else ('- ['+x['source']+'] '+escape(x['quote'])) for x in value[field]]
        blocks.append('## '+title+'\n'+('\n'.join(lines) if lines else '- 无'))
    return '\n\n'.join(blocks)


def assess(reference,value):
    """Reject uncited additions, stale selections and drift between fields and body."""
    checks=[]
    def add(key,passed):checks.append({'id':'body_'+key,'status':'passed' if passed else 'failed'})
    body=value.get('evidence')
    shape=isinstance(body,dict) and set(body)=={'facts','plans','suggestions'}
    if shape:
        for field in ('facts','plans'):
            rows=body[field]
            shape=shape and isinstance(rows,list) and len(rows)<=30
            if not shape:break
            shape=all(isinstance(r,dict) and set(r)=={'source','quote'} and isinstance(r['source'],str)
                      and isinstance(r['quote'],str) and len(r['quote'])<=1200 for r in rows)
            if not shape:break
        ideas=body['suggestions']
        shape=shape and isinstance(ideas,list) and len(ideas)<=5 and all(isinstance(t,str) and t.strip() and len(t)<=500 and not any(c in t for c in '\r\n\x00') for t in ideas)
    add('shape',shape)
    if not shape:return checks
    for field in ('facts','plans'):
        rows=body[field];ids=[r['source'] for r in rows]
        add(field+'_coverage',len(ids)==len(set(ids)) and set(ids)==set(reference[field]))
        add(field+'_grounding',all(r['source'] in reference['sources'] and r['quote']==reference['sources'][r['source']] for r in rows))
    # Normalize platform newlines and a single optional trailing newline only.
    doc=value.get('document')
    add('document_parity',isinstance(doc,str) and doc.replace('\r\n','\n').removesuffix('\n')==render(body))
    return checks
