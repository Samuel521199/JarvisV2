"""Three real project-derived tasks through the existing bounded proxy and Host.

These are operator-authored controlled tasks, not independent end-user trials.
Gold references never enter model context. No new credentials or permissions.
"""
from pathlib import Path
import copy,json,sys,tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
from adapters.development_bridge import exchange
from adapters.models.native import NativeModel
from control.network import NetworkGate
from control.recovery.gate import StopGate
from sdk.protocol import CoreError
from tools.work_trials import bounded_route,run_suite


def suite():
    # Reuse the shared requested-document format, not historical task answers.
    old=json.loads((ROOT/'tests/fixtures/work_fidelity_v2.json').read_text(encoding='utf-8'))
    contract=old['cases'][0]['turns'][0]['prompt'].split('只在本轮reply中输出JSON',1)[1]
    contract='只在本轮reply中输出JSON'+contract
    def turn(request,sources,expected,plans=()):
        return {'prompt':request+'\n本轮可引用原文：\n'+'\n'.join(k+'：'+v for k,v in sources.items())+'\n'+contract,
            'expected':expected,'unordered':[],'text_fields':['document'],'forbidden':{},
            'body_evidence':{'sources':sources,'facts':[k for k in sources if k not in plans],'plans':list(plans)}}
    storage={'F1':'本机C、D分区属于同一块内置物理磁盘。',
             'F2':'E是外接硬盘NTFS分区，真实LPAC文本执行已通过。',
             'F3':'G是同一外接硬盘的exFAT分区，现有LPAC持久ACL检查未通过。'}
    storage2={**storage,'F4':'E和G属于同一块外接物理硬盘，分区间副本不能防这块硬盘整体失效。'}
    acceptance={'F1':'Jarvis日用和开发主目录已迁至E盘，代码与日用数据仍分离。',
                'F2':'Codex迁移工具已测试，但真实记忆当前仍在C盘，离线切换和重启验收尚未执行。',
                'P1':'完全退出Codex后运行离线迁移，再重启核对原会话和记忆。'}
    acceptance2={**acceptance,'F3':'旧版影子探针生成86个额外字节码缓存，固定程序包完整性门拒绝启动。',
                 'F4':'86个缓存已核对并归档移出，659个清单源码文件原摘要保持；日用v0.1.8已恢复在线，epoch为7。'}
    learning={'F1':'首次探针对开发profile调用require_online，被development_external_denied拒绝。',
              'F2':'拒绝发生在模型请求发出之前，该次探针模型调用数为0。',
              'F3':'开发profile禁止直接外联，模型请求必须走既有认证的本地代理。'}
    learning2={**learning,'F4':'修正后的探针只检查网络暂停开关，并通过既有本地代理请求模型，没有开启直接外联或备用厂商。',
               'F5':'本轮未进行学习者独立作答、延迟记忆或迁移测验。'}
    return {'schema':'jarvis.work-trials.v2','origin':'user_supplied',
        'provenance':'Operator-authored tasks derived from this user-authorized Jarvis migration and actual local evidence on 2026-11-13. No independent-user or supplier-quotation claim; not learner outcome evidence.',
        'cases':[
            {'id':'actual-storage-choice','domain':'comparison','skill':'none','turns':[
                turn('根据本机实际记录比较运行位置：必须位于外接盘且保持已验证的LPAC边界。selected_volume填单个盘符或null，candidate_isolated填布尔。保留本轮所有事实，不把迁盘当关闭隔离的理由。',storage,{'selected_volume':'E','candidate_isolated':True}),
                turn('继续核对备份的故障域。same_external_physical_disk填布尔，partition_copy_protects_whole_disk_failure填布尔。保留本轮所有事实，不能把多分区称为独立整盘灾备。',storage2,{'same_external_physical_disk':True,'partition_copy_protects_whole_disk_failure':False})]},
            {'id':'actual-acceptance-notes','domain':'documents','skill':'journal-review','turns':[
                turn('整理本次迁移验收简报。codex_cutover_completed和all_storage_retired填布尔；原文没有证明旧副本已退役时不能宣称全量完成。保留本轮事实和已确认计划，计划不能写成完成事实。',acceptance,{'codex_cutover_completed':False,'all_storage_retired':False},['P1']),
                turn('把新增的真实启动故障及恢复过程加入简报。manifested_source_changed和codex_cutover_completed填布尔，daily_epoch填整数。保留本轮全部事实及仍有效的计划，不把生成缓存的问题说成清单源码被改。',acceptance2,{'manifested_source_changed':False,'codex_cutover_completed':False,'daily_epoch':7},['P1'])]},
            {'id':'actual-boundary-lesson','domain':'learning','skill':'english-coach','turns':[
                turn('用本次真实错误整理学习卡，区分权限边界拒绝与模型服务失败。failure_category填permission_boundary或provider_failure，model_calls_started填整数。保留本轮全部事实，不发明未发生的模型故障。',learning,{'failure_category':'permission_boundary','model_calls_started':0}),
                turn('继续整理修正方法与学习结论。direct_egress_enabled填布尔，learner_retention_result未实测填null。保留本轮全部事实，不把看过学习卡等同于学习者已掌握。',learning2,{'direct_egress_enabled':False,'learner_retention_result':None})]}]}


def main():
    output=Path(sys.argv[1]).resolve();dev=ROOT/'user-data'
    def checkpoint():
        StopGate(dev).require_running()
        if NetworkGate(dev).read()['blocked']:raise CoreError('network_disabled','Model network is paused')
    checkpoint();status=exchange(dev,'/status')
    if status['daily_call_limit']-status['calls_in_24h']<12:raise RuntimeError('Need twelve calls within the unchanged approved allowance')
    catalog=copy.deepcopy(exchange(dev,'/catalog')['catalog']);provider=catalog['default_provider']
    catalog['automatic_fallback']=False;catalog['fallback_order']=[provider]
    # The pinned proxy only accepts its approved profile, including this ceiling.
    route=bounded_route(catalog,provider,reasoning='low',max_output_tokens=8192)
    if route['adapter'] not in {'vertex','gemini'}:raise RuntimeError('Unexpected approved route')
    def no_direct_credentials(*_):raise RuntimeError('Direct model credentials must never be used')
    def factory(cfg,_):return NativeModel(cfg,no_direct_credentials,dev/'temp')
    directory=Path('E:/Jarvis/validation/model-domain-temp');directory.mkdir(parents=True,exist_ok=True)
    original=tempfile.TemporaryDirectory
    def temporary(*args,**kwargs):
        kwargs.setdefault('dir',directory);return original(*args,**kwargs)
    with patch('tools.work_trials.tempfile.TemporaryDirectory',temporary):
        result=run_suite(suite(),output,catalog,route,factory,execution='live',owner_checkpoint=checkpoint)
    result['project_derived_not_independent_user_tasks']=True
    with (output/'summary.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'complete':result['comparison_complete'],'candidate_conditions_passed':result['all_candidate_conditions_passed'],
        'calls':result['costs']['attempts'],'quality_gain':result['quality_gain'],'full_cost':result['costs']['full_cost']}),flush=True)


if __name__=='__main__':main()
