"""A materialized branch source remains bounded by its original source policy."""
from sdk.protocol import CoreError


def require_complete_export(db,scope):
    if db.one('SELECT 1 FROM memory_source_branches WHERE domain_id=?',(scope,)):
        raise CoreError('memory_collection_required','Export the parent and branches together to preserve source dependencies')


def destinations(db,ident):
    own={r['provider'] for r in db.all('SELECT provider FROM knowledge_destinations WHERE source_id=?',(ident,))}
    link=db.one('SELECT parent_id FROM memory_source_branches WHERE source_id=?',(ident,))
    if not link:return sorted(own)
    parent=db.one('SELECT status FROM knowledge_sources WHERE id=?',(link['parent_id'],))
    if not parent or parent['status']!='active':return []
    allowed={r['provider'] for r in db.all('SELECT provider FROM knowledge_destinations WHERE source_id=?',(link['parent_id'],))}
    return sorted(own&allowed)


def permitted():
    # s is the source alias; one provider placeholder, shared by lexical/vectors.
    return ("s.status='active' AND EXISTS(SELECT 1 FROM knowledge_destinations d WHERE d.source_id=s.id AND d.provider=? "
            "AND NOT EXISTS(SELECT 1 FROM memory_source_branches b JOIN knowledge_sources p ON p.id=b.parent_id "
            "WHERE b.source_id=s.id AND (p.status!='active' OR NOT EXISTS(SELECT 1 FROM knowledge_destinations pd "
            "WHERE pd.source_id=p.id AND pd.provider=d.provider))))")
