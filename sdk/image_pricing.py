"""Image modality accounting. Estimates are never provider invoices."""
from datetime import date,datetime,timezone
from decimal import Decimal


def estimate_image(price,usage,created):
    result={'amount':None,'currency':'USD','reason':'image_usage_missing','price':price}
    try:
        if price['schema']!='google-image-rates.v1':return {**result,'reason':'invalid_price'}
        if datetime.fromtimestamp(created,timezone.utc).date()>date.fromisoformat(price['valid_until']):return {**result,'reason':'price_expired'}
        incoming=usage['prompt_tokens'];outgoing=usage['completion_tokens'];images=usage['output_image_tokens']
        thinking=usage.get('reasoning_tokens',0);cached=usage.get('cache_read_tokens',0)
        if any(type(n) is not int or n<0 for n in (incoming,outgoing,images,thinking,cached)) or images>outgoing or cached>incoming:return {**result,'reason':'invalid_usage'}
        texts=outgoing-images
        if 'output_text_tokens' in usage and usage['output_text_tokens']!=texts:return {**result,'reason':'unreconciled_usage'}
        if usage.get('reasoning_in_completion') is not False:return {**result,'reason':'unreconciled_usage'}
        if usage.get('total_tokens',incoming+outgoing+thinking)!=incoming+outgoing+thinking:return {**result,'reason':'unreconciled_usage'}
        counts={'input':incoming-cached,'cache_read':cached,'text_output':texts+thinking,'image_output':images}
        components={k:float(Decimal(n)*Decimal(str(price[k]))/1000000) for k,n in counts.items()}
        return {**result,'amount':round(sum(components.values()),12),'reason':'image_modality_rates','components':components,'counts':counts,'invoice_verified':False}
    except (KeyError,ValueError,TypeError,ArithmeticError):return result
