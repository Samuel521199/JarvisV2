"""Small deterministic admission grammar for local, reversible chat intentions.

Model candidates aren't authorization. Unsupported wording stays a proposal;
ambiguous clocks never acquire a default time or timezone.
"""
from datetime import datetime, timedelta, timezone
import re
from modules.task_resource.commitments import due
from sdk.protocol import CoreError

ISO = r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|[+-]\d\d:\d\d)'
DAY = r'(?:今天|明天|后天|\d{4}-\d\d-\d\d)'
CLOCK = r'(?:\d{1,2}:\d\d|\d{1,2}点(?:\d{1,2}分?)?)'
LOCAL = DAY + r'\s*(?:上午|下午|晚上|中午)?' + CLOCK + r'\s*UTC[+-]\d\d:\d\d'
TIME = '(?:' + ISO + '|' + LOCAL + ')'
PREFIX = r'(?:(?:请(?:你)?(?:帮我)?|帮我|麻烦(?:你)?(?:帮我)?|劳驾(?:你)?|给我)\s*)?'
EN_PREFIX = r'(?:(?:please|could you|can you)\s+)?'
REMIND = r'(?:提醒我一下|提醒一下我|提醒我)'
UNSAFE = r'不要|不必|无需|别|如果|假设|例如|比如|引用|转发|示例|解释|代码|演示|[“”"「」`\n]'
EN_UNSAFE = r"\b(?:do\s+not|don['’]t|never|if|unless|example|quote|explain)\b"
COMPOUND = r'[;；]|然后|并且|同时|顺便|还要|另外|\b(?:and|then|also)\b'


def create_parts(text):
    """Extract literal task and clock; candidates cannot supply missing text."""
    patterns = [
        (PREFIX+r'(?:记下|记(?:个|一个|一条)|新增(?:一个|一条)?|添加(?:一个|一条)?|加(?:个|一个|一条))待办(?:事项)?[：:，,\s]*(.+?)[。！!]?$', False, False),
        (PREFIX+r'在(?:我的)?待办(?:清单|列表)(?:里|中)?(?:添加|加)(?:一项|一个|一条)[：:，,\s]*(.+?)[。！!]?$', False, False),
        (PREFIX+r'(?:在|于|到)?\s*('+TIME+r')(?:时)?[，,\s]*'+REMIND+r'[，,\s]*(.+?)[。！!]?$', True, False),
        (PREFIX+REMIND+r'(?:在|于)?\s*('+TIME+r')[，,\s]*(.+?)[。！!]?$', True, False),
        (PREFIX+r'(?:设置|设|定|添加|新增)(?:个|一个|一条)?(?:本地)?提醒[：:，,\s]*('+TIME+r')[，,\s]*(.+?)[。！!]?$', True, False),
        (PREFIX+r'(?:设置|设|定)(?:个|一个|一条)?提醒[，,\s]*时间是\s*('+TIME+r')[，,\s]*内容是\s*(.+?)[。！!]?$', True, False),
        (PREFIX+r'(?:设置|设|定)(?:个|一个|一条)?\s*('+TIME+r')\s*的(?:本地)?提醒[：:，,\s]*(.+?)[。！!]?$', True, False),
        (PREFIX+REMIND+r'[，,\s]*(.+?)[，,\s]*(?:时间(?:定)?在|时间是|时间为|在|于)\s*('+TIME+r')[。！!]?$', True, True),
        (EN_PREFIX+r'(?:add|create)\s+(?:(?:a|one)\s+)?(?:to-do|todo|task)(?:\s+item)?\s*[:，,\s]\s*(.+?)[.!]?$', False, False),
        (EN_PREFIX+r'add\s+(.+?)\s+to\s+(?:my|the)\s+(?:to-do|todo|task)\s+list[.!]?$', False, False),
        (EN_PREFIX+r'remind me to\s+(.+?)\s+at\s+('+TIME+r')[.!]?$', True, True),
        (EN_PREFIX+r'(?:at\s+)?('+TIME+r')[,\s]+remind me to\s+(.+?)[.!]?$', True, False),
        (EN_PREFIX+r'remind me at\s+('+TIME+r')\s+to\s+(.+?)[.!]?$', True, False),
        (EN_PREFIX+r'(?:set|create|add)\s+(?:a\s+)?(?:local\s+)?reminder\s+for\s+('+TIME+r')(?:\s+to\s+|:\s*)(.+?)[.!]?$', True, False),
        (EN_PREFIX+r'(?:set|create|add)\s+(?:a\s+)?(?:local\s+)?reminder\s+(?:to|for)\s+(.+?)\s+at\s+('+TIME+r')[.!]?$', True, True),
    ]
    for pattern, timed, reversed_groups in patterns:
        match=re.fullmatch(pattern,text,re.IGNORECASE)
        if match:
            if not timed:return match[1].strip(),None
            clock,label=(match[2],match[1]) if reversed_groups else (match[1],match[2])
            return label.strip(),clock
    return None


