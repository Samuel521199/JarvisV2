"""Pure policy for evidence-bound exterior-art changes and conservative adoption.

No model code, paths or unbounded scene replacement is accepted. This closes a
limited parameterized recipe loop, not arbitrary Blender artistic autonomy.
"""
import copy
import hashlib
import json
from modules.skills.studio3d.artillery_recipe import PARAMETERS, VARIANTS, parameters, describe
from modules.skills.studio3d.hard_surface_review import VIEWS, review_gate

VERSION='1.3.0'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def decode(raw):
    raw=raw.strip()
    if raw.startswith('```'):raw=raw.split('\n',1)[1].rsplit('```',1)[0].strip()
    return json.loads(raw)


def validate_patch(value, current, reviews, source_digest):
    """Require actual reviewer evidence, semantic ownership and small deltas."""
    if not isinstance(value,dict) or set(value)!={'source_digest','changes','unresolved'}:raise ValueError('Invalid patch envelope')
    if value['source_digest']!=source_digest:raise ValueError('Stale patch source')
    if not isinstance(value['changes'],list) or len(value['changes'])>4:raise ValueError('At most four parameter edits per candidate')
    if not isinstance(value['unresolved'],list) or len(value['unresolved'])>12 or any(not isinstance(s,str) or len(s)>600 for s in value['unresolved']):raise ValueError('Invalid unresolved list')
    current=parameters(current);after=parameters(current);seen=set();by_view={r['view']:r for r in reviews};actions=[]
    for row in value['changes']:
        if not isinstance(row,dict) or set(row)!={'parameter','value','group','evidence','reason'}:raise ValueError('Invalid semantic operation')
        k=row['parameter']
        if not isinstance(k,str) or k not in PARAMETERS or k in seen:raise ValueError('Unknown or duplicate parameter')
        seen.add(k);spec=PARAMETERS[k]
        if row['group']!=spec[3]:raise ValueError('Operation targets the wrong semantic group')
        if not isinstance(row['reason'],str) or not 1<=len(row['reason'])<=600:raise ValueError('Missing bounded reason')
        e=row['evidence']
        if not isinstance(e,list) or not 1<=len(e)<=5:raise ValueError('Missing observed evidence')
        for item in e:
            if not isinstance(item,dict) or set(item)!={'view','correction'}:raise ValueError('Invalid evidence link')
            review=by_view.get(item['view']);idx=item['correction']
            if not review or type(idx) is not int or not 0<=idx<len(review['corrections']):raise ValueError('Evidence does not exist')
            finding=review['corrections'][idx]
            if finding['confidence']=='low':raise ValueError('Low-confidence observation cannot trigger geometry edits')
            if spec[3]=='lighting' and finding['kind']!='lighting':raise ValueError('Exposure needs lighting evidence')
            if spec[3]=='finish' and finding['kind']!='material':raise ValueError('Material edit needs material evidence')
            if spec[3] not in ('finish','lighting') and finding['kind']!='geometry':raise ValueError('Geometry edit needs geometry evidence')
        after[k]=row['value'];parameters(after)
        delta=abs(after[k]-current[k]);max_step=(spec[2]-spec[1])*.30
        if k=='wheel_ribs':max_step=2
        if k in VARIANTS:max_step=spec[2]-spec[1]
        if delta<=1e-8 or delta>max_step+1e-8:raise ValueError('No-op or excessive parameter change: '+k)
        actions.append({**row,'before':current[k],'tool':'set_exterior_parameter'})
    # Treat new arrays as data and never mutate the accepted source.
    return after,actions


def severity(reviews):
    out={}
    for r in reviews:
        counts={k:sum(c['severity']==k for c in r['corrections']) for k in ('high','medium','low')}
        out[r['view']]={**counts,'uncertain':r['verdict']=='uncertain','score':counts['high']*10+counts['medium']*3+counts['low']}
    return out


def adoption(before,after):
    a=severity(before);b=severity(after)
    if set(a)!=set(VIEWS) or set(b)!=set(VIEWS):return {'accepted':False,'reason':'incomplete_five_view_review'}
    if any(b[v]['uncertain'] for v in VIEWS):return {'accepted':False,'reason':'uncertain_review'}
    if any(b[v]['high']>a[v]['high'] for v in VIEWS):return {'accepted':False,'reason':'new_high_severity_regression'}
    prior=sum(x['score'] for x in a.values());new=sum(x['score'] for x in b.values())
    if new>=prior:return {'accepted':False,'reason':'no_observed_improvement','before_score':prior,'after_score':new}
    return {'accepted':True,'reason':'model_review_improvement_without_new_high_severity','before_score':prior,'after_score':new,
            'metric_scope':'ordinal reviewer findings, NOT percentage image similarity','user_approval':False,'lod_authorized':False}


def repair_focus(iterations,reviews):
    """Avoid indefinitely starving surface work after several retained shape edits.

    A major shape error still wins. Rejected edits do not count as progress.
    This is a workflow scheduling rule, not a quality score or learned fact.
    """
    findings=[c for r in reviews for c in r['corrections']]
    if any(c['kind']=='geometry' and c['severity']=='high' for c in findings):return None
    if not any(c['kind']=='material' and c['confidence']!='low' for c in findings):return None
    count=0
    for it in reversed(iterations):
        if not it.get('adoption',{}).get('accepted'):continue
        groups={a['group'] for a in it.get('proposed_actions',[])}
        if 'finish' in groups:break
        if groups-{'lighting'}:count+=1
    return 'finish' if count>=3 else None


