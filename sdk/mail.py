"""Gmail contracts and safe text codecs; no mailbox or execution authority."""
import base64
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
from html.parser import HTMLParser
import re

from sdk.protocol import CoreError

READ='https://www.googleapis.com/auth/gmail.readonly'
COMPOSE='https://www.googleapis.com/auth/gmail.compose'
SEND='https://www.googleapis.com/auth/gmail.send'
MODIFY='https://www.googleapis.com/auth/gmail.modify'
LEVELS={'read':{READ},'compose':{READ,COMPOSE},'send':{READ,SEND},'manage':{READ,MODIFY}}
CHANGES={'read':(['UNREAD'],[]),'unread':([],['UNREAD']),'star':([],['STARRED']),
         'unstar':(['STARRED'],[]),'archive':(['INBOX'],[]),'inbox':([],['INBOX']),
         'spam':(['INBOX'],['SPAM']),'unspam':(['SPAM'],['INBOX']),
         'trash':([],['TRASH']),'untrash':(['TRASH'],[])}


def capabilities(scope):
    scopes=set(scope.split()) if isinstance(scope,str) else set()
    return {'read':bool(scopes&{READ,MODIFY}),'draft':bool(scopes&{COMPOSE,MODIFY}),
            'send':bool(scopes&{SEND,COMPOSE,MODIFY}),'modify':MODIFY in scopes}


def client_configuration(value):
    if not isinstance(value,dict) or set(value)!={'installed'} or not isinstance(value['installed'],dict):
        raise CoreError('mail_client_invalid','Select a Google OAuth desktop application JSON, not an API key or service account')
    data=value['installed'];ident=data.get('client_id');secret=data.get('client_secret')
    if (not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9_-]{5,180}\.apps\.googleusercontent\.com',ident)
            or not isinstance(secret,str) or not 1<=len(secret)<=256):
        raise CoreError('mail_client_invalid','Desktop client ID and secret are required')
    return {'client_id':ident,'client_secret':secret}


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,180}',value):
        raise CoreError('mail_invalid','Invalid message identifier')
    return value


def address(value):
    if not isinstance(value,str) or len(value)>254 or '\r' in value or '\n' in value:
        raise CoreError('mail_address','Expected one email address')
    parsed=parseaddr(value)[1]
    if parsed!=value or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',parsed):
        raise CoreError('mail_address','Expected one email address')
    return parsed


def draft(value):
    if not isinstance(value,dict) or set(value)!={'to','subject','body'}:raise CoreError('mail_invalid','Unexpected draft fields')
    address(value['to'])
    if not isinstance(value['subject'],str) or not 1<=len(value['subject'])<=200 or any(c in value['subject'] for c in '\r\n'):
        raise CoreError('mail_invalid','Invalid mail subject')
    if not isinstance(value['body'],str) or not 1<=len(value['body'])<=30000:raise CoreError('mail_invalid','Mail body is empty or too long')
    return value


def encoded_message(value,sender,message_id):
    draft(value);address(sender)
    mail=EmailMessage(policy=SMTP);mail['From']=sender;mail['To']=value['to'];mail['Subject']=value['subject']
    mail['Message-ID']=message_id;mail.set_content(value['body'])
    return base64.urlsafe_b64encode(mail.as_bytes()).decode().rstrip('=')


class PlainHTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style','head'}:self.skip+=1
        if tag in {'br','p','div','li','tr'} and not self.skip:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in {'script','style','head'} and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)