def literal(label,expected,*,target=False):
    """Only known reference wrappers may surround the exact literal title."""
    label=label.strip()
    if label==expected:return True
    if target:
        label=re.sub(r'^(?:现有的|现有|已有的|已有)\s*','',label)
        label=re.sub(r'^(?:the\s+)?existing\s+','',label,flags=re.IGNORECASE)
        label=re.sub(r'^(?:待办事项|待办|提醒)\s*','',label)
        label=re.sub(r'^(?:the\s+)?(?:to-do(?:\s+item)?|todo(?:\s+item)?|reminder|task)(?:\s+for)?\s+','',label,flags=re.IGNORECASE)
        label=re.sub(r'的(?:提醒|待办|时间)$','',label).strip()
        if label==expected:return True
    for left,right in [('“','”'),('「','」'),('"','"'),("'","'")]:
        if label.startswith(left) and label.endswith(right) and label[1:-1].strip()==expected:return True
    return False


def edit_parts(text,operation):
    if operation=='reschedule':
        pattern=PREFIX+r'(?:把|将)?\s*(.+?)(?:改期到|改到|改为|挪到|推迟到|移到|调整为|调整到|重新安排在)\s*('+TIME+r')[。！!]?'
        english=EN_PREFIX+r'(?:move|reschedule)\s+(.+?)\s+to\s+('+TIME+r')[.!]?'
    elif operation=='cancel':
        pattern=PREFIX+r'取消\s*(.+?)[。！!]?';english=EN_PREFIX+r'cancel\s+(.+?)[.!]?'
    elif operation=='complete':
        pattern=r'(?:我已完成了[，,]\s*)?'+PREFIX+r'(?:把|将)?\s*(.+?)(?:标记为完成|标记完成|设为完成)[。！!]?'
        english=EN_PREFIX+r'mark\s+(.+?)\s+(?:as\s+)?(?:done|complete|completed)[.!]?'
    else:return None
    match=re.fullmatch(pattern,text) or re.fullmatch(english,text,re.IGNORECASE)
    if match:return match[1].strip(),match[2] if operation=='reschedule' else None
    if operation=='complete':
        match=re.fullmatch(r'我(?:已经|已)?完成(?:了)?\s*(.+?)[，,]\s*(?:请)?标记(?:一下)?[。！!]?',text)
        if match:return match[1].strip(),None
    return None


