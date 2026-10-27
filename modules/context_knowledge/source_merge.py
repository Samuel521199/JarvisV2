"""Owner-reviewed text/chapter merge with immutable bases and current revocations.

No semantic rewrite is guessed: only identical or disjoint line edits combine.
Overlapping edits remain explicit owner choices. Documents are still references.
"""
import difflib
import time
from modules.context_knowledge.domains import Domains
from modules.context_knowledge.history import record
from modules.context_knowledge.knowledge import Knowledge, MAX_BYTES
from sdk.protocol import CoreError, canonical, decode, digest

VERSION='memory-source-merge-1.0.0'


def combine(base,parent,branch):
    if parent==branch:return parent
    if parent==base:return branch
    if branch==base:return parent
    before=base.splitlines(keepends=True);left=parent.splitlines(keepends=True);right=branch.splitlines(keepends=True)
    if max(len(before),len(left),len(right))>2000:return None
    edits=[]
    for side,lines in enumerate((left,right)):
        for tag,i,j,a,b in difflib.SequenceMatcher(None,before,lines).get_opcodes():
            if tag!='equal':edits.append((i,j,lines[a:b],side))
    accepted=[]
    for i,j,lines,side in sorted(edits,key=lambda e:(e[0],e[1],e[3])):
        duplicate=False
        for a,b,replacement,other in accepted:
            if (i,j,lines)==(a,b,replacement):duplicate=True;break
            if other!=side and (max(i,a)<min(j,b) or i==j and a<=i<=b or a==b and i<=a<=j):return None
        if not duplicate:accepted.append((i,j,lines,side))
    result=list(before)
    for i,j,lines,_ in reversed(accepted):result[i:j]=lines
    value=''.join(result)
    return value if value.strip() and len(value.encode())<=MAX_BYTES else None


