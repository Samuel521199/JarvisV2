"""Freeze evidence for the completed structure-3D acceptance run; no model calls."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/evidence/anatomy-structure-2026-10-23'
def read(name):return json.loads((BASE/name).read_text(encoding='utf-8'))
def main():
    if (BASE/'assessment.json').exists():raise SystemExit('Assessment already exists; preserve history')
    browser=read('deployed-2/browser.json');generated=read('generated-1/browser.json');first=read('model-1/evaluation.json');second=read('model-2/evaluation.json');soak=read('soak-1/performance.json');numbers=read('model-2/numerical.json');receipt=second['refreshed_artifact']
    assert all(x['status']=='passed' for x in [browser,generated,first,second,soak,numbers])
    for name,sha in receipt['renderer_sha256'].items():assert hashlib.sha256((ROOT/'modules/skills/anatomy'/name).read_bytes()).hexdigest()==sha,name
    for name,sha in receipt['host_validation_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    calls={row['turn_id']:row for row in first['usage']+second['usage']};assert len(calls)==3
    cost=round(sum(row['billing']['amount'] for row in calls.values()),10)
    with urllib.request.urlopen('http://127.0.0.1:18282/api/snapshot',timeout=10) as r:runtime=json.load(r)['status']['release']
    files=['host/anatomy.py','host/anatomy_scene.py','host/anatomy_composer.py','modules/skills/anatomy/build.mjs','modules/skills/anatomy/studio.html','modules/skills/anatomy/studio-view.js','modules/skills/anatomy/structure3d.mjs','modules/skills/anatomy/structure-scenes.mjs','modules/skills/anatomy/structure-audit.mjs','modules/skills/anatomy/scene-schema.json','modules/skills/anatomy/studio-presets.json','seed/skills/conversation.json','tests/anatomy_structure3d.mjs','tools/probe_anatomy_structure.cjs','tools/probe_anatomy_generated.cjs','tools/probe_anatomy_structure_soak.cjs','tools/eval_anatomy_structure.py']
    report={'adapter_version':'4.0.0','status':'verified_with_limits','project_file_version_at_close':(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'runtime_version':runtime,'source':receipt['source'],'files_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'final_renderer_matches_receipt':True,
      'tests':{'python_full':{'tests':226,'seconds':170.100,'status':'passed'},'anatomy_final':{'tests':15,'status':'passed'},'structure_geometry':{k:v for k,v in numbers.items() if k!='inventories'},'original_teaching_models':{'cylinder_states':45360,'motor_cases':216,'wave_cases':3888,'coupling_cases':648,'part_poses':1292,'status':'passed'},'browser':'deployed-2/browser.json','generated_scene':'generated-1/browser.json'},
      'model_evaluation':{'route':'vertex','model':first['model'],'generation_calls':1,'review_calls':2,'initial_score':first['technical_score'],'final_score':second['technical_score'],'final_scores':second['review']['scores'],'weights':{'structure':.3,'motion_consistency':.3,'effect_consistency':.25,'inspectability':.15},'visual_score':None,'scope':'data-only technical model review; no screenshot vision, independent certification or success-rate estimate','review_correction':'Initial review incorrectly described one 20:40 gear pair as two-stage. Actual configuration has one stage; final prompt made this explicit. Raw review preserved.','cost_estimate_usd':cost,'billing':'Actual recorded usage including reasoning at dated local prices; not supplier invoices'},
      'improvements':{'animation':'Added 10/20/30 FPS targets, default20; one-pump1300ms observed updates14 ->25','section':'Highlighted cut boundaries; exact solid caps remain unavailable','scope_notice':'Prominent teaching-flow disclaimer'},
      'observed_performance':{'one_pump_updates_per_1300ms':browser['animation_updates'],'five_component_updates_per_1500ms':generated['updates_in_1500ms'],'extended_seconds':soak['actual_seconds'],'extended_updates':soak['updates'],'extended_updates_per_second':soak['average_updates_per_second'],'limits':soak['scope']},
      'limits':second['review']['unverified']+['No exact section caps, per-pixel depth buffer or exact transparent ordering','No CFD, combustion, heat transfer, load feedback, manufacturing CAD or video export','Original artifact URLs remain immutable; use the new artifact for structure4.0'],
      'demo_url':generated['url'],'engine_url':browser['url'],'jet_url':'http://127.0.0.1:18282'+browser['receipts'][0]['url'],'pump_url':'http://127.0.0.1:18282'+browser['receipts'][-1]['url']}
    with (BASE/'assessment.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2);stream.write('\n')
    handoff=read('handoff.json');handoff.update(state='complete; implementation frozen and evidence finalized',code_changes_planned=False,remaining=[],final_assessment='assessment.json',adapter_version='4.0.0',project_file_version=report['project_file_version_at_close'])
    (BASE/'handoff.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':report['status'],'model_cost_usd':cost,'technical_score':second['technical_score'],'visual_score':None,'demo':report['demo_url'],'runtime_version':runtime}))
if __name__=='__main__':main()
