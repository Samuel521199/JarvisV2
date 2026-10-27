"""One explicit image comparison, one revision, one final visual review."""
import base64,hashlib,time
from control.paths import child
from modules.dialogue.store import Dialogues
from modules.skills.studio3d.refinement import prompt,parse
from sdk.protocol import CoreError,canonical

def assess(root,body,dialogues,receipt,final=False):
    from host.studio3d import check,update
    from host.studio3d_reference import record,upload
    ident=body['id'];check(root,ident)
    raw=child(root,'artifacts/studio3d/'+receipt['id']+'/preview.png').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=receipt['files']['preview.png']['sha256']:raise CoreError('studio3d_changed','Review render changed')
    # Render and reference are resolved by host-owned IDs, never model paths.
    ref=record(root,body['reference'])[0]
    rendered=upload(root,{'name':'render-'+receipt['id']+'.png','source':'Jarvis delivered render '+receipt['id'],'license':'First-party procedural render; task visual review','data':base64.b64encode(raw).decode('ascii')})
    message=prompt(receipt['configuration'],body.get('focus',''),final,receipt.get('refinement',{}).get('after',{}).get('assessment'))
    store=Dialogues(root);turn='studio3d-'+ident+('-verify' if final else '-compare')
    try:
        chat=store.create();store.update(chat,{'title':'3D 对照'+('复核' if final else '修正')+' · '+receipt['title'][:40]})
        update(root,ident,status='PLANNING',phase='对照新渲染复核' if final else '对照参考图分析差距',chat_id=chat,turn_id=turn)
        dialogues.submit_background({'chat_id':chat,'request_id':turn,'text':message,'provider':body['provider'],'model':body['model'],'reasoning':'default','skill':'none','memory_enabled':False,'reference_images':[ref['id'],rendered['id']]})
        deadline=time.monotonic()+160
        while True:
            check(root,ident);row=store.turn(turn)
            if row['status'] not in ('READY','RUNNING'):break
            if time.monotonic()>deadline:raise CoreError('model_unknown','Review deadline reached; no replay')
            time.sleep(.25)
        if row['status']!='SUCCEEDED':raise CoreError('model_unknown' if row['status']=='UNKNOWN' else 'studio3d_model_failed','Visual review did not succeed')
        assessment=parse(row['reply'],final,[o['id'] for o in receipt['configuration']['objects']])
        return {'chat_id':chat,'turn_id':turn,'provider':body['provider'],'model':body['model'],'reference_sha256':ref['sha256'],'render_sha256':rendered['sha256'],'render_job':receipt['id'],'assessment':assessment,'model_based':True,'AAA_certified':False}
    finally:
        try:store.cancel(turn)
        except CoreError:pass
        store.close()

def begin(root,body,dialogues):
    from host.studio3d import state
    from host.studio3d_reference import record
    from sdk.protocol import decode
    prior=state(root,body['refine'])['receipt']
    if body.get('reuse_review'):
        failed=state(root,body['reuse_review']);store=Dialogues(root)
        try:
            if failed['status'] not in ('FAILED','UNKNOWN') or not failed['turn_id'] or not failed['turn_id'].endswith('-compare'):raise CoreError('studio3d_invalid','Only completed comparison candidates may be reused')
            turn=store.turn(failed['turn_id']);request=decode(turn['request']);ids=request.get('reference_images',[])
            if turn['status']!='SUCCEEDED' or len(ids)!=2 or any(request.get(k)!=body[k] for k in ('provider','model')):raise CoreError('studio3d_invalid','Review provenance mismatch')
            ref=record(root,ids[0])[0];rendered=record(root,ids[1])[0]
            if ref['sha256']!=record(root,body['reference'])[0]['sha256'] or rendered['sha256']!=prior['files']['preview.png']['sha256']:raise CoreError('studio3d_changed','Review inputs differ')
            review={'chat_id':failed['chat_id'],'turn_id':failed['turn_id'],'provider':body['provider'],'model':body['model'],'reference_sha256':ref['sha256'],'render_sha256':rendered['sha256'],'render_job':prior['id'],'assessment':parse(turn['reply'],parts=[o['id'] for o in prior['configuration']['objects']]),'model_based':True,'AAA_certified':False,'reused_from':failed['id']}
        finally:store.close()
    else:review=assess(root,body,dialogues,prior)
    folder=child(root,'artifacts/studio3d-reviews');folder.mkdir(exist_ok=True,parents=True)
    (folder/(body['id']+'.json')).write_text(canonical({'source_job':body['refine'],'before':review,'after':None}),encoding='utf-8')
    scene=review['assessment']['scene'];scene['reference']=body['reference']
    if 'surface_texture' in prior['configuration']:
        from modules.skills.studio3d.contract import validate
        scene['surface_texture']=prior['configuration']['surface_texture'];scene=validate(scene)
    model_receipt={k:review[k] for k in ('chat_id','turn_id','provider','model','reference_sha256')}
    model_receipt.update(status='SUCCEEDED',visual_review=True,reference_image_sent=True,render_image_sent=True,source_job=body['refine'])
    return scene,model_receipt,review

def finish(root,body,dialogues,receipt,before):
    from host.studio3d import update
    after=assess(root,body,dialogues,receipt,True)
    result={'source_job':body['refine'],'revision_limit':1,'model_calls':1 if 'reused_from' in before else 2,'before':before,'after':after,'acceptance':'model visual opinion; not independent AAA certification'}
    # Avoid storing another full scene in the visual report; it is in scene.json
    # and the original model turn. Record only the exact proposed-scene hash.
    result['before']['candidate_sha256']=hashlib.sha256(canonical(before['assessment']['scene']).encode()).hexdigest()
    result['before']['assessment']={k:v for k,v in before['assessment'].items() if k!='scene'}
    raw=canonical(result).encode();folder=child(root,'artifacts/studio3d/'+body['id']);(folder/'review.json').write_bytes(raw)
    child(root,'artifacts/studio3d-reviews/'+body['id']+'.json').write_bytes(raw)
    receipt['files']['review.json']={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'url':'/api/studio3d/files/'+body['id']+'/review.json'}
    receipt.update(refinement=result,derived_from=body['refine'])
    receipt['quality']['reference_match']=after['assessment']['verdict']
    (folder/'receipt.json').write_text(canonical(receipt),encoding='utf-8')
    update(root,body['id'],status='BUILDING',phase='已保存本轮修改与复核记录')
    return receipt
