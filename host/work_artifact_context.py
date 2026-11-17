"""Model-library affiliation from exact recorded digests, never name matching."""
import json,re,sqlite3
from pathlib import Path
from control.paths import child,reject_links

SHA=re.compile('[a-f0-9]{64}')


def model_links(root):
    location=child(root,'model-library/location.json')
    folder=Path(json.loads(location.read_text(encoding='utf-8'))['repository']).resolve() if location.exists() else child(root,'model-library')
    catalog=folder/'catalog.sqlite3';jobs=child(root,'state/studio3d.sqlite3')
    if not catalog.exists() or not jobs.exists():return {}
    reject_links(catalog);reject_links(jobs)
    db=sqlite3.connect(catalog.as_uri()+'?mode=ro',uri=True,timeout=.1)
    try:
        assets={ident:json.loads(body).get('name',ident) for ident,body in db.execute('SELECT id,body FROM assets')}
        anchors={}
        for ident,sha in db.execute("SELECT asset_id,sha256 FROM files WHERE ext IN ('.blend','.glb','.vrm')"):
            if isinstance(sha,str) and SHA.fullmatch(sha):anchors.setdefault(sha,set()).add(ident)
    finally:db.close()
    db=sqlite3.connect(jobs.as_uri()+'?mode=ro',uri=True,timeout=.1)
    try:rows=db.execute("SELECT id,json_extract(receipt,'$.input_asset.sha256'),json_extract(receipt,'$.files') FROM jobs ORDER BY created DESC LIMIT 200").fetchall()
    finally:db.close()
    graph={};nodes={}
    for ident,source,raw in rows:
        files=json.loads(raw) if raw else {};values={source} if isinstance(source,str) and SHA.fullmatch(source) else set()
        for name,value in files.items():
            sha=value.get('sha256') if isinstance(value,dict) else None
            if name.endswith(('.blend','.glb','.vrm')) and isinstance(sha,str) and SHA.fullmatch(sha):values.add(sha)
        nodes[ident]=values
        for sha in values:graph.setdefault(sha,set()).update(values-{sha})
    seen=set();affiliations={}
    for start in graph:
        if start in seen:continue
        component=set();pending=[start]
        while pending:
            sha=pending.pop()
            if sha in component:continue
            component.add(sha);pending.extend(graph[sha]-component)
        seen.update(component);owners=set().union(*(anchors.get(sha,set()) for sha in component))
        # Shared components between different library assets are ambiguous.
        if len(owners)==1:
            ident=next(iter(owners))
            for sha in component:affiliations[sha]=(ident,assets.get(ident,ident))
    result={}
    for ident,values in nodes.items():
        candidates={affiliations[sha] for sha in values if sha in affiliations}
        if len(candidates)==1:result[ident]=next(iter(candidates))
    return result
