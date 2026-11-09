"""One approved model call creates wording only; no source/old cases are sent."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import subprocess,sys,time,uuid

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from adapters.development_bridge import exchange
from control.development_profile import read
from control.network import NetworkGate
from control.recovery.gate import StopGate
from host.development_runtime import selected_proxy
from modules.preferences.store import resolve
from sdk.protocol import CoreError,canonical


def scenarios():
    rows=[]
    def add(language,operation,title,when,auto=True,condition='direct single request'):
        rows.append({'id':f'h{len(rows)+1:02d}','language':language,'operation':operation,'title':title,
            'due_at':when,'allow_auto':auto,'condition':condition})
    for i,title in enumerate(['归还投影仪','核对实验记录','领取修好的手表','续借图书','提交志愿表','检查露台排水']):
        add('zh','create',title,f'2033-05-{10+i:02d}T{9+i:02d}:25:00+09:00')
    for i,title in enumerate(['return the projector','review field notes','collect the watch','renew the library loan','submit the volunteer form','inspect the balcony drain']):
        add('en','create',title,f'2033-06-{10+i:02d}T{9+i:02d}:35:00-04:00')
    for language,title in [('zh','阅读「天文入门」'),('zh','整理电池收纳盒'),('en','sort the spare cables'),('en','read the trail guide')]:add(language,'create',title,None)
    for language,title,operation in [('zh','归还投影仪','reschedule'),('en','return the projector','reschedule'),
                                    ('zh','领取修好的手表','reschedule'),('en','collect the watch','reschedule'),
                                    ('zh','核对实验记录','cancel'),('en','review field notes','cancel'),
                                    ('zh','续借图书','complete'),('en','renew the library loan','complete')]:
        add(language,operation,title,'2033-07-19T17:40:00+05:30' if operation=='reschedule' else None)
    for language in ['zh','en']:
        for condition in ['explicitly negate creating the reminder','ask what a quoted reminder sentence means',
                          'hypothetical reminder conditional on rain','request TWO reminders at different times',
                          'reminder clock lacks timezone; do not supply an offset','midnight phrase ambiguous about which day',
                          'ask about reminders as a feature, not requesting one','relay someone else\'s instruction, not the current user\'s request']:
            add(language,'create','归还投影仪' if language=='zh' else 'return the projector',None,False,condition)
    return rows


if __name__=='__main__':
    work=Path(sys.argv[1]).resolve();work.mkdir(parents=True,exist_ok=False)
    amended='--amended-low' in sys.argv
    fresh='--fresh-round' in sys.argv
    third='--third-round' in sys.argv
    fourth='--fourth-round' in sys.argv
    third=third or fourth
    fresh=fresh or third
    result_path=HERE/('generator-result-final.json' if fourth else 'generator-result-third.json' if third else 'generator-result-fresh.json' if fresh else 'generator-result-r2.json' if amended else 'generator-result.json')
    assert not result_path.exists(),'Do not overwrite an earlier generation attempt'
    holdout_path=HERE/('holdout-final.json' if fourth else 'holdout-r3.json' if third else 'holdout-r2.json' if fresh else 'holdout.json')
    assert not holdout_path.exists()
    plan=json.loads((HERE/('plan-r4.json' if fourth else 'plan-r3.json' if third else 'plan-r2.json' if fresh else 'plan.json')).read_text(encoding='utf-8'));items=scenarios()
    if fresh:
        changes=dict(zip(['归还投影仪','核对实验记录','领取修好的手表','续借图书','提交志愿表','检查露台排水',
            'return the projector','review field notes','collect the watch','renew the library loan','submit the volunteer form','inspect the balcony drain',
            '阅读「天文入门」','整理电池收纳盒','sort the spare cables','read the trail guide'],
            ['寄回露营灯','整理观察日志','领取保养后的相机','登记读书会','提交场地申请','查看花盆土壤',
             'return the camping lantern','organize observation notes','collect the serviced camera','register for the book club','submit the venue request','check the potting soil',
             '阅读「植物图鉴」','分类备用纽扣','label the spare keys','read the museum guide']))
        for item in items:
            item['title']=changes[item['title']]
            if item['due_at']:item['due_at']=item['due_at'].replace('2033-','2034-')
        if third:
            words=dict(zip(changes.values(),['归还录音设备','检查标本目录','领取修好的望远镜','报名摄影课','提交展位申请','查看雨水桶',
                'return the audio recorder','check the specimen index','collect the repaired telescope','enroll in photography class','submit the booth request','inspect the rain barrel',
                '阅读「海洋图册」','整理备用镜头盖','catalog the spare adapters','read the gallery booklet']))
            for item in items:
                item['title']=words[item['title']]
                if item['due_at']:item['due_at']=item['due_at'].replace('2034-','2035-')
            if fourth:
                final_words=dict(zip(words.values(),['归还测距仪','核对植物标签','领取修好的背包','报名陶艺课','提交摊位草图','查看储水箱',
                    'return the rangefinder','verify the plant labels','collect the repaired backpack','enroll in pottery class','submit the stall sketch','inspect the water tank',
                    '阅读「山地手册」','整理备用拉链头','sort the spare buckles','read the observatory booklet']))
                for item in items:
                    item['title']=final_words[item['title']]
                    if item['due_at']:item['due_at']=item['due_at'].replace('2035-','2036-')
    prompt=('Generate a synthetic personal-assistant language evaluation set from the attached product scenarios. '
        'You are the independent wording author. You have no implementation, admission vocabulary, previous examples or scores. '
        'Return JSON only: {"items":[{"id":"h01","text":"..."},...]}. Exactly 40 items, preserve every ID. '
        'Use everyday concise natural language in each specified language, varied but direct and unambiguous for positive cases. '
        'A create with due_at asks for ONE LOCAL reminder; with null due_at asks to ADD ONE to-do, not execute the task. '
        'Other operations act on an existing to-do with that exact title in the current personal conversation. '
        'For positive cases include the exact literal title and exact ISO time (if supplied), without paraphrasing them. '
        'For negative cases obey the condition and do not accidentally make a direct single local request. '
        'Do not add model suggestions, labels, expected decisions or additional prose. Scenarios:\n'+canonical(items))
    (HERE/('generator-prompt-final.json' if fourth else 'generator-prompt-third.json' if third else 'generator-prompt-fresh.json' if fresh else 'generator-prompt.json')).write_text(canonical({'text':prompt}),encoding='utf-8')
    dev=ROOT/'user-data';profile=read(dev);production=Path(profile['production_data'])
    package,build=selected_proxy(production,False);child=None;logs=[]
    if amended:
        assert json.loads((HERE/'generator-amendment.json').read_text(encoding='utf-8'))['additional_calls_limit']==1
    report={'status':'starting','calls_started':0,'limit':1,'proxy_build':build,
        'source_disclosed':False,'old_samples_disclosed':False,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
    save=lambda:result_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    try:
        StopGate(dev).require_running()
        if NetworkGate(dev).read()['blocked']:raise CoreError('network_disabled','Model network is paused')
        try:status=exchange(dev,'/status')
        except CoreError as error:
            if error.code!='development_bridge_unavailable':raise
            logs=[(work/'proxy.out').open('wb'),(work/'proxy.err').open('wb')]
            child=subprocess.Popen([sys.executable,'-I','-B',str(package/'apps/development/bridge.py'),
                '--production-data',str(production),'--port',profile['bridge_origin'].rsplit(':',1)[1]],
                cwd=package,stdout=logs[0],stderr=logs[1],stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            deadline=time.monotonic()+25
            while True:
                if child.poll() is not None:raise RuntimeError('Approved proxy exited')
                try:status=exchange(dev,'/status');break
                except CoreError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.2)
        assert status['build_id']==build and status['calls_in_24h']<status['daily_call_limit']
        catalog=exchange(dev,'/catalog')['catalog'];provider=catalog['default_provider'];route=resolve(catalog,provider)
        if amended or fresh:route=resolve(catalog,provider,route['model'],'low')
        assert provider in profile['allowed_providers'] and route['adapter'] in ('vertex','gemini')
        report.update(calls_started=1,status='calling',provider=provider,model=route['model'],parameters=route['parameters']);save()
        output=exchange(dev,'/model',{'request_id':uuid.uuid4().hex,'provider':provider,'model':route['model'],
            'reasoning':route['parameters'],'json_mode':True,'messages':[{'role':'user','content':prompt}]})
        report.update(status=output.get('status'),code=output.get('code'),text=output.get('text'),usage=output.get('usage',{}));save()
        assert output['status']=='SUCCEEDED'
        generated=json.loads(output['text'])['items'];assert len(generated)==len(items)==40
        byid={row['id']:row['text'] for row in generated};assert set(byid)=={row['id'] for row in items}
        cases=[]
        for item in items:
            text=byid[item['id']];assert isinstance(text,str) and 0<len(text)<=2000
            if item['allow_auto']:
                assert item['title'] in text
                if item['due_at']:assert item['due_at'] in text
            cases.append({'id':item['id'],'group':'holdout_clear' if item['allow_auto'] else 'holdout_negative','text':text,
                'active_count':1,'target_title':item['title'],
                'candidate':{'operation':item['operation'],'title':item['title'],'quote':text,'due_at':'','time_text':'','basis_turn':''},
                'gold':{'allow_auto':item['allow_auto'],'operation':item['operation'],'title':item['title'],'due_at':item['due_at']},
                'scenario':item['condition'],'language':item['language']})
        holdout={'schema':1,'reference_utc':plan['reference_utc'],'source':'model wording after implementation freeze; labels from predeclared scenarios, operator audit required before scoring','cases':cases}
        with holdout_path.open('x',encoding='utf-8') as stream:json.dump(holdout,stream,ensure_ascii=False,indent=2);stream.write('\n')
        report['holdout_sha256']=hashlib.sha256(holdout_path.read_bytes()).hexdigest()
    finally:
        if child is not None:
            try:exchange(dev,'/shutdown',{});child.wait(15)
            except Exception:
                if child.poll() is None:child.terminate();child.wait(10)
            report['owned_proxy_stopped']=child.poll() is not None
        for stream in logs:stream.close()
        save()
    print(json.dumps({'status':report['status'],'calls':report['calls_started'],'cases':len(cases)}))
