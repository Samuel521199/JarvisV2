"""Explicit requirement-to-check coverage, not natural-language entailment."""
from sdk.protocol import CoreError
from modules.task_resource.quote_checks import REQUIREMENT
from modules.task_resource.quote_request import REQUIREMENT as REQUEST_REQUIREMENT
from modules.task_resource.source_checks import REQUIREMENT as SOURCE_REQUIREMENT
from modules.task_resource.change_checks import REQUIREMENT as CHANGE_REQUIREMENT

from modules.task_resource.inheritance_checks import REQUIREMENT as REWORK_REQUIREMENT

from modules.task_resource.recovery_checks import REQUIREMENT as RECOVERY_REQUIREMENT

VERSION = 'declared-requirements-1'
SUPPORTED = {'literal': {'text_equals'}, 'statistics': {'text_statistics'}, 'semantic': set(), 'quote_selection': {'quote_selection'}, 'quote_request': {'quote_request'}, 'quote_sources': {'quote_sources'}, 'quote_changes': {'quote_changes'}, 'quote_rework': {'quote_rework'}, 'quote_recovery': {'quote_recovery'}}


def validate(rules):
    requirements = rules.get('requirements')
    if 'requirements' not in rules:
        return
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 16:
        raise CoreError('acceptance_invalid', 'Expected one to sixteen explicit requirements')
    checks = {c['id'] for c in rules['criteria']}
    seen = set()
    for item in requirements:
        if (not isinstance(item, dict) or set(item) != {'id', 'text', 'kind', 'criterion_ids'}
                or not isinstance(item['id'], str) or not 1 <= len(item['id']) <= 80 or item['id'] in seen
                or not isinstance(item['text'], str) or not 1 <= len(item['text'].strip()) <= 1000
                or not isinstance(item['kind'], str) or item['kind'] not in SUPPORTED
                or not isinstance(item['criterion_ids'], list) or len(item['criterion_ids']) > 16
                or any(not isinstance(c, str) or c not in checks for c in item['criterion_ids'])
                or len(set(item['criterion_ids'])) != len(item['criterion_ids'])):
            raise CoreError('acceptance_invalid', 'Invalid requirement or unknown criterion reference')
        seen.add(item['id'])
        if item['kind']=='quote_selection' and item['text']!=REQUIREMENT:
            raise CoreError('acceptance_invalid', 'Quote requirements have a fixed bounded meaning')
        if item['kind']=='quote_request' and item['text']!=REQUEST_REQUIREMENT:
            raise CoreError('acceptance_invalid', 'Quote request requirements have a fixed bounded meaning')
        if item['kind']=='quote_sources' and item['text']!=SOURCE_REQUIREMENT:
            raise CoreError('acceptance_invalid','Quote source requirements have a fixed bounded meaning')
        if item['kind']=='quote_recovery' and item['text']!=RECOVERY_REQUIREMENT:
            raise CoreError('acceptance_invalid','Recovery requirements have a fixed bounded meaning')
        if item['kind']=='quote_rework' and item['text']!=REWORK_REQUIREMENT:
            raise CoreError('acceptance_invalid','Rework requirements have a fixed bounded meaning')
        if item['kind']=='quote_changes' and item['text']!=CHANGE_REQUIREMENT:
            raise CoreError('acceptance_invalid','Quote change requirements have a fixed bounded meaning')


def evaluate(rules, checks):
    requirements = rules.get('requirements', []) if rules else []
    criteria = {c['id']: c for c in rules['criteria']} if rules else {}
    results = {c['id']: c['status'] for c in checks}
    rows = []
    for item in requirements:
        refs = item['criterion_ids']
        supported = bool(refs) and all(criteria[r]['check'] in SUPPORTED[item['kind']] for r in refs)
        status = ('unknown' if not supported else 'failed' if any(results[r] == 'failed' for r in refs)
                  else 'invalid' if any(results[r] == 'invalid' for r in refs)
                  else 'passed' if all(results[r] == 'passed' for r in refs) else 'unknown')
        rows.append({**item, 'status': status, 'reason': 'unmapped' if not refs else
                     'unsupported_verifier' if not supported else 'linked_checks'})
    complete = bool(rows) and rules['coverage'] == 'complete' and all(r['status'] == 'passed' for r in rows)
    return {'version': VERSION, 'state': 'SATISFIED' if complete else 'UNSPECIFIED' if not rows else 'INCOMPLETE',
            'requirements': rows, 'complete': complete, 'scope': 'explicitly_declared_requirements',
            'semantic_goal_verified': False}
