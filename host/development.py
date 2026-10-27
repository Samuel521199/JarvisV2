"""Owner-operated development submissions, frozen routes, review and background execution."""
from host.background import BackgroundLane
import time

from host.core import Core
from adapters.storage.sqlite import Database
from control.paths import child
from control.recovery.gate import RunLock
from modules.preferences.store import resolve
from sdk.protocol import CoreError, canonical, contract, decode, digest


def list_runs(root):
    db = Database(child(root, 'state/core.sqlite3'))
    try:
        rows = db.all('SELECT id,status,phase,attempt,task_id,release_id,error,spec FROM development_runs ORDER BY created DESC LIMIT 40')
        for row in rows: row['goal'] = decode(row.pop('spec'))['goal']
        return rows
    finally: db.close()


def resolve_routes(core, routes):
    if not isinstance(routes, dict) or set(routes) != {'plan', 'code'}: raise CoreError('development_invalid', 'Select plan and code routes')
    config = core.preferences.read()
    if not config: raise CoreError('settings_missing', 'Configure models first')
    resolved = {}
    for phase, items in routes.items():
        if not isinstance(items, list) or not 1 <= len(items) <= 2: raise CoreError('development_invalid', 'Choose primary and optional backup')
        resolved[phase] = []
        for item in items:
            if not isinstance(item, dict) or set(item) != {'provider', 'model', 'reasoning'}: raise CoreError('development_invalid', 'Invalid route')
            if item['provider']=='codex-cli':
                if phase!='code':raise CoreError('development_invalid','Codex is a candidate coder, not a planning route')
                if not config.get('coding',{}).get('enabled'):raise CoreError('development_invalid','Codex coding preference is disabled')
                from adapters.models.codex_cli import route
                resolved[phase].append(route(item['model'],item['reasoning']));continue
            resolved[phase].append(resolve(config['catalog'], **item))
        if len({digest(r) for r in resolved[phase]}) != len(resolved[phase]): raise CoreError('development_invalid', 'Duplicate route')
    return resolved


def admit(core, spec, resolved, tx):
    core.grants.add({'schema':'jarvis.grant.v1','grant_id':spec['grant_id'],'principal_id':'owner.local','scope_id':'personal',
                     'capabilities':['model.generate.v1','development.build.v1','release.activate.v1','artifact.write.v1',spec['capability']],
                     'max_cost_units':spec['limits']['max_model_calls']+spec['limits']['max_attempts']+4,
                     'expires_at':time.time()+spec['limits']['max_seconds']},transaction=tx)
    ident=core.development.submit(spec,transaction=tx)
    tx.execute('INSERT INTO development_controls VALUES(?,?,NULL,?)',(ident,canonical(resolved),time.time()))
    return ident


