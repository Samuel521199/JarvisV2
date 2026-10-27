"""Independent finite-domain oracle; no execution, source fetching or model call."""
import hashlib
import re
from sdk.protocol import CoreError, decode

VERSION = 'quote-selection-1'
REQUIREMENT = '按冻结报价输入核对预算、交期、完整合格集合、最低价和所选来源引用'


def source_digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def invalid():
    raise CoreError('acceptance_invalid', 'Expected bounded quote input and its exact reviewed digest')


def keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected.split())


def bounded_text(value, size):
    return isinstance(value, str) and 1 <= len(value) <= size and value == value.strip() and not any(ord(c) < 32 for c in value)


def integer(value, maximum):
    return type(value) is int and 0 <= value <= maximum


def parse_source(text):
    if not isinstance(text, str) or len(text) > 12000: invalid()
    try: value = decode(text.encode('utf-8'))
    except (CoreError, UnicodeError): invalid()
    if (not keys(value, 'schema currency max_price_minor max_delivery_days offers')
            or value['schema'] != 'jarvis.quote-input.v1'
            or not isinstance(value['currency'], str) or not re.fullmatch('[A-Z]{3}', value['currency'])
            or not integer(value['max_price_minor'], 10**12) or not integer(value['max_delivery_days'], 3650)
            or not isinstance(value['offers'], list) or not 1 <= len(value['offers']) <= 100): invalid()
    seen = set()
    for offer in value['offers']:
        if (not keys(offer, 'id price_minor delivery_days source') or not bounded_text(offer['id'], 80)
                or offer['id'] in seen or not integer(offer['price_minor'], 10**12)
                or not integer(offer['delivery_days'], 3650) or not bounded_text(offer['source'], 300)): invalid()
        seen.add(offer['id'])
    return value


def bound_source(body, rule):
    steps = body['steps']
    if (len(steps) < 2 or steps[-1]['capability'] != 'artifact.write.v1'
            or steps[-1].get('input_from') != rule['step_id'] or steps[-2]['step_id'] != rule['step_id']
            or any(not s['capability'].startswith('plugin.') for s in steps[:-1])
            or set(steps[0]['arguments']) != {'text'} or steps[0].get('input_from')
            or any(s.get('input_from') != steps[i-1]['step_id'] or s['arguments'] for i, s in enumerate(steps[1:-1], 1))): invalid()
    text = steps[0]['arguments']['text']
    value = parse_source(text)
    if source_digest(text) != rule['expected']: invalid()
    return value


def verify(body, rule, text):
    evidence = {'verifier': VERSION, 'source_digest': rule['expected']}
    def result(status, reason): return {**evidence, 'status': status, 'reason': reason}
    try: source = bound_source(body, rule)
    except CoreError: return result('invalid', 'quote_source_changed')
    try:
        if not isinstance(text, str) or len(text) > 20000: return result('failed', 'quote_report_invalid')
        report = decode(text.encode('utf-8'))
    except (CoreError, UnicodeError): return result('failed', 'quote_report_invalid')
    if (not keys(report, 'schema eligible_ids selected_id selected_source') or report['schema'] != 'jarvis.quote-result.v1'
            or not isinstance(report['eligible_ids'], list) or len(report['eligible_ids']) > 100
            or any(not bounded_text(i, 80) for i in report['eligible_ids'])
            or len(set(report['eligible_ids'])) != len(report['eligible_ids'])
            or report['selected_id'] is not None and not bounded_text(report['selected_id'], 80)
            or report['selected_source'] is not None and not bounded_text(report['selected_source'], 300)):
        return result('failed', 'quote_report_invalid')
    eligible = {o['id']: o for o in source['offers'] if o['price_minor'] <= source['max_price_minor']
                and o['delivery_days'] <= source['max_delivery_days']}
    if set(report['eligible_ids']) != set(eligible): return result('failed', 'quote_eligible_mismatch')
    if not eligible:
        return result('passed', 'quote_no_eligible') if report['selected_id'] is None and report['selected_source'] is None else result('failed', 'quote_selection_mismatch')
    chosen = eligible.get(report['selected_id'])
    if not chosen or chosen['price_minor'] != min(o['price_minor'] for o in eligible.values()):
        return result('failed', 'quote_selection_mismatch')
    if report['selected_source'] != chosen['source']: return result('failed', 'quote_source_mismatch')
    return result('passed', 'quote_verified')
