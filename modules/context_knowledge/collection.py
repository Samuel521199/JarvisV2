"""A project (or personal root) plus its isolated memory domains in one transaction."""
import re
import time
from modules.context_knowledge.bundle import Bundle, validate
from modules.context_knowledge.domains import Domains
from modules.context_knowledge.transfer import MAX_TRANSFER_BYTES
from sdk.protocol import CoreError,canonical,digest

FORMAT='jarvis.memory-collection.v2'


def checked(value):
    try:
        modern=value['format']==FORMAT
        if set(value)!=({'format','root','domains','snapshots','bundles','checksum'}|({'source_branches'} if modern else set())) or value['format'] not in {FORMAT,'jarvis.memory-collection.v1'}:raise ValueError()
        if not isinstance(value['domains'],list) or len(value['domains'])>100 or not isinstance(value['bundles'],list) or len(value['bundles'])>101:raise ValueError()
        ids={value['root']}
        for d in value['domains']:
            if set(d)!={'id','parent','kind','name','revision','archived','created'} or d['id'] in ids or not re.fullmatch('domain-[a-f0-9]{32}',d['id']):raise ValueError()
            if d['parent']!=value['root'] or d['kind'] not in {'branch','task','world'} or not isinstance(d['name'],str) or not 1<=len(d['name'])<=80:raise ValueError()
            if type(d['revision']) is not int or d['revision']<1 or d['archived'] not in (0,1) or type(d['created']) not in (int,float):raise ValueError()
            ids.add(d['id'])
        scopes=set();objects=set();source_objects={};fact_objects={}
        for b in value['bundles']:
            validate(b);scope=b['sources']['scope']
            if scope not in ids or scope in scopes:raise ValueError()
            scopes.add(scope)
            for r in b['facts']+b['sources']['sources']+b['sources']['tombstones']:
                if r['id'] in objects:raise ValueError()
                objects.add(r['id'])
            if scope==value['root']:
                source_objects={r['id']:r for r in b['sources']['sources']+b['sources']['tombstones']}
                fact_objects={r['id']:r for r in b['facts']}
        if ids!=scopes or not isinstance(value['snapshots'],list) or len(value['snapshots'])>100000:raise ValueError()
        seen=set()
        for s in value['snapshots']:
            if set(s)!={'domain_id','kind','id','revision'} or s['domain_id'] not in ids-{value['root']} or s['kind'] not in {'source','fact'}:raise ValueError()
            if type(s['revision']) is not int or s['revision']<1 or (s['kind']=='source' and s['id'] not in source_objects) or (s['kind']=='fact' and s['id'] not in fact_objects):raise ValueError()
            k=(s['domain_id'],s['kind'],s['id'])
            if k in seen:raise ValueError()
            seen.add(k)
        lineages=value.get('source_branches',[])
        if not isinstance(lineages,list) or len(lineages)>200:raise ValueError()
        documents={r['id']:(b['sources']['scope'],r) for b in value['bundles'] for r in b['sources']['sources']+b['sources']['tombstones']}
        branches={d['id'] for d in value['domains'] if d['kind']=='branch'};seen=set();parents=set()
        for link in lineages:
            if set(link)!={'domain_id','source_id','parent_id','base_revision'} or link['domain_id'] not in branches:raise ValueError()
            local=documents.get(link['source_id']);parent=documents.get(link['parent_id'])
            if not local or local[0]!=link['domain_id'] or not parent or parent[0]!=value['root']:raise ValueError()
            if type(link['base_revision']) is not int or not 1<=link['base_revision']<=parent[1]['revision']:raise ValueError()
            if link['source_id'] in seen or (link['domain_id'],link['parent_id']) in parents:raise ValueError()
            seen.add(link['source_id']);parents.add((link['domain_id'],link['parent_id']))
        if value['checksum']!=digest({k:v for k,v in value.items() if k!='checksum'}):raise ValueError()
        if len(canonical(value).encode())>MAX_TRANSFER_BYTES-1000:raise ValueError()
        return value
    except (KeyError,TypeError,ValueError,RecursionError):raise CoreError('memory_bundle_invalid','Invalid memory collection') from None


