"""Read-only consistency diagnostics. Never repairs or guesses source truth."""
import time
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.vectors import Vectors


def inspect(db,scope):
    started=time.monotonic()
    with db.read_snapshot():
        def count(sql,args=()):return db.one(sql,args)['n']
        counts={'facts':count('SELECT count(*) AS n FROM facts WHERE scope=? AND deleted=0',(scope,)),
                'forgotten':count('SELECT count(*) AS n FROM facts WHERE scope=? AND deleted=1',(scope,)),
                'pending_candidates':count("SELECT count(*) AS n FROM memory_candidates WHERE scope=? AND state='PENDING'",(scope,)),
                'sources':count("SELECT count(*) AS n FROM knowledge_sources WHERE scope=? AND status!='deleted'",(scope,)),
                'pending_claims':count("SELECT count(*) AS n FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id WHERE s.scope=? AND c.state='pending'",(scope,)),
                'history_versions':count('SELECT count(*) AS n FROM memory_history WHERE scope=?',(scope,)),
                'unknown_history_time':count('SELECT count(*) AS n FROM memory_history WHERE scope=? AND recorded IS NULL',(scope,))}
        issues=[]
        invalid=count("SELECT count(*) AS n FROM knowledge_claims c JOIN knowledge_sources s ON s.id=c.source_id "
                      "LEFT JOIN facts f ON f.id=c.fact_id WHERE s.scope=? AND c.state='accepted' AND "
                      "(s.status!='active' OR s.revision!=c.source_revision OR f.id IS NULL OR f.deleted=1)",(scope,))
        if invalid:issues.append({'code':'invalid_claim_dependency','count':invalid,'action':'review_claims'})
        invalid=count("SELECT count(*) AS n FROM memory_history h WHERE h.scope=? AND ((h.kind='fact' AND NOT EXISTS("
                      "SELECT 1 FROM facts f WHERE f.id=h.id AND f.deleted=0)) OR (h.kind='source' AND NOT EXISTS("
                      "SELECT 1 FROM knowledge_sources s WHERE s.id=h.id AND s.status!='deleted')))",(scope,))
        if invalid:issues.append({'code':'orphan_history','count':invalid,'action':'review_cleanup'})
        slot=Knowledge(db).slot();fts={'available':bool(slot),'consistent':None}
        if slot:
            try:
                # Global index coverage: no text or IDs leave the diagnostic route.
                missing=count(f'SELECT count(*) AS n FROM knowledge_chunks c WHERE NOT EXISTS(SELECT 1 FROM {slot} f WHERE f.rowid=c.seq)')
                extra=count(f'SELECT count(*) AS n FROM {slot} f WHERE NOT EXISTS(SELECT 1 FROM knowledge_chunks c WHERE c.seq=f.rowid)')
                fts.update(consistent=missing==extra==0,missing=missing,orphan_rows=extra)
                if missing or extra:issues.append({'code':'fts_coverage','count':missing+extra,'action':'rebuild_fts'})
            except Exception:
                fts.update(available=False,consistent=False)
                issues.append({'code':'fts_unavailable','count':1,'action':'rebuild_fts'})
        vectors=Vectors(db).status()
    return {'version':'memory-health-1.0.0','scope':scope,'counts':counts,'issues':issues,'fts':fts,
            'vectors':{'active':bool(vectors['active']),'count':vectors['vectors'],'stale':vectors['stale'],
                       'recipe_current':vectors['recipe_current'],'staging':len(vectors['staging'])},
            'elapsed_ms':round(1000*(time.monotonic()-started),3),
            'coverage':'Current-scope ledger checks and global projection coverage; not semantic truth, full integrity or privacy certification'}
