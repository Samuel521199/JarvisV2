"""Validate a Jarvis plan without silently supplying missing artistic choices."""
import copy
from modules.skills.studio3d.demonstration import validate

TUNABLE=('amplitude','crown_fraction','shoulder_fraction','end_blend')


def validate_plan(reply,teacher):
    if not isinstance(reply,dict) or set(reply)!={'decision','actions','lesson_used','checks','limits'}:
        raise ValueError('Invalid independent plan fields')
    for key in ('lesson_used','checks','limits'):
        if not isinstance(reply[key],list) or len(reply[key])>12 or any(not isinstance(x,str) or not 1<=len(x)<=1600 for x in reply[key]):
            raise ValueError('Unbounded plan reasoning')
    if reply['decision']=='tool_gap':
        if reply['actions']!=[]:raise ValueError('Tool gap cannot contain execution actions')
        return None,{'mode':'DECLINED_TOOL_GAP','independent_success':False}
    if reply['decision']!='execute' or not isinstance(reply['actions'],list) or len(reply['actions'])!=len(teacher['actions']):
        raise ValueError('Explicit complete bounded plan required')
    result=copy.deepcopy(teacher);result['author']='Jarvis';result['actions']=copy.deepcopy(reply['actions'])
    validate(result,[a['target'] for a in teacher['actions']])
    changes=[]
    for base in teacher['actions']:
        a=next((a for a in result['actions'] if a['target']==base['target']),None)
        if a is None or set(a)!=set(base):raise ValueError('Frozen action schema changed')
        for key in set(base)-set(TUNABLE)-{'reason'}:
            if a[key]!=base[key]:raise ValueError('Plan changed a frozen asset value: '+key)
        if not .008<=a['amplitude']<=.034 or not .05<=a['crown_fraction']<=.35 or not .10<=a['shoulder_fraction']<=.40 or not .015<=a['end_blend']<=.09:
            raise ValueError('Plan exceeds declared artistic envelope')
        changes.extend({'target':a['target'],'field':k,'teacher':base[k],'jarvis':a[k]} for k in TUNABLE if a[k]!=base[k])
    return result,{'mode':'JARVIS_PARAMETER_SELECTION' if changes else 'EXACT_PARAMETER_REPLAY','parameter_changes':changes,
                   'independent_success':False,'limits':'Codex authored tool and frozen asset selection/cameras; no arbitrary Blender reconstruction or cross-asset learning claim'}