def command(root, value):
    fields = {'create': {'spec', 'routes'}, 'detail': {'id'}, 'approve': {'id', 'package_id'}, 'revoke': {'id'}, 'retry_rejected': {'id'}}
    if not isinstance(value, dict) or not isinstance(value.get('action'), str) or value.get('action') not in fields or set(value) != {'action'} | fields[value['action']]:
        raise CoreError('development_invalid', 'Invalid development command')
    core = Core(root)
    try:
        action = value['action']
        if action == 'create':
            spec = value['spec']; routes = value['routes']
            if not isinstance(spec, dict): raise CoreError('development_invalid', 'Expected development specification')
            # API never accepts a broad grant supplied by model text or a request to edit the host.
            spec = {**spec, 'grant_id': 'workbench-' + digest(spec)[:32]}
            contract('development', spec)
            if spec['principal_id'] != 'owner.local' or spec['scope_id'] != 'personal': raise CoreError('development_invalid', 'Only local owner pure tools are supported')
            resolved = resolve_routes(core, routes)
            with RunLock(core.root, 'development'):
                core.gate.require_running()
                old = core.db.one('SELECT id,digest FROM development_runs WHERE request_id=?', (spec['request_id'],))
                if old:
                    control = core.db.one('SELECT routes FROM development_controls WHERE run_id=?', (old['id'],))
                    if old['digest'] != digest(spec) or not control or decode(control['routes']) != resolved: raise CoreError('conflict', 'Submission changed')
                    return {'id': old['id'], 'existing': True}
                with core.db.transaction() as tx:
                    ident=admit(core,spec,resolved,tx)
                return {'id': ident, 'existing': False}
        ident = value['id']; row = core.development.get(ident)
        control = core.db.one('SELECT * FROM development_controls WHERE run_id=?', (ident,))
        parent=core.db.one('SELECT goal_id FROM goal_growth WHERE development_id=?',(ident,))
        if action == 'detail':
            routes = decode(control['routes']) if control else None
            if routes:
                routes = {phase: [{k: r[k] for k in ('id', 'model', 'parameters')} for r in items] for phase, items in routes.items()}
            grant = core.db.one('SELECT spent,revoked,body FROM grants WHERE id=?', (row['spec']['grant_id'],))
            if grant: grant['body'] = decode(grant['body'])
            return {'parent_goal':parent['goal_id'] if parent else None, 'run': row, 'routes': routes, 'approved_package': control['approved_package'] if control else None, 'grant': grant,
                    'calls':core.db.all('SELECT phase,status,error,model,usage FROM model_calls WHERE run_id=? ORDER BY created',(ident,)),
                    'package': core.packages.get(row['release_id']) if row['release_id'] else None,
                    'task': core.tasks.get(row['task_id']) if row['task_id'] else None,
                    'actions': core.tasks.actions(row['task_id']) if row['task_id'] else []}
        if not control: raise CoreError('development_invalid', 'This run is managed by the CLI')
        if action == 'revoke':
            core.grants.revoke(row['spec']['grant_id']); core.development.cancel(ident)
            return {'revoked': True}
        if action == 'retry_rejected':
            with RunLock(core.root,'development'),core.db.transaction() as tx:
                core.gate.require_running();row=core.development.get(ident)
                if row['status']!='WAITING' or row['error']!='model_unavailable' or row['cancel']:raise CoreError('invalid_state','No known rejected route to retry')
                if row['deadline']<=time.time():raise CoreError('deadline','Development budget expired')
                from control.policy.grants import GrantStore
                GrantStore.authorize(tx,{'grant_id':row['spec']['grant_id'],'principal_id':'owner.local','scope_id':'personal'},'model.generate.v1')
                count=tx.execute("UPDATE model_calls SET status='ACKNOWLEDGED' WHERE run_id=? AND status='REJECTED'",(ident,)).rowcount
                if not count:raise CoreError('invalid_state','No rejected model call')
                core.db.event(tx,None,'model.rejected_retry_accepted',{'run_id':ident,'calls':count})
            return {'id':ident,'acknowledged':count}
        with RunLock(core.root, 'development'):
            core.gate.require_running(); row = core.development.get(ident)
            if row['release_id'] != value['package_id'] or row['phase'] != 'verified' or row['cancel'] or row['status'] != 'WAITING':
                raise CoreError('conflict', 'Candidate or state changed')
            package = core.packages.get(row['release_id'])
            if package['status'] != 'VERIFIED': raise CoreError('review_required', 'Candidate has not passed verification')
            core.development.checkpoint(ident, 'release.activate.v1')
            with core.db.transaction() as tx:
                tx.execute('UPDATE development_controls SET approved_package=? WHERE run_id=?', (row['release_id'], ident))
                core.db.event(tx, None, 'development.reviewed', {'run_id': ident, 'package_id': row['release_id']})
            return {'approved_package': row['release_id']}
    finally: core.close()


class DevelopmentRunner:
    def __init__(self, root, lane=None):
        self.root=root;self.owns_lane=lane is None;self.lane=lane or BackgroundLane()

    def state(self): return self.lane.state()

    def start(self, value):
        if not isinstance(value, dict) or set(value) != {'id', 'network_enabled', 'retry_unknown'} or not isinstance(value['id'], str) or any(type(value[k]) is not bool for k in ('network_enabled', 'retry_unknown')):
            raise CoreError('development_invalid', 'Invalid run options')
        core=Core(self.root)
        try:core.development.get(value['id']);core.gate.require_running()
        finally:core.close()
        return self.lane.submit('development',value['id'],self._run,value)

    def _run(self, value):
        core=Core(self.root)
        try:result=core.develop(value['id'],value['network_enabled'],value['retry_unknown'])
        finally:core.close()
        if result['status']=='SUCCEEDED':
            from host.goal_growth import after_development
            after_development(self.root,value['id'])
        return result

    def close(self):
        if self.owns_lane:self.lane.close()
