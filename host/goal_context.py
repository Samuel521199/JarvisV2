"""Goal-bound, revocable memory projections. No implicit cross-project promotion."""
import time

from host.memory import scope_for, LOCK
from host.memory_domains import chat_scope
from modules.context_knowledge.memory import Memory
from modules.context_knowledge.retrieval import VERSION as RETRIEVAL_VERSION
from modules.dialogue.store import Dialogues
from modules.task_resource.plans import Plans, planning_key
from sdk.protocol import CoreError, canonical, decode


def snapshot(core, scope, enabled, routes, query=''):
    scope_for(core.root,scope)
    if type(enabled) is not bool:raise CoreError('memory_invalid','Invalid memory switch')
    memory=Memory(core.db)
    views=[memory.view(scope,r['id'],enabled,query,selectors={'channel':'task'}) for r in routes]
    common=set.intersection(*[{(f['id'],f['revision']) for f in v['facts']} for v in views]) if views else set()
    facts=[f for f in views[0]['facts'] if (f['id'],f['revision']) in common] if views else []
    return {'facts':facts,'providers':[r['id'] for r in routes],'selectors':{'channel':'task'},
            'dependencies':[{'id':f['id'],'revision':f['revision']} for f in facts],
            'retrieval':{'mode':'lexical','version':RETRIEVAL_VERSION,'semantic':'transaction_lexical'}}


def bind(core, ident, context, tx):
    if not isinstance(context,dict) or set(context)!={'scope','enabled','chat_id','turn_id'}:
        raise CoreError('plan_invalid','Invalid goal context')
    row=Plans(core.db).get(ident)
    scope=context['scope'];enabled=context['enabled'];upstream_refs=[]
    if context['chat_id'] or context['turn_id']:
        chats=Dialogues(core.root)
        try:
            chat=chats.read(context['chat_id']);turn=chats.turn(context['turn_id'])
            action=decode(turn['assistant_action']) if turn['assistant_action'] else {}
            if (chat['archived'] or chat['removed'] or turn['chat_id']!=chat['id'] or turn['status']!='SUCCEEDED'
                or turn['cancel'] or action.get('kind')!='goal' or action.get('goal')!=row['request']['goal']
                or action.get('input_text')!=row['request']['input_text'] or scope!=chat_scope(core.root,chat)
                or enabled!=decode(turn['request']).get('memory_enabled',True)
                or any(r['id']!=turn['provider'] or r['model']!=turn['model'] for r in row['routes'])):
                raise CoreError('plan_source_changed','Chat source no longer matches this goal')
        finally:chats.close()
        upstream=decode(turn['memory_context']) if turn['memory_context'] else {}
        upstream_refs=upstream.get('dependencies',upstream.get('facts',[]))
        if not Memory(core.db).references_valid(scope,turn['provider'],enabled,upstream_refs,{'channel':'task'}):
            raise CoreError('goal_context_changed','Chat used a withdrawn or corrected memory; send an updated request')
        tx.execute('INSERT INTO chat_goals VALUES(?,?,?)',(context['turn_id'],context['chat_id'],ident))
    view=snapshot(core,scope,enabled,row['routes'],row['request']['goal']+' '+row['request']['input_text'])
    deps={(f['id'],f['revision']) for f in view['dependencies']+upstream_refs}
    view['dependencies']=[{'id':i,'revision':r} for i,r in sorted(deps)]
    tx.execute('INSERT INTO goal_context(goal_id,scope,enabled,view) VALUES(?,?,?,?)',(ident,scope,int(enabled),canonical(view)))


def get(core, ident):
    row=core.db.one('SELECT * FROM goal_context WHERE goal_id=?',(ident,))
    if row:
        row['view']=decode(row['view']);row['history']=decode(row['history'])
    return row


def check(core, ident, destinations=None):
    row=get(core,ident)
    if not row:return []
    if row['view'].get('redacted'):raise CoreError('goal_context_changed','Background was cleared; refresh and review the goal')
    scope_for(core.root,row['scope']);memory=Memory(core.db)
    expected=row['view'].get('dependencies',row['view']['facts'])
    for provider in destinations or row['view']['providers']:
        if not memory.references_valid(row['scope'],provider,bool(row['enabled']),expected,row['view'].get('selectors')):raise CoreError('goal_context_changed','Goal memory changed or destination is not permitted; review a refreshed plan')
    link=core.db.one('SELECT chat_id FROM chat_goals WHERE goal_id=?',(ident,))
    if link:
        chats=Dialogues(core.root)
        try:
            chat=chats.read(link['chat_id'])
            if chat['removed'] or chat['archived']:raise CoreError('plan_source_changed','Restore the source chat first')
        finally:chats.close()
    return row['view']['facts']


def amend(core, ident, revision, goal, text, operation=None):
    if type(revision) is not int or not isinstance(goal,str) or not 1<=len(goal.strip())<=4000 or not isinstance(text,str) or len(text)>12000:
        raise CoreError('plan_invalid','Invalid amended goal')
    with LOCK,core.db.transaction() as tx:
        core.gate.require_running()
        link=core.works.link(ident)
        if link and link['parent_goal']:
            raise CoreError('rework_invalid','Use the linked revision editor; automatic replanning cannot replace pinned input')
        p=Plans(core.db).get(ident);ctx=get(core,ident)
        growth=tx.execute('SELECT status FROM goal_growth WHERE goal_id=?',(ident,)).fetchone()
        if (p['revision']!=revision or p['cancel'] or p['task_id'] or p['status'] not in {'NEW','WAITING','REVIEW','NEEDS_INPUT'}
            or growth and growth['status']!='REJOINED'):
            raise CoreError('conflict','Cannot rewrite running or admitted work; review a separate follow-up goal')
        if p['generation']>=3:raise CoreError('plan_revision_limit','This goal has reached its explicit replan limit')
        view=snapshot(core,ctx['scope'] if ctx else 'personal',bool(ctx['enabled']) if ctx else False,p['routes'],goal+' '+text)
        history=(ctx['history'] if ctx else [])+[{'request':p['request'],'proposal':p['proposal'],'generation':p['generation']}]
        request={**p['request'],'goal':goal,'input_text':text};deadline=time.time()+600
        from host.capabilities import catalog as available_catalog
        catalog=available_catalog(core,ctx['scope'] if ctx else 'personal')
        core.grants.revoke(planning_key(p)+'-plan',transaction=tx)
        tx.execute("UPDATE goal_plans SET request=?,catalog=?,proposal=NULL,generation=generation+1,revision=revision+1,status='NEW',error=NULL,deadline=? WHERE id=?",
                   (canonical(request),canonical(catalog),deadline,ident))
        key=planning_key(Plans(core.db).get(ident))
        core.grants.add({'schema':'jarvis.grant.v1','grant_id':key+'-plan','principal_id':'owner.local','scope_id':'personal',
                         'capabilities':['model.generate.v1'],'max_cost_units':2,'expires_at':deadline},transaction=tx)
        tx.execute('INSERT INTO goal_context VALUES(?,?,?,?,?) ON CONFLICT(goal_id) DO UPDATE SET view=excluded.view,history=excluded.history',
                   (ident,ctx['scope'] if ctx else 'personal',ctx['enabled'] if ctx else 0,canonical(view),canonical(history)))
        core.db.event(tx,None,'goal.amended',{'goal_id':ident,'generation':p['generation']+1})
        if operation:tx.execute('INSERT INTO assistant_operations VALUES(?,?,?,?)',(operation,ident,'amend',canonical({'id':ident,'generation':p['generation']+1})))
    return {'id':ident,'generation':p['generation']+1}
