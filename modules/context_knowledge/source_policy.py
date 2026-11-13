"""A materialized branch source remains bounded by its original source policy."""
from sdk.protocol import CoreError


def method_source(text):
    from sdk.protocol import decode
    try:value=decode(text)
    except CoreError:return False
    return isinstance(value,dict) and isinstance(value.get('schema'),str) and value['schema'].startswith('jarvis.method-card.')


def require_complete_export(db,scope):
    if db.one('SELECT 1 FROM memory_source_branches WHERE domain_id=?',(scope,)):
        raise CoreError('memory_collection_required','Export the parent and branches together to preserve source dependencies')


def destinations(db,ident,*,include_methods=False):
    if not include_methods:
        source=db.one('SELECT text FROM knowledge_sources WHERE id=?',(ident,))
        if source and method_source(source['text']):return []
    own={r['provider'] for r in db.all('SELECT provider FROM knowledge_destinations WHERE source_id=?',(ident,))}
    link=db.one('SELECT parent_id FROM memory_source_branches WHERE source_id=?',(ident,))
    if not link:return sorted(own)
    parent=db.one('SELECT status,text FROM knowledge_sources WHERE id=?',(link['parent_id'],))
    if not parent or parent['status']!='active':return []
    if not include_methods and method_source(parent['text']):return []
    allowed={r['provider'] for r in db.all('SELECT provider FROM knowledge_destinations WHERE source_id=?',(link['parent_id'],))}
    return sorted(own&allowed)


def permitted(*,methods=False):
    # s is the source alias; one provider placeholder, shared by lexical/vectors.
    role="CASE WHEN json_valid(s.text) THEN coalesce(json_extract(s.text,'$.schema'),'') LIKE 'jarvis.method-card.%' ELSE 0 END"
    parent_role="CASE WHEN json_valid(p.text) THEN coalesce(json_extract(p.text,'$.schema'),'') LIKE 'jarvis.method-card.%' ELSE 0 END"
    return ("s.status='active' AND "+('' if methods else 'NOT ')+"("+role+") AND EXISTS(SELECT 1 FROM knowledge_destinations d WHERE d.source_id=s.id AND d.provider=? "
            "AND NOT EXISTS(SELECT 1 FROM memory_source_branches b JOIN knowledge_sources p ON p.id=b.parent_id "
            "WHERE b.source_id=s.id AND (p.status!='active' OR "+('0' if methods else '('+parent_role+')')+" OR NOT EXISTS(SELECT 1 FROM knowledge_destinations pd "
            "WHERE pd.source_id=p.id AND pd.provider=d.provider))))")
