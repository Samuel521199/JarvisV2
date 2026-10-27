"""Validated rate snapshots and conservative estimates, never supplier invoices."""
from datetime import date, datetime, timezone
from decimal import Decimal
import math
from sdk.protocol import CoreError


def validate_price(value):
    if value is None: return None
    required = {'currency', 'input', 'output', 'cache_read', 'cache_write', 'fee_percent', 'checked_at', 'source', 'max_input_tokens'}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - {'valid_until'}:
        raise CoreError('price_invalid', 'Invalid rate fields')
    if value['currency'] not in {'USD', 'CNY'}: raise CoreError('price_invalid', 'Unsupported currency')
    for key in ['input', 'output', 'cache_read', 'cache_write', 'fee_percent']:
        n=value[key]
        if n is not None and (type(n) not in {int,float} or not math.isfinite(n) or not 0 <= n <= 1000000):
            raise CoreError('price_invalid', 'Rate must be finite and nonnegative')
    if type(value['max_input_tokens']) is not int or not 1 <= value['max_input_tokens'] <= 10000000:
        raise CoreError('price_invalid', 'Invalid input tier')
    if not isinstance(value['source'], str) or len(value['source']) > 500: raise CoreError('price_invalid', 'Invalid source')
    try:
        checked=date.fromisoformat(value['checked_at'])
        if value.get('valid_until') and date.fromisoformat(value['valid_until']) < checked: raise ValueError()
    except (ValueError, TypeError): raise CoreError('price_invalid', 'Invalid rate date') from None
    return value


def estimate(profile, usage, created):
    if profile and profile.get('image_price'):
        from sdk.image_pricing import estimate_image
        return estimate_image(profile['image_price'],usage,created)
    result={'amount':None,'currency':None,'reason':'historical_no_price_snapshot','price':None}
    if not profile: return result
    price=profile.get('price');result.update(price=price,reason='missing_usage_or_price')
    if profile.get('adapter')=='local': return {**result,'amount':0,'reason':'local_no_api_charge'}
    if price is None: return result
    try: validate_price(price)
    except CoreError: return {**result,'reason':'invalid_price'}
    result['currency']=price['currency']
    if price.get('valid_until') and datetime.fromtimestamp(created,timezone.utc).date()>date.fromisoformat(price['valid_until']):
        return {**result,'reason':'price_expired'}
    counts=[usage.get('prompt_tokens'),usage.get('completion_tokens')]
    if any(type(n) is not int or n<0 for n in counts): return result
    incoming,outgoing=counts
    cached=usage.get('cache_read_tokens',0);written=usage.get('cache_write_tokens',0)
    reasoning=usage.get('reasoning_tokens',0)
    if any(type(n) is not int or n<0 for n in [cached,written,reasoning]) or cached+written>incoming:
        return {**result,'reason':'invalid_usage'}
    if usage.get('reasoning_in_completion') is False: outgoing+=reasoning
    total=usage.get('total_tokens')
    if type(total) is int and total!=incoming+outgoing: return {**result,'reason':'unreconciled_usage'}
    if incoming>price['max_input_tokens']: return {**result,'reason':'outside_price_tier'}
    parts=[(incoming-cached-written,'input'),(outgoing,'output'),(cached,'cache_read'),(written,'cache_write')]
    if price['fee_percent'] is None or any(n and price[k] is None for n,k in parts):
        return {**result,'reason':'missing_token_rate'}
    amount=sum(Decimal(n)*Decimal(str(price[k] or 0)) for n,k in parts)/Decimal(1000000)
    amount*=1+Decimal(str(price['fee_percent']))/100
    return {**result,'amount':float(amount.quantize(Decimal('.000000000001'))),'reason':'token_rates'}