def message(value,full=False):
    if not isinstance(value,dict):raise CoreError('mail_response','Invalid Gmail message')
    identifier(value.get('id'));payload=value.get('payload',{})
    headers={}
    for h in payload.get('headers',[])[:100]:
        if isinstance(h,dict) and isinstance(h.get('name'),str) and isinstance(h.get('value'),str):headers.setdefault(h['name'].lower(),h['value'][:2000])
    result={'id':value['id'],'thread_id':value.get('threadId',''),'subject':headers.get('subject','(无主题)'),
            'from':headers.get('from',''),'to':headers.get('to',''),'date':headers.get('date',''),
            'reply_to':headers.get('reply-to',''),'labels':value.get('labelIds',[])[:50],
            'snippet':str(value.get('snippet',''))[:1000],'message_id':headers.get('message-id','')}
    if full:
        plain=[];html=[];count=0
        def visit(part,depth=0):
            nonlocal count
            count+=1
            if depth>10 or count>100 or not isinstance(part,dict):return
            if not part.get('filename') and part.get('mimeType') in {'text/plain','text/html'}:
                data=part.get('body',{}).get('data','')
                if isinstance(data,str) and len(data)<200000:
                    try:content=base64.urlsafe_b64decode(data+'='*(-len(data)%4)).decode('utf-8',errors='replace')[:50000]
                    except (ValueError,TypeError):content=''
                    (plain if part['mimeType']=='text/plain' else html).append(content)
            for item in part.get('parts',[])[:50]:visit(item,depth+1)
        visit(payload)
        if plain:body='\n'.join(plain)
        else:
            parser=PlainHTML();parser.feed('\n'.join(html));body=''.join(parser.parts)
        result['body']=body[:50000]
    return result


def _category(mail,rules=()):
    sender=parseaddr(mail.get('from',''))[1].lower();text=(mail.get('subject','')+' '+mail.get('snippet','')).lower()
    for rule in rules:
        if sender and rule.get('sender')==sender:return {'category':rule['category'],'reason':'主人的发件人规则','rule_id':rule['id']}
    if 'SPAM' in mail.get('labels',[]):return {'category':'spam','reason':'Gmail 垃圾邮件标签'}
    if any(x in text for x in ['密码过期','验证密码','中奖','钱包助记词','seed phrase','verify your password']):
        return {'category':'suspicious','reason':'命中可疑内容提示；不代表已证实欺诈'}
    if any(x in text for x in ['账单','收据','消费成功','扣款','付款失败','航班','会议','面试','invoice','receipt','payment failed','flight','security alert','验证码']):
        return {'category':'important','reason':'命中通知类关键词；可能误判'}
    if 'IMPORTANT' in mail.get('labels',[]):return {'category':'important','reason':'Gmail 重要标签；可由主人规则纠正'}
    if 'CATEGORY_PROMOTIONS' in mail.get('labels',[]):return {'category':'promotion','reason':'Gmail 推广分类；不证明邮件可信或有害'}
    if any(x in text for x in ['unsubscribe','退订','优惠','促销','sale ends']):return {'category':'promotion','reason':'命中推广类关键词'}
    return {'category':'normal','reason':'暂无特别规则'}


def classify(mail,rules=()):
    result=_category(mail,rules)
    sender=parseaddr(mail.get('from',''))[1].lower();subject=mail.get('subject','').casefold();domain=sender.rsplit('@',1)[-1]
    for rule in sorted((r for r in rules if r.get('kind')=='folder_rule' and r.get('enabled',True)),key=lambda r:(-r.get('priority',50),r['id'])):
        pattern=rule['pattern'].strip().casefold();field=rule['field']
        matched=(pattern in subject if field=='subject' else sender==pattern if field=='sender' else domain==pattern or domain.endswith('.'+pattern))
        if matched:return {**result,'folder':rule['folder'],'folder_reason':'你的'+{'subject':'标题','sender':'发件人','domain':'域名'}[field]+'规则：'+rule['pattern'],
            'folder_rule_id':rule['id'],'folder_basis':'personal_rule','model_tokens':0}
    text=subject+' '+sender
    groups=[('账号安全',('验证码','security alert','password','登录','安全警报','安全提醒')),
        ('账单财务',('invoice','receipt','payment','账单','收据','付款','扣款')),
        ('物流订单',('delivery','shipment','tracking','物流','快递','订单','发货')),
        ('工作协作',('gitlab','github','meeting','workshop','项目','会议','工单','评审','review','project')),
        ('学习成长',('english','lesson','course','学习','课程','练习','口语')),
        ('订阅资讯',('newsletter','unsubscribe','订阅','观察','新闻','促销','sale'))]
    for folder,words in groups:
        matched=next((w for w in words if w in text),None)
        if matched:return {**result,'folder':folder,'folder_reason':'标题/发件人命中“'+matched+'”，可纠正','folder_basis':'local_hint','model_tokens':0}
    return {**result,'folder':'待整理','folder_reason':'没有匹配的本地规则；未交给云端模型','folder_basis':'unclassified','model_tokens':0}