class Collection:
    def __init__(self,db):self.db=db

    def export(self,root,origin=lambda scope,kind,row:None):
        # Each Bundle uses the existing transaction when snapshotting through export_snapshot.
        self.db.connection.execute('BEGIN')
        try:
            domains=Domains(self.db).list(root)
            scopes=[root]+[r['id'] for r in domains]
            bundles=[Bundle(self.db).snapshot(s,lambda k,r:origin(s,k,r)) for s in scopes]
            snapshots=self.db.all('SELECT s.* FROM memory_snapshots s JOIN memory_domains d ON d.id=s.domain_id WHERE d.parent=? ORDER BY s.domain_id,s.id',(root,))
            lineages=self.db.all('SELECT b.* FROM memory_source_branches b JOIN memory_domains d ON d.id=b.domain_id WHERE d.parent=? ORDER BY b.source_id',(root,))
            value={'format':FORMAT,'root':root,'domains':domains,'snapshots':snapshots,'bundles':bundles,'source_branches':lineages};value['checksum']=digest(value)
            return checked(value)
        finally:self.db.connection.execute('ROLLBACK')

    def plan(self,root,value):
        checked(value);manager=Bundle(self.db);plans=[];conflicts=[]
        for d in value['domains']:
            old=self.db.one('SELECT * FROM memory_domains WHERE id=?',(d['id'],))
            if old and (old['parent']!=root or old['kind']!=d['kind']):conflicts.append(d['id'])
            for s in (s for s in value['snapshots'] if s['domain_id']==d['id']):
                prior=self.db.one('SELECT revision FROM memory_snapshots WHERE domain_id=? AND kind=? AND id=?',(d['id'],s['kind'],s['id']))
                if prior and prior['revision']!=s['revision']:conflicts.append(d['id'])
        for b in value['bundles']:
            scope=root if b['sources']['scope']==value['root'] else b['sources']['scope']
            plans.append({'scope':scope,'plan':manager.plan(scope,b)})
        lineages=value.get('source_branches',[])
        for link in lineages:
            old=self.db.one('SELECT * FROM memory_source_branches WHERE source_id=? OR (domain_id=? AND parent_id=?)',(link['source_id'],link['domain_id'],link['parent_id']))
            if old and old!=link:conflicts.append(link['source_id'])
        total=self.db.one("SELECT count(*) AS n FROM knowledge_sources WHERE status!='deleted'")['n']
        total+=sum(p['plan']['sources']['counts']['create']-p['plan']['sources']['counts']['delete'] for p in plans)
        state=self.db.all('SELECT * FROM memory_domains ORDER BY id')
        return {'token':digest({'root':root,'checksum':value['checksum'],'plans':plans,'domains':state}),
                'can_apply':not conflicts and total<=200 and all(p['plan']['can_apply'] for p in plans),
                'plans':plans,'conflicts':conflicts,'new_domains':sum(not any(x['id']==d['id'] for x in state) for d in value['domains']),
                'source_root':value['root'],'target_root':root,'policy':'paused_without_destinations'}

    def preview(self,root,value):
        self.db.connection.execute('BEGIN')
        try:return self.plan(root,value)
        finally:self.db.connection.execute('ROLLBACK')

    def restore(self,root,value,token):
        checked(value)
        with self.db.transaction() as tx:
            plan=self.plan(root,value)
            if token!=plan['token']:raise CoreError('conflict','Memory collection changed')
            if not plan['can_apply']:raise CoreError('memory_restore_conflict','Memory collection conflicts')
            for d in value['domains']:
                # Imported domains stay archived until the owner explicitly restores them.
                tx.execute('INSERT OR IGNORE INTO memory_domains VALUES(?,?,?,?,?,1,?)',(d['id'],root,d['kind'],d['name'],d['revision'],d['created']))
            receipts=[]
            for b,p in zip(value['bundles'],plan['plans']):receipts.append(Bundle(self.db).apply(tx,p['scope'],b,p['plan']))
            for s in value['snapshots']:tx.execute('INSERT OR IGNORE INTO memory_snapshots VALUES(?,?,?,?)',(s['domain_id'],s['kind'],s['id'],s['revision']))
            from modules.context_knowledge.knowledge import Knowledge
            for link in value.get('source_branches',[]):
                tx.execute('INSERT OR IGNORE INTO memory_source_branches VALUES(?,?,?,?)',tuple(link[k] for k in ('domain_id','source_id','parent_id','base_revision')))
            # Current local tombstones win even if an older collection carries
            # a still-live derivative. Do this after all branches are restored.
            for r in self.db.all("SELECT s.* FROM memory_source_branches b JOIN knowledge_sources s ON s.id=b.source_id JOIN knowledge_sources p ON p.id=b.parent_id WHERE p.status='deleted' AND s.status!='deleted'"):
                Knowledge(self.db).delete_in(tx,r['scope'],r['id'],r['revision'])
            return {'receipts':receipts,'domains':len(value['domains']),'policy':plan['policy']}