def anchored_parts(text,operation,title):
    if not title or text.count(title)!=1:return None
    clocks=list(re.finditer(TIME,text));timed=operation=='reschedule' or operation=='create' and bool(clocks)
    if len(clocks)!=(1 if timed else 0):return None
    begin=text.index(title);end=begin+len(title)
    if clocks and not (end<=clocks[0].start() or begin>=clocks[0].end()):return None
    label=title
    for left,right in [('“','”'),('「','」'),('"','"'),("'","'")]:
        if begin>0 and end<len(text) and text[begin-1]==left and text[end]==right:label=text[begin-1:end+1];break
    frame=text[:begin]+'@item@'+text[end:]
    for left,right in [('“','”'),('「','」'),('"','"'),("'","'")]:
        frame=frame.replace(left+'@item@'+right,'@item@')
    frame=re.sub(TIME,'@clock@',frame)
    zh=re.sub('^'+PREFIX,'',frame).strip();en=re.sub('^'+EN_PREFIX,'',frame,flags=re.IGNORECASE).strip().lower()
    common_zh=['@item@','@clock@','请','帮我','我','的','把','将','待办事项','待办任务','待办','这个待办','提醒','这个提醒','本地','一个','一条','一项','个','现有的','现有','已有的','已有']
    common_en=['the','a','one','my','local','locally','existing','to-do','todo','task','tasks','item','reminder']
    if operation=='create':
        zh_root=bool(re.match(r'(?:提醒我|提醒一下我|提醒我一下|设置|设|定|记下|记|添加|新增|加|在|于|到|@clock@)',zh))
        en_root=bool(re.match(r'(?:remind me\b|set\b|create\b|add\b)',en))
        zh_ok=bool(re.search('提醒',zh)) if timed else bool(re.search('待办',zh))
        en_ok=bool(re.search(r'\b(?:remind|reminder)\b',en)) if timed else bool(re.search(r'\b(?:to-do|todo|task)\b',en))
        zh_words=['提醒我一下','提醒一下我','提醒我','设置','设','定','记下','记','添加','新增','加','在','于','到','时','我的','清单','列表','里','中',
                  '时间设定为','时间设为','时间定在','时间是','时间在','时间为','时间','设定为','设为','定在','内容是','内容为','内容','是','为']
        en_words=['remind','me','set','create','add','new','at','for','to','list']
    elif operation=='reschedule':
        zh_root=bool(re.match(r'(?:把|将|@item@)',zh));en_root=bool(re.match(r'(?:move|reschedule)\b',en))
        zh_words=['改期到','改到','改为','挪到','推迟到','移到','调整为','调整到','重新安排在','重新安排到','重新安排为','的时间','时间']
        en_words=['move','reschedule','to','for']
        zh_ok=any(word in zh for word in zh_words[:-2]);en_ok=True
    elif operation=='cancel':
        zh_root=zh.startswith('取消');en_root=bool(re.match(r'cancel\b',en))
        zh_words=['取消','这个','这项'];en_words=['cancel','from'];zh_ok=en_ok=True
    elif operation=='complete':
        zh_root=bool(re.match(r'(?:我|把|将|@item@)',zh));en_root=bool(re.match(r'mark\b',en))
        zh_words=['已','已经','完成','了','标记为','标记','一下','设为'];en_words=['mark','as','done','complete','completed']
        zh_ok=bool(re.search(r'标记|设为',zh));en_ok=True
    else:return None
    punctuation=r'[\s，,：:。.!！]'
    zh_tokens='|'.join(re.escape(word) for word in sorted(set(common_zh+zh_words),key=len,reverse=True))
    en_tokens='|'.join(re.escape(word) for word in sorted(set(common_en+en_words),key=len,reverse=True))
    valid_zh=zh_root and zh_ok and re.fullmatch('(?:'+zh_tokens+'|'+punctuation+')+',zh)
    valid_en=en_root and en_ok and re.fullmatch(r'(?:@item@|@clock@|\b(?:'+en_tokens+r')\b|'+punctuation+')+',en)
    if valid_zh or valid_en:return label,clocks[0].group() if clocks else None
    return None