class SourceMerge:
    def __init__(self,db):self.db=db;self.library=Knowledge(db)

    def domain(self,scope):
        value=Domains(self.db).get(scope)
        if value['kind']!='branch':raise CoreError('memory_invalid','Source merge requires a project branch')
        return value

    def inherited(self,scope):
        domain=self.domain(scope)
        return self.db.all("SELECT s.id,s.revision,s.title,m.revision AS base_revision,b.source_id AS branch_id "
                           "FROM memory_snapshots m JOIN knowledge_sources s ON s.id=m.id "
                           "LEFT JOIN memory_source_branches b ON b.domain_id=m.domain_id AND b.parent_id=m.id "
                           "WHERE m.domain_id=? AND m.kind='source' AND s.scope=? AND s.status!='deleted' ORDER BY s.title",(scope,domain['parent']))

    def fork(self,scope,ident,revision):
        if type(revision) is not int or revision<1:raise CoreError('memory_invalid','Invalid source base revision')
        with self.db.transaction() as tx:
            self.domain(scope)
            base=Domains(self.db).historical_source(scope,ident,revision)
            old=tx.execute('SELECT source_id FROM memory_source_branches WHERE domain_id=? AND parent_id=?',(scope,ident)).fetchone()
            if old:
                local=tx.execute('SELECT status FROM knowledge_sources WHERE id=?',(old['source_id'],)).fetchone()
                if local['status']=='deleted':raise CoreError('knowledge_missing','Forgotten branch copies cannot be recreated')
                return {'id':old['source_id'],'existing':True}
            result=self.library.save_in(tx,{'id':'','scope':scope,'title':base['title'],'text':base['text'],'providers':[],'paused':True},0)
            if result.get('existing'):raise CoreError('conflict','An independent identical branch source exists; keep its provenance separate')
            tx.execute('INSERT INTO memory_source_branches VALUES(?,?,?,?)',(scope,result['id'],ident,revision))
            return result

    def values(self,local):
        link=self.db.one('SELECT * FROM memory_source_branches WHERE source_id=?',(local['id'],))
        parent=self.db.one('SELECT * FROM knowledge_sources WHERE id=?',(link['parent_id'],)) if link else None
        old=self.db.one("SELECT body FROM memory_history WHERE kind='source' AND id=? AND revision=?",(link['parent_id'],link['base_revision'])) if link else None
        base=decode(old['body']) if old else None
        live=lambda row: {'title':row['title'],'text':row['text']} if row and row['status']!='deleted' else None
        current,branch=live(parent),live(local)
        combined=None
        if base and current and branch:
            title=combine(base['title'],current['title'],branch['title'])
            text=combine(base['text'],current['text'],branch['text'])
            if title is not None and 1<=len(title.strip())<=160 and text is not None:combined={'title':title,'text':text}
        state=('forgotten' if parent and parent['status']=='deleted' else 'missing_base' if link and not base
               else 'unchanged' if branch==current or base and branch==base else 'delete' if not branch and current==base
               else 'create' if not link and branch else 'replace' if current==base else 'combined' if combined else 'conflict')
        return link,parent,{'base':base,'parent':current,'branch':branch,'combined':combined,'state':state}

    def plan(self,scope):
        domain=self.domain(scope);items=[]
        for local in self.db.all('SELECT * FROM knowledge_sources WHERE scope=? ORDER BY id',(scope,)):
            link,parent,values=self.values(local)
            if local['status']=='deleted' and not link:continue
            items.append({'id':local['id'],'title':local['title'] or (parent['title'] if parent else '已删除资料'),
                          'revision':local['revision'],'parent_id':parent['id'] if parent else None,
                          'parent_revision':parent['revision'] if parent else 0,'base_revision':link['base_revision'] if link else None,
                          'state':values['state'],'combined_available':values['combined'] is not None,
                          'content_digest':digest(values)})
        return {'scope':scope,'parent':domain['parent'],'items':items,'version':VERSION,
                'token':digest({'domain':domain,'epoch':self.library.epoch(),'items':items}),
                'policy':'reference_only_paused_without_destinations'}

    def preview(self,scope):
        with self.db.read_snapshot():return self.plan(scope)

    def detail(self,scope,ident):
        with self.db.read_snapshot():
            self.domain(scope)
            local=self.db.one('SELECT * FROM knowledge_sources WHERE id=? AND scope=?',(ident,scope))
            if not local:raise CoreError('knowledge_missing','Branch source unavailable')
            return self.values(local)[2]|{'id':ident,'revision':local['revision']}

    def apply(self,scope,token,choices):
        if not isinstance(token,str) or not isinstance(choices,dict) or len(choices)>200 or any(v not in {'parent','branch','combined'} for v in choices.values()):
            raise CoreError('memory_invalid','Review each source merge explicitly')
        receipt='source-merge-'+digest({'scope':scope,'token':token,'choices':choices})
        with self.db.transaction() as tx:
            self.domain(scope)
            prior=tx.execute('SELECT counts FROM memory_imports WHERE id=?',(receipt,)).fetchone()
            if prior:return decode(prior['counts'])|{'replayed':True}
            plan=self.plan(scope)
            if token!=plan['token']:raise CoreError('conflict','Sources changed; preview the merge again')
            actions={r['id']:r for r in plan['items'] if r['state'] not in {'forgotten','missing_base','unchanged'}}
            if set(choices)!=set(actions):raise CoreError('memory_invalid','Every source change needs a choice')
            changed=0
            for ident,choice in choices.items():
                if choice=='parent':continue
                row=actions[ident]
                local=self.db.one('SELECT * FROM knowledge_sources WHERE id=?',(ident,))
                values=self.values(local)[2];selected=values[choice]
                if choice=='combined' and selected is None:raise CoreError('memory_invalid','Overlapping edits require manual review')
                if selected is None:
                    self.library.delete_in(tx,plan['parent'],row['parent_id'],row['parent_revision'])
                else:
                    result=self.library.save_in(tx,{'id':row['parent_id'] or '','scope':plan['parent'],**selected,'providers':[],'paused':True},row['parent_revision'])
                    if result.get('existing'):raise CoreError('conflict','An independent identical parent source exists; no lineage guessed')
                    if not row['parent_id']:
                        tx.execute('INSERT INTO memory_source_branches VALUES(?,?,?,?)',(scope,ident,result['id'],result['revision']))
                        record(tx,'source',tx.execute('SELECT * FROM knowledge_sources WHERE id=?',(result['id'],)).fetchone())
                changed+=1
            result={'changed':changed,'kept_parent':sum(v=='parent' for v in choices.values()),'receipt':receipt,'replayed':False,'policy':plan['policy']}
            tx.execute('INSERT INTO memory_imports VALUES(?,?,?,?,?)',(receipt,plan['parent'],digest(choices),time.time(),canonical(result)))
            return result
