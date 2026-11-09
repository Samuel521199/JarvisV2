"""Reviewed source draft, copied into the existing intent module after r3 runs.

Full frames are checked, not keyword-presence authorization: every remaining
token must be known request syntax; task names and clocks stay literal anchors.
"""
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
    common_zh=['@item@','@clock@','请','帮我','我','的','把','将','待办事项','待办任务','待办','这个待办','提醒','这个提醒','本地','一个','一条','一项','个']
    common_en=['the','a','one','my','local','to-do','todo','task','tasks','item','reminder']
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
        zh_words=['改期到','改到','改为','挪到','推迟到','移到','调整为','调整到','重新安排在','重新安排到','的时间','时间']
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
