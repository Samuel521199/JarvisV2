"""Reviewed Standard/global list prices; separate source per Google route."""
from modules.image_generation.catalog import validate

SOURCES={'vertex':'https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing','gemini':'https://ai.google.dev/gemini-api/docs/pricing'}
RATES={'gemini-nano-banana-2.1':(1.5,7.5,30,.15),'gemini-3.1-flash-lite-image':(.25,1.5,30,.025),'gemini-3.1-flash-image':(.5,3,60,.05)}

def snapshot(adapter,model):
    incoming,text,image,cache=RATES[model]
    return {'schema':'google-image-rates.v1','currency':'USD','adapter':adapter,'model':model,'tier':'standard/global','input':incoming,'text_output':text,'image_output':image,'cache_read':cache,'checked_at':'2026-10-25','valid_until':'2026-11-24','source':SOURCES[adapter],'expiry_policy':'Local 30-day recheck deadline, not provider shutdown. Excludes taxes, credits and negotiated discounts.'}

def quote(adapter,value,references=0):
    validate(value);price=snapshot(adapter,value['model'])
    tokens={'512':747,'1K':1120,'2K':1680,'4K':3780 if value['model']=='gemini-nano-banana-2.1' else 2520}[value['size']]
    image=tokens*price['image_output']/1000000
    # A conservative planning allowance, not a provider-side spending cap.
    input_allowance=len(value['prompt'].encode())*2+1024+references*1120
    output_allowance=4096 if 'lite-image' in value['model'] else 8192
    upper=image+(input_allowance*price['input']+output_allowance*price['text_output'])/1000000
    return {'currency':'USD','image_output_estimate':round(image,8),'planning_allowance':round(upper,8),'price':price,'not_hard_billing_cap':True,'note':'图片输出估算另加输入与思考；预留额用于本地提交检查，不是Google账单硬上限。'}
