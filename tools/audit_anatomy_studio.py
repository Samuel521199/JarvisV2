"""Summarize the recorded 2026-10-23 acceptance run without model calls.

Counts below describe the completed run, not a replacement for running tests.
Reject overwriting the saved assessment so earlier evidence remains immutable.
"""
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/evidence/anatomy-studio-2026-10-23'
def read(name):return json.loads((BASE/name).read_text(encoding='utf-8'))
def main():
    if (BASE/'assessment.json').exists():raise SystemExit('Assessment already exists; preserve it')
    latest=read('deployed-4/browser.json');first=read('deployed-1/browser.json');recovered=read('recovered-2/browser.json')
    assert latest['status']==recovered['status']=='passed'
    for receipt in latest['artifacts']:
        for name,sha in receipt['renderer_sha256'].items():assert hashlib.sha256((ROOT/'modules/skills/anatomy'/name).read_bytes()).hexdigest()==sha
        for name,sha in receipt['host_validation_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha
    files=['host/anatomy.py','host/anatomy_scene.py','host/anatomy_composer.py',
      *['modules/skills/anatomy/'+f for f in ['build.mjs','scene-schema.json','studio-presets.json','studio-model.mjs','studio-view.js','studio.html']],
      *['apps/workbench/'+f for f in ['settings-anatomy.js','settings.js','server.py','ui.js']],
      'seed/skills/conversation.json','tests/test_anatomy.py','tests/test_anatomy_studio.py','tests/anatomy_studio.mjs',
      'tools/probe_anatomy_studio.cjs','tools/probe_anatomy_composition.cjs']
    checks={
      'python_full_suite':{'command':'python -m unittest discover -s tests','tests':215,'seconds':171.202,'status':'passed'},
      'python_final_anatomy':{'tests':15,'status':'passed'},
      'studio_model':{'cylinder_states':45360,'motor_cases':216,'water_cases':3888,'coupling_cases':648,'part_poses':1292,'presets':6,'status':'passed'},
      'planetary_regression':{'motion_cases':57327,'poses':732,'vertex_checks':780678,'penetrations':0,'status':'passed'},
      'browser':{'final':'deployed-4/browser.json','recovery':'recovered-2/browser.json','final_checks':14,'script_errors':0,'animation_updates_per_1300ms':26,'status':'passed'}}
    calls=first['cloud_receipt']['calls']+recovered['receipt']['calls'];cost=round(sum(c['billing']['amount'] for c in calls),10)
    assessment={
      'status':'verified_with_limits','project':'0.2.0-dev.10','adapter':'3.0.0',
      'source':{'repository':'https://github.com/wheresryan22/anatomy','commit':'1482e8469b0a9e0d8cc18ea2740a01423d29ae80','license':'MIT','author':'Ryan','changes':'Jarvis independently authored composition, kinematic trees, teaching physics, effect views, integration and receipts; original iso kit preserved'},
      'files_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'checks':checks,
      'real_model':{'provider':'vertex','model':'gemini-3.8-flash','calls':2,'composed_engine':'deployed-1/browser.json','assembly_initial_rejection':'deployed-2/browser.json','assembly_reused_after_audited_identifier_normalization':'recovered-2/browser.json','extra_calls_for_repair':0,'billing_estimate':{'currency':'USD','amount':cost,'basis':'Recorded usage including reasoning and local dated rates; not supplier invoices'},'generalization':'Two tasks on one route; no multi-model success-rate claim'},
      'final_renderer_hashes_match_final_preset_receipts':True,
      'immutable_history':'Earlier artifacts keep their exact renderer hashes. Final generic renderer adds a prismatic guide line after the original model artifact. Failed reports and previous snapshots are not rewritten. Final browser covers final rendering resources.',
      'rating':{'score':8.5,'scale':10,'kind':'engineering self-assessment, not blind evaluation','criteria':[{'name':'kinematics','score':9,'weight':.3},{'name':'visuals','score':8,'weight':.2},{'name':'interaction','score':9,'weight':.2},{'name':'integration','score':8,'weight':.2},{'name':'mechanism_coverage','score':8,'weight':.1}]},
      'limits':['Assembly: up to 16 box/cylinder bodies with prescribed tree joints; no closed-loop or inverse solver','Particles/flames/sparks/fields/pump flow are illustrative; no combustion/CFD/field solver','Motor steady state and 1D small-amplitude waves only; no circuit transient or fluid load feedback','No CAD/manufacturing, FEA, collision, video, low-end PC or long duration benchmark','Explicit generation in skill manager; ordinary chat does not start paid models or execute code'],
      'demo_urls':{'engine':'http://127.0.0.1:18282'+latest['artifacts'][0]['url'],'jet':'http://127.0.0.1:18282'+latest['artifacts'][1]['url'],'electromechanical_water':'http://127.0.0.1:18282'+latest['artifacts'][2]['url'],'free_assembly':recovered['url']}}
    for name,data in [('checks.json',checks),('assessment.json',assessment)]:
        with (BASE/name).open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps({'cost_usd':cost,'demos':assessment['demo_urls'],'source_files':len(files)}))
if __name__=='__main__':main()
