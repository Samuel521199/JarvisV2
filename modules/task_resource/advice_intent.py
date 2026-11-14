"""Versioned, compositional purpose checks for optional advice.

Each clause must be covered in full. Slots combine across clauses; missing or
uncovered requirements remain visible in diagnostics, never inferred from data.
This is a bounded grammar, not a general natural-language or permission parser.
Changing its accepted language requires a new persisted advice version.
"""
import re

VERSION='advice-intent-1'
NEEDS={
    'jarvis.notes-input.v1':{'operation':'copy','fidelity':'verbatim','source_ids':'keep','order':'input'},
    'jarvis.practice-input.v1':{'operation':'multiply','answers':'correct','order':'input'},
}
PURPOSES={'jarvis.notes-input.v1':'notes-excerpt-v1','jarvis.practice-input.v1':'practice-product-v1'}


def rule(pattern,**slots):return re.compile(pattern,re.IGNORECASE),slots


NOTES=r'(?:当前|这些|这批)?(?:资料|笔记)'
IDS=r'来源(?:ID|编号|标识)'
JOIN=r'(?:和|与|及)'
ORDER=r'(?:原|原始|输入)?顺序'
COPY={'operation':'copy','fidelity':'verbatim'}
NOTES_RULES=[
    rule(r'整理'+NOTES),
    rule(r'(?:原样|逐字)(?:摘录|引用)(?:每条|各条|所有)?(?:原文|资料)',**COPY),
    rule(r'(?:把|将)'+NOTES+r'按'+ORDER+r'逐条(?:原样引用|逐字摘录|照抄)(?:成报告)?',**COPY,order='input'),
    rule(r'(?:把|将)'+NOTES+r'逐条(?:原样引用|逐字摘录|照抄)(?:成报告)?',**COPY),
    rule(r'(?:保留|保持)'+IDS+JOIN+ORDER,source_ids='keep',order='input'),
    rule(r'(?:保留|保持)'+ORDER+JOIN+IDS,source_ids='keep',order='input'),
    rule(r'(?:保留|保持)'+IDS,source_ids='keep'),
    rule(r'附上(?:各自|每条资料的)?'+IDS,source_ids='keep'),
    rule(r'(?:保留|保持)'+ORDER,order='input'),
    rule(r'(?:不要|不)(?:概括|总结|改写)'),
    rule(r'不把草稿估价写成确认结论'),
    rule(r'保存报告'),
    rule(r'(?:organize|arrange) (?:these|the|current) notes by copying each source verbatim in order with its id',**COPY,order='input',source_ids='keep'),
    rule(r'(?:copy|quote|transcribe) (?:each|every|all) (?:source|sources|note|notes) (?:verbatim|word for word)',**COPY),
    rule(r'(?:keep|preserve|retain) (?:the |their )?(?:source ids|source identifiers)',source_ids='keep'),
    rule(r'(?:keep|preserve|retain) (?:the |their )?(?:original|input) order',order='input'),
    rule(r'(?:keep|preserve|retain) (?:the |their )?source ids and (?:the )?(?:original|input) order',source_ids='keep',order='input'),
    rule(r'(?:do not|don\x27t) (?:summarize|rewrite|paraphrase)'),
    rule(r'save (?:the |a )?report'),
]
PRACTICE_RULES=[
    rule(r'(?:用当前给出的数生成|生成当前)乘法练习'+JOIN+r'正确答案',operation='multiply',answers='correct'),
    rule(r'按'+ORDER+r'把当前整数对做成乘法练习',operation='multiply',order='input'),
    rule(r'(?:根据|用)(?:当前)?(?:pairs|整数对|数对)(?:出|生成|制作)乘法(?:题|练习)(?:和|及)(?:正确)?答案',operation='multiply',answers='correct'),
    rule(r'(?:生成|制作|出)(?:当前)?乘法(?:题|练习)',operation='multiply'),
    rule(r'(?:附|附上|提供|给出)(?:每题的)?(?:正确)?答案',answers='correct'),
    rule(r'(?:保留|保持)(?:题目|输入|原|原始)顺序',order='input'),
    rule(r'顺序不变',order='input'),
    rule(r'(?:不要|不|勿)(?:评价|判断)(?:学习者|我|学生)是否掌握'),
    rule(r'不得声称已经掌握'),
    rule(r'保存练习表'),
    rule(r'(?:make|create|generate) multiplication (?:exercises|questions) and (?:correct )?answers from (?:these|the|current) pairs',operation='multiply',answers='correct'),
    rule(r'(?:make|create|generate) multiplication (?:exercises|questions) from (?:these|the|current) pairs',operation='multiply'),
    rule(r'(?:include|provide|add) (?:the )?(?:correct )?answers',answers='correct'),
    rule(r'(?:keep|preserve|retain|preserving) (?:the |their )?(?:original |input )?order',order='input'),
    rule(r'(?:do not|don\x27t) (?:claim|assess) (?:student |learner )?mastery'),
    rule(r'save (?:the |a )?worksheet'),
]
RULES={'jarvis.notes-input.v1':NOTES_RULES,'jarvis.practice-input.v1':PRACTICE_RULES}
PREFIX=re.compile(r'^(?:(?:请帮我|请|帮我|麻烦)(?:\s*)|please\s+)?(?:(?:并且|并|且)|and\s+)?',re.IGNORECASE)


def analyze(goal,schema):
    """Return full-coverage decisions and exact unsupported spans for diagnosis."""
    result={'version':VERSION,'matched':False,'slots':{},'missing':[], 'uncovered':[], 'clauses':[]}
    if schema not in RULES:
        result['reason']='unsupported_schema';return result
    if not isinstance(goal,str) or not 1<=len(goal)<=2000:
        result['reason']='goal_bounds';return result
    spans=list(re.finditer(r'[^，,；;。\.\r\n]+',goal))
    if not 1<=len(spans)<=32:
        result['reason']='clause_bounds';return result
    for span in spans:
        text=span.group().strip()
        if not text:continue
        clause=PREFIX.sub('',text,count=1)
        found=None
        for expression,slots in RULES[schema]:
            if expression.fullmatch(clause):found=slots;break
        record={'start':span.start(),'end':span.end(),'text':span.group()}
        if found is None:result['uncovered'].append(record);continue
        record['slots']=dict(found);result['clauses'].append(record)
        for key,value in found.items():
            if key in result['slots'] and result['slots'][key]!=value:
                result['uncovered'].append(record)
            else:result['slots'][key]=value
    result['missing']=[key for key,value in NEEDS[schema].items() if result['slots'].get(key)!=value]
    result['matched']=not result['missing'] and not result['uncovered']
    result['reason']='covered' if result['matched'] else ('uncovered_clause' if result['uncovered'] else 'missing_slots')
    if result['matched']:result['task_purpose']=PURPOSES[schema]
    return result
