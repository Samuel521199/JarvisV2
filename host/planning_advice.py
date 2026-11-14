"""Bounded task-planning advice, provenance and counterevidence; never authority.

Uses existing goal context, source permissions, model calls and completion facts.
It does not infer that exposure caused an outcome or promote advice into facts.
"""
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.knowledge import Knowledge
from modules.context_knowledge.joint import members
from modules.context_knowledge.methods import select,text_digest,parse
from modules.task_resource.plans import Plans
from sdk.protocol import CoreError,canonical,decode,digest

KEY='conditional_advice'
VERSION=1
BAD={'NEEDS_CORRECTION','INVALIDATED'}


def family(method):
    # Names, revisions, expiry and copied observations are not a new procedure.
    return digest({'requires':method['requires'],'summary':method['summary'].strip(),
        'counterexamples':[s.strip() for s in method['counterexamples']]})


def binding(plan):
    return digest({k:plan[k] for k in ('request','routes','catalog','generation','planning_round')})


class PlanningAdvice:
    def __init__(self,db):self.db=db

    def allowed(self,scope,provider,enabled):
        if not enabled:return {}
        memory=Memory(self.db)
        ordinary=memory.references(scope,provider,True,{'channel':'task'})
        methods=[r for s in (members(scope) or [scope]) for r in Knowledge(self.db).references(s,provider,methods=True)]
        return {r['id']:r['revision'] for r in ordinary+methods}

    def resolver(self,scope,providers,enabled):
        rights=[self.allowed(scope,p,enabled) for p in providers]
        def resolve(ident):
            row=self.db.one("SELECT id,revision,text FROM knowledge_sources WHERE id=? AND status='active'",(ident,))
            return row if row and rights and all(r.get(ident)==row['revision'] for r in rights) else None
        return resolve

    def held(self,scope,ref,goal_id,transfer=None):
        # Recheck authoritative completion, not a cached 'success count'. All
        # exposed advice is held after unresolved counterevidence; cause unknown.
        if not self.db.one("SELECT value FROM meta WHERE key='completion_schema'"):return False
        return bool(self.db.one("""SELECT g.goal_id FROM goal_context g
            JOIN goal_plans p ON p.id=g.goal_id JOIN task_completion c ON c.task_id=p.task_id
            WHERE g.scope=? AND g.goal_id!=? AND json_extract(g.view,'$.conditional_advice.version')=1
            AND json_extract(c.body,'$.state')='NEEDS_CORRECTION'
            AND (json_extract(c.body,'$.feedback.kind')='reject' OR EXISTS(
                SELECT 1 FROM json_each(c.body,'$.checks') criterion WHERE json_extract(criterion.value,'$.status')='failed'))
            AND (EXISTS(SELECT 1 FROM json_each(g.view,'$.conditional_advice.receipt.methods') m
                WHERE json_extract(m.value,'$.source_id')=? AND json_extract(m.value,'$.source_revision')=?
                AND json_extract(m.value,'$.source_digest')=?) OR EXISTS(
                SELECT 1 FROM json_each(g.view,'$.conditional_advice.families') f WHERE f.value=?)) LIMIT 1""",
            (scope,goal_id,ref['source_id'],ref['source_revision'],ref['source_digest'],transfer or '')))

    def offer(self,plan,scope,enabled,selectors):
        if not enabled or not plan['routes']:return None
        providers=list(dict.fromkeys(r['id'] for r in plan['routes']));resolve=self.resolver(scope,providers,enabled)
        sources=[];seen=set()
        for part in (members(scope) or [scope]):
            candidates=Knowledge(self.db).search(part,providers[0],plan['request']['goal']+' '+plan['request']['input_text'],methods=True)[0]
            for candidate in candidates:
                ident=candidate['evidence']['source_id']
                if ident in seen:continue
                seen.add(ident);row=resolve(ident)
                if row:
                    ref={'source_id':ident,'source_revision':row['revision'],'source_digest':text_digest(row['text'])}
                    try:transfer=family(parse(row['text']))
                    except CoreError:transfer=None
                    if not self.held(scope,ref,plan['id'],transfer):sources.append(row)
                if len(seen)>=12:break
            if len(seen)>=12:break
        result=select(sources,selectors,resolve,limit=2,max_bytes=3000)
        if not result['methods']:return None
        refs={}
        for method in result['methods']:
            refs[method['source_id']]=method['source_revision']
            for ref in method['evidence']:refs[ref['source_id']]=ref['revision']
        return {'version':VERSION,'binding':binding(plan),'selectors':selectors,'receipt':result['receipt'],
            'dependencies':[{'id':i,'revision':r} for i,r in sorted(refs.items())],
            'families':{m['source_id']:family(m) for m in result['methods']}}

    def inherit(self,plan,parent,context):
        bundle=context['view'].get(KEY)
        if not bundle:return None
        self.checked(parent,context,bundle['selectors'])
        return {'version':VERSION,'mode':'inherited','binding':binding(plan),'parent_goal':parent['id'],
            'parent_binding':binding(parent),'selectors':bundle['selectors'],'receipt':bundle['receipt'],
            'dependencies':bundle['dependencies'],'families':bundle['families']}

    def checked(self,plan,context,selectors,destinations=None,depth=0):
        if KEY not in context['view']:return []
        bundle=context['view'][KEY]
        try:
            if (not isinstance(bundle,dict) or type(bundle.get('version')) is not int or bundle['version']!=VERSION
                or bundle['binding']!=binding(plan) or (bundle.get('mode')!='inherited' and bundle['selectors']!=selectors)
                or not context['enabled'] or context['view'].get('redacted')):raise ValueError('Advice binding changed')
            mode=bundle.get('mode')
            required={'version','binding','selectors','receipt','dependencies','families'}|({'mode','parent_goal','parent_binding'} if mode=='inherited' else set())
            if mode not in (None,'inherited') or not required<=set(bundle)<=required|{'dispatch','observation'}:
                raise ValueError('Unknown advice fields or mode')
            if bundle.get('mode')=='inherited':
                if depth>=8 or bundle['parent_goal']==plan['id']:raise ValueError('Advice inheritance cycle or depth')
                row=self.db.one('SELECT * FROM goal_context WHERE goal_id=?',(bundle['parent_goal'],))
                if not row or row['scope']!=context['scope'] or not row['enabled']:raise ValueError('Inherited scope changed')
                row['view']=decode(row['view']);parent=Plans(self.db).get(bundle['parent_goal'])
                if binding(parent)!=bundle['parent_binding']:raise ValueError('Parent advice context changed')
                prior=row['view'].get(KEY)
                if not prior:raise ValueError('Parent advice provenance missing')
                self.checked(parent,row,prior['selectors'],destinations,depth+1)
                if bundle['dependencies']!=prior['dependencies'] or bundle['receipt']!=prior['receipt'] or bundle['families']!=prior['families']:
                    raise ValueError('Inherited dependency receipt changed')
                return []
            receipt=bundle['receipt'];refs=receipt['methods']
            if (set(receipt)!={'version','context_digest','methods'} or not isinstance(refs,list)
                or not 1<=len(refs)<=2 or len({r['source_id'] for r in refs})!=len(refs)):
                raise ValueError('Advice receipt changed')
            providers=destinations or [r['id'] for r in plan['routes']]
            resolve=self.resolver(context['scope'],providers,bool(context['enabled']))
            sources=[resolve(r['source_id']) for r in refs]
            if any(r is None for r in sources):raise ValueError('Source no longer authorized')
            result=select(sources,selectors,resolve,limit=2,max_bytes=3000)
            if result['receipt']!=receipt or any(self.held(context['scope'],r,plan['id'],family(m)) for r,m in zip(refs,result['methods'])):
                raise ValueError('Advice or counterevidence changed')
            if bundle['families']!={m['source_id']:family(m) for m in result['methods']}:
                raise ValueError('Advice procedure family changed')
            dependencies={}
            for method in result['methods']:
                dependencies[method['source_id']]=method['source_revision']
                for ref in method['evidence']:dependencies[ref['source_id']]=ref['revision']
            if bundle['dependencies']!=[{'id':i,'revision':r} for i,r in sorted(dependencies.items())]:
                raise ValueError('Advice dependency inventory changed')
            return result['methods']
        except (CoreError,KeyError,ValueError,TypeError) as error:
            raise CoreError('goal_context_changed','Planning advice changed, was withdrawn or needs counterevidence review') from error

    def assembly(self,plan,context,run_id,prompt):
        if KEY not in context['view']:return
        view=context['view'];original=canonical(view);bundle=view[KEY]
        stamp={'run_id':run_id,'input_digest':digest({'prompt':prompt,'schema':'goal-plan'})}
        if bundle.get('dispatch')==stamp:return
        # Assembly is not dispatch. Projection consults the real model ledger.
        bundle['dispatch']=stamp
        with self.db.transaction() as tx:
            if tx.execute('UPDATE goal_context SET view=? WHERE goal_id=? AND view=?',(canonical(view),plan['id'],original)).rowcount!=1:
                raise CoreError('goal_context_changed','Advice context changed during prompt assembly')
            self.db.event(tx,None,'goal.advice_assembled',{'goal_id':plan['id'],'run_id':run_id,'input_digest':stamp['input_digest'],
                'source_ids':[r['source_id'] for r in bundle['receipt']['methods']]})

    def observe(self,task_id,completion,tx):
        row=self.db.one('SELECT g.* FROM goal_context g JOIN goal_plans p ON p.id=g.goal_id WHERE p.task_id=?',(task_id,))
        if not row:return
        view=decode(row['view']);bundle=view.get(KEY)
        if not bundle or view.get('redacted'):return
        if type(bundle.get('version')) is not int or bundle['version']!=VERSION:
            raise CoreError('goal_context_changed','Unknown planning advice version')
        observation={'task_id':task_id,'fingerprint':completion['fingerprint'],'state':completion['state'],
            'condition_score':completion['condition_score'],'score_scope':completion['score_scope'],
            'coverage_complete':completion['requirement_coverage']['complete'],
            'review_required':completion['state'] in BAD,'causal_contribution':None}
        if bundle.get('observation')==observation:return
        bundle['observation']=observation
        tx.execute('UPDATE goal_context SET view=? WHERE goal_id=?',(canonical(view),row['goal_id']))
        self.db.event(tx,task_id,'goal.advice_observed',{'goal_id':row['goal_id'],**observation,
            'source_ids':[r['source_id'] for r in bundle['receipt']['methods']]})

    def projection(self,plan,context,selectors):
        if not context or KEY not in context['view']:return None
        bundle=context['view'][KEY];current=False
        try:self.checked(plan,context,selectors);current=True
        except CoreError:pass
        stamp=bundle.get('dispatch',{});calls=[]
        if stamp:
            calls=self.db.all('SELECT id,status,usage,input_digest FROM model_calls WHERE run_id=? AND phase=? ORDER BY created',
                (stamp['run_id'],'goal-plan'))
            calls=[{'id':r['id'],'status':r['status'],'usage':decode(r['usage']) if r['usage'] else None}
                for r in calls if r['input_digest']==stamp['input_digest']]
        return {'version':VERSION,'current':current,'offered':bundle.get('receipt',{}).get('methods',[]),
            'model_calls':calls,'model_dispatched':any(r['status'] in {'DISPATCHING','UNKNOWN','SUCCEEDED','REJECTED','INVALID'} for r in calls),
            'observation':bundle.get('observation'),'inherited_from':bundle.get('parent_goal'),'advisory_only':True,'execution_authorized':False,
            'automatic_promotion':False,'independent_successes':None,'causal_contribution':None}
