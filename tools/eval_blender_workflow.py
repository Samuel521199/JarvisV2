"""Exercise Jarvis's native Blender build/edit path in a new disposable data root."""
import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

from host.core import Core
from host import studio3d
from sdk.protocol import CoreError


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-root', required=True)
    p.add_argument('--blender', required=True)
    p.add_argument('--report', required=True)
    args = p.parse_args()
    root = Path(args.data_root).resolve()
    if root.exists(): p.error('Use a new test data root; existing data is never reset')
    Core.initialize(root).close()
    subprocess.run([sys.executable, '-m', 'tools.prepare_studio3d', '--data-root', str(root), '--blender', args.blender], check=True)
    report = {'schema': 'jarvis.blender-workflow-eval.v1', 'data_root': str(root), 'paid_calls': 0, 'results': {}}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    def save(): report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    def run(label, request):
        report['results'][label] = {'request': request}
        save()
        studio3d.start(root, request, None)
        deadline = time.monotonic()+330
        while time.monotonic()<deadline:
            job = studio3d.state(root, request['id'])
            if job['status'] not in ('QUEUED','PLANNING','BUILDING'): break
            time.sleep(.3)
        else:
            studio3d.cancel(root,request['id'])
            raise RuntimeError('Native build exceeded evaluator deadline')
        report['results'][label]['job'] = job
        save()
        assert job['status']=='DELIVERED', job
        assert job['receipt']['report']['glb_roundtrip']['passed']
        print(label+': DELIVERED '+request['id'], flush=True)
        return job
    scene = {'schema':'jarvis.studio3d.v1','units':'m','title':'Blender 工作流验收 · 分件机械壳体',
             'materials':[{'id':'shell-metal','color':'#507b9c','metallic':.75,'roughness':.32},
                          {'id':'steel','color':'#aeb9c6','metallic':.9,'roughness':.22}],
             'objects':[{'id':'housing','kind':'lathe','material':'shell-metal','params':{'profile':[[.14,-.25],[.20,-.20],[.21,.15],[.17,.25]],'segments':48},'modifiers':{'bevel':.004}},
                        {'id':'shaft','kind':'cylinder','material':'steel','position':[0,0,.35],'params':{'radius':.055,'depth':.3,'segments':32},'modifiers':{'bevel':.003}},
                        {'id':'mount','kind':'box','material':'steel','position':[0,0,-.29],'params':{'size':[.50,.40,.06]},'modifiers':{'bevel':.008}}],
             'render':{'quality':'preview','engine':'CYCLES','view':'front','five_views':True},
             'unfulfilled':['流程诊断模型，不对应真实机械尺寸、载荷或 AAA 美术验收。']}
    before=run('before',{'id':uuid.uuid4().hex,'scene':scene})
    raw,_=studio3d.file(root,before['id'],'scene.json')
    changes={'objects':[{'id':'housing','set':{'scale':[1.25,1.25,1]}}],
             'materials':[{'id':'shell-metal','set':{'color':'#ba5938','roughness':.18}}]}
    request={'id':uuid.uuid4().hex,'edit':before['id'],'source_sha256':hashlib.sha256(raw).hexdigest(),'changes':changes}
    after=run('after',request)
    assert studio3d.file(root,before['id'],'scene.json')[0]==raw
    bparts={o['id']:o for o in before['receipt']['configuration']['objects']}
    aparts={o['id']:o for o in after['receipt']['configuration']['objects']}
    assert bparts['shaft']==aparts['shaft'] and bparts['mount']==aparts['mount']
    assert after['receipt']['edit']['affected_objects']==['housing']
    assert after['receipt']['edit']['new_model_calls']==0
    try: studio3d.start(root,{**request,'id':uuid.uuid4().hex,'source_sha256':'0'*64},None)
    except CoreError as error:
        assert error.code=='conflict'
        report['stale_source_rejected']=True
    else: raise AssertionError('Stale source accepted')
    report.update(status='passed',source_preserved=True,untouched_parts_preserved=True,
                  visual_acceptance='pending_manual_review',scope='native scene build, bounded part/material edit, actual five-view renders, GLB roundtrip; no character rig or arbitrary external BLEND editing')
    save()
    print(json.dumps({'status':'passed','report':str(report_path),'before':before['id'],'after':after['id']},ensure_ascii=False))


if __name__=='__main__': main()