def patch_prompt(current, reviews, source_digest, policy, failures=None,focus=None):
    current=parameters(current)
    compact=[]
    for r in reviews:
        ordered=sorted(enumerate(r['corrections']),key=lambda item:({'high':0,'medium':1,'low':2}[item[1]['severity']],item[0]))
        # Material findings must not be permanently starved by a geometry-only
        # first-three truncation. Keep highest-priority observations of both.
        chosen=ordered[:2]
        for item in ordered:
            if item[1]['kind']=='material' and item not in chosen:chosen.append(item);break
        for item in ordered:
            if len(chosen)>=3:break
            if item not in chosen:chosen.append(item)
        compact.append({'view':r['view'],'verdict':r['verdict'],'corrections':[{'index':i,**c} for i,c in chosen],'omitted_findings':max(0,len(ordered)-len(chosen)),
                        'camera_caveat':r.get('camera_caveat'),'reference_conflicts':r.get('reference_conflicts')})
    guide={k:[current[k],v[1],v[2],v[3],v[4]] for k,v in PARAMETERS.items()}
    text='''You are Jarvis's exterior game-art repair planner. Propose at most FOUR bounded parameter changes from actual five-view review evidence. No Python, paths, new objects or hidden mechanical inventions. Do not change geometry to imitate perspective, shadows or contradictions between generated references. Prefer an empty changes list with unresolved limitations over false repairs. Each change must cite a non-low-confidence correction of the matching geometry/material/lighting kind. Preserve explicit reference conflict policy. Max step is 30% of parameter range; wheel_ribs max step 2. Integer variants select tested topology recipes rather than scalar dimensions. Integer fields stay integers. Return strict JSON:
{"source_digest":"HASH","changes":[{"parameter":"name","value":0,"group":"semantic group","evidence":[{"view":"left","correction":0}],"reason":"observable justification"}],"unresolved":["cannot resolve using these tools"]}
Do not claim acceptance or learning. A fresh five-view render/review will decide whether to retain this candidate.
'''
    text+='PARAMETERS values are [current,min,max,group,meaning]. Integer variants select any registered integer option in range, not interpolated geometry; scalar 30% limits remain. An established curved_double shield policy permits continuous shape refinement; old reviewer notes saying unspecified are superseded.\n'
    if focus=='finish':text+='CURRENT_WORKFLOW_FOCUS: finish only. Several shape edits were retained while surface mismatches remain. Propose only finish-group actions supported by material evidence, or empty changes if unsupported. Geometry is frozen for this trial. Avoid previously rejected grain/spot regressions.\n'
    if failures:
        bounded=[]
        for f in failures[-2:]:
            comparisons=sorted(f.get('comparisons',[]),key=lambda r:r['change']!='worse')[:2]
            bounded.append({'iteration':f['iteration'],'changes':f['changes'],'reason':str(f['reason'])[:80],
                'comparisons':[{'view':r['view'],'change':r['change'],'regression':str(r.get('regressions',[])[:1])[:90],'improvement':str(r.get('improvements',[])[:1])[:90]} for r in comparisons]})
        text+='A previous patch was rejected. Isolate ONE supported improvement or choose a different repair, rather than repeating the rejected combination. Favor changes supported across views. Feedback is not ground truth.\nREJECTED_PATCHES:'+json.dumps(bounded,ensure_ascii=False,separators=(',',':'))+'\n'
    text+='SOURCE_DIGEST:'+source_digest+'\nPARAMETERS:'+json.dumps(guide,ensure_ascii=False,separators=(',',':'))+'\nPOLICY:'+json.dumps(policy,ensure_ascii=False,separators=(',',':'))+'\nREVIEWS:'+json.dumps(compact,ensure_ascii=False,separators=(',',':'))
    if len(text)>12000:
        # Keep evidence index/kind/confidence and concise observations; no silent loss of views.
        for r in compact:
            r['camera_caveat']=str(r['camera_caveat'])[:60]
            r['reference_conflicts']=str(r['reference_conflicts'])[:60]
            for c in r['corrections']:
                c.pop('format_repair',None)
                for k in ('feature','visible_evidence','action'):c[k]=c[k][:45]
        text=text[:text.index('\nREVIEWS:')]+'\nREVIEWS:'+json.dumps(compact,ensure_ascii=False,separators=(',',':'))
    if len(text)>12000:raise ValueError('Planner context exceeds host budget')
    return text


def candidate_lesson(source, candidate, actions, outcome):
    return {'schema':'jarvis.studio3d.art-episode.v1','source':source,'candidate':candidate,'actions':copy.deepcopy(actions),'outcome':outcome,
            'lifecycle':'CANDIDATE','scope':'This recipe and this asset only; visual-model assessment',
            'automatic_promotion':False,'eligible_for_global_retrieval':False,
            'required_before_promotion':['independent reference task','verified cause','regression checks','reviewed applicability and counterexamples'],
            'user_approval':False,'lod_authorized':False}