def resolve(text, reference, day_hint=None):
    """Relative days use the original utterance timestamp in the explicit offset."""
    text = text.strip()
    if re.fullmatch(ISO, text): due(text); return text
    if day_hint and re.fullmatch(CLOCK+r'\s*UTC[+-]\d\d:\d\d', text): text=day_hint+text
    match=re.fullmatch('('+DAY+r')\s*(上午|下午|晚上|中午)?('+CLOCK+r')\s*UTC([+-]\d\d:\d\d)',text)
    if not match: return None
    day,period,clock,offset=match.groups()
    due('2000-01-01T00:00:00'+offset)
    sign=-1 if offset[0]=='-' else 1
    zone=timezone(sign*timedelta(hours=int(offset[1:3]),minutes=int(offset[4:])))
    date=datetime.fromtimestamp(reference,zone).date()
    if day in ('今天','明天','后天'): date+=timedelta(days={'今天':0,'明天':1,'后天':2}[day])
    else: date=datetime.strptime(day,'%Y-%m-%d').date()
    parts=re.fullmatch(r'(\d{1,2})(?::(\d\d)|点(?:(\d{1,2})分?)?)',clock)
    hour=int(parts[1]);minute=int(parts[2] or parts[3] or 0)
    if period in ('下午','晚上'):
        if not 1<=hour<=23: return None
        if period=='晚上' and hour==12:return None  # midnight/day-boundary needs clarification
        if hour>12 and ((period=='晚上' and hour<18) or (period=='下午' and hour>18)):return None
        if hour<12: hour+=12
    elif period=='中午':
        if hour not in (11,12,1): return None
        if hour==1:hour=13
    elif period=='上午' and not 1<=hour<=11: return None
    result=datetime(date.year,date.month,date.day,hour,minute,tzinfo=zone).isoformat(timespec='seconds')
    due(result);return result


def interpret(text, operation, title, reference, *, target_title=None, active_count=0):
    text=text.strip()
    result={'mode':'REVIEW','message':'请核对本地待办候选及原文。','title':title,'due_at':None,'needs_time':operation in ('create','reschedule')}
    # A direct reminder prefix is affirmative; a remaining "不要/别" still
    # blocks admission. Quoted occurrences are not stripped.
    if text.startswith('别忘了'):text=text[len('别忘了'):].lstrip()
    parts=create_parts(text) if operation=='create' else edit_parts(text,operation)
    unique_reference=(operation!='create' and parts and active_count==1
        and parts[0].lower() in ('这个提醒','这项待办','这个待办','this reminder','this task'))
    if not parts or not (literal(parts[0],title,target=operation!='create') or unique_reference):
        parts=anchored_parts(text,operation,title)
    # A directly requested title may contain literal book/quotation marks.
    # The full request must still match; quoted commands and forwarded prose do not.
    guarded=text
    if parts and literal(parts[0],title,target=operation!='create'):
        start=text.find(parts[0])
        if start>=0:guarded=text[:start]+re.sub(r'[“”"「」]','',parts[0])+text[start+len(parts[0]):]
    if re.search(UNSAFE,guarded) or re.search(EN_UNSAFE,guarded,re.IGNORECASE):
        return {**result,'mode':'NOT_REQUEST','message':'原文含否定、引用或条件，不作为直接待办指令。'}
    if re.search(COMPOUND,text,re.IGNORECASE) or len(list(re.finditer(TIME,text)))>1:
        return {**result,'message':'请求含多个动作，需保留完整要求并核对，不能自动合并为一项提醒。'}
    if operation=='create':
        if parts and literal(parts[0],title):
            if parts[1] is None:return {**result,'mode':'AUTO','message':'明确的本地待办请求','needs_time':False}
            try:when=resolve(parts[1],reference)
            except (CoreError,ValueError,OverflowError):when=None
            if when:return {**result,'mode':'AUTO','message':'原文明确的时间和事项','due_at':when,'needs_time':False}
        vague=re.fullmatch(PREFIX+r'(?:在)?('+DAY+r')(?:上午|下午|晚上|中午)?'+REMIND+r'[，,\s]*(.+?)[。！!]?$',text)
        if vague and vague[2].strip()==title:
            return {**result,'mode':'NEEDS_TIME','message':'需要具体几点和UTC偏移；没有保存提醒。','day_hint':vague[1]}
        return result
    if operation not in ('reschedule','cancel','complete') or target_title!=title:return result
    if not parts:return result
    label=parts[0]
    if not literal(label,target_title,target=True) and not (active_count==1 and label.lower() in ('这个提醒','这项待办','这个待办','this reminder','this task')):return result
    if operation=='reschedule':
        try:when=resolve(parts[1],reference)
        except (CoreError,ValueError,OverflowError):when=None
        if not when:return result
        result['due_at']=when
    return {**result,'mode':'AUTO','message':'原文明确指向当前会话待办','needs_time':False}
