"""One explicit paired-image Jarvis review, saved before submission; never auto-retry."""
import argparse,base64,hashlib,json,re,time,urllib.request,uuid
from pathlib import Path
from control.local_access import install_client


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-root',required=True,type=Path);p.add_argument('--provider',required=True);p.add_argument('--model',required=True);p.add_argument('--review-name',default='jarvis-visual-review');a=p.parse_args()
    if not re.fullmatch('[a-z0-9-]{1,70}',a.review_name):raise ValueError('Review record identity')
    asset=a.asset_root.resolve();out=asset/'metadata'/(a.review_name+'.json')
    if out.exists():raise ValueError('Review already recorded; inspect it, do not replay')
    origin='http://127.0.0.1:18282';install_client(origin)
    def get(path):return json.load(urllib.request.urlopen(origin+path,timeout=30))
    def post(path,body):
        token=get('/api/session')['token'];r=urllib.request.Request(origin+path,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Origin':origin,'X-Jarvis-Token':token,'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(r,timeout=60))
    def save(value):out.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    refs=[]
    for name in ['reference.png','renders/hero.png']:
        raw=(asset/name).read_bytes();r=post('/api/studio3d/references',{'name':'Panzer II '+name,'source':'User-provided concept reference' if name=='reference.png' else 'Actual Jarvis Blender assembled high-poly render','license':'User-supplied local project; no redistribution license asserted','data':base64.b64encode(raw).decode()});refs.append({'id':r['id'],'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
    chat=post('/api/chats',{})['id'];post('/api/chat/update',{'id':chat,'patch':{'title':'二号坦克分件组装与高模学习审阅'}})
    report=json.loads((asset/'metadata/assembly-report.json').read_text(encoding='utf-8'))
    prompt='你是 Jarvis 的3D美术审阅者。图1是用户的目标概念图，图2是实际Blender组装渲染，不是AI重绘。对照图指出模型已经体现的细节，以及剩余的轮廓/比例/安装、材质、缺件问题。不同相机和灯光不能误判成几何变化；不要只因面数高就给高评价。几何没有真实测绘，不做制造或武器性能判断。只生成候选经验，不能声称权重学习、独立重建、跨资产提升或AAA验收。保持中文简洁。返回严格JSON：{"observations":[],"geometry_gaps":[],"material_gaps":[],"candidate_lessons":[{"when":"","steps":[],"reject_when":"","check":""}],"next_priorities":[],"uncertainty":[]}。已核验事实：5个源GLB各约190万三角面、每件3张4096x4096颜色/粗糙金属度/法线贴图；右履带镜像成左履带；6个分件合计'+str(report['triangles'])+'三角面；只做整体尺度和摆放，不重拓扑、不烘焙、不添加风化；原件不变；GLB回读通过。'
    turn='assembly-review-'+uuid.uuid4().hex;body={'chat_id':chat,'request_id':turn,'text':prompt,'provider':a.provider,'model':a.model,'reasoning':'medium','skill':'studio3d','memory_enabled':False,'reference_images':[r['id'] for r in refs]}
    row={'status':'PREPARED','chat_id':chat,'request_id':turn,'references':refs,'request':body,'started_at':time.time(),'model_weight_training':False};save(row)
    try:
        row['accepted']=post('/api/chat/send',body);row['status']='SUBMITTED';save(row)
        for _ in range(180):
            state=get('/api/chats/'+chat);item=next((x for x in state['turns'] if x['id']==turn),None)
            if item and item['status'] not in ('READY','RUNNING'):
                row.update(status=item['status'],reply=item.get('reply'),error=item.get('error'));break
            time.sleep(1)
        else:row['status']='OBSERVATION_TIMEOUT'
        row['usage']=[x for x in get('/api/usage') if x['turn_id']==turn]
    except Exception as e:row['observer_error']=str(e);raise
    finally:row['elapsed_seconds']=time.time()-row['started_at'];save(row)
    print(json.dumps({k:row.get(k) for k in ['status','chat_id','request_id','elapsed_seconds']},ensure_ascii=False))

if __name__=='__main__':main()
