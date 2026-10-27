"""Optional observer integration; source policy stays with the existing Host."""
from sdk.protocol import CoreError


def service(core):
    from modules.evaluation.outcomes import Outcomes
    def source_check(ident):
        from host.goal_context import check
        try:
            check(core, ident)
            from host.work_revisions import check as check_work
            check_work(core, ident)
            row = core.db.one('SELECT cancel FROM goal_plans WHERE id=?', (ident,))
            return 'invalid' if not row or row['cancel'] else 'current'
        except CoreError as exc:
            if exc.code in {'goal_context_changed','plan_source_changed','chat_archived','chat_removed','memory_scope','rework_source_changed'}:
                return 'invalid'
            return 'unknown'
    def task_check(ident):
        from host.completion import check_use
        try:check_use(core,ident);return 'current'
        except CoreError as exc:
            return 'invalid' if exc.code=='experience_changed' else 'unknown'
    return Outcomes(core.db, core.root, source_check, task_check)


def observe(core, task_id=None, limit=32, cached=False):
    try:
        observer = service(core)
        if cached and task_id: return observer.cached(task_id)
        return observer.refresh(task_id,transaction=core.db.connection if core.db.connection.in_transaction else None) if task_id else observer.consume(limit)
    except Exception:
        # This path is optional Reflection; it never masks a task error or outcome.
        return {'state': 'UNAVAILABLE', 'score': None, 'error': 'outcome_observer_unavailable'}


def status(core):
    try:
        observer = service(core)
        cursor = core.db.one('SELECT last_seq FROM outcome_consumers')['last_seq']
        return {'enabled':observer.enabled(), 'last_seq':cursor,
                'lag_events':max(0,core.db.one('SELECT COALESCE(MAX(seq),0) AS n FROM events')['n']-cursor),
                'failed_tasks':core.db.one('SELECT COUNT(*) AS n FROM outcome_failures')['n']}
    except Exception:
        return {'enabled':None, 'error':'outcome_observer_unavailable'}
