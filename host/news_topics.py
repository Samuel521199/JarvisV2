"""Local, multilingual topic filters for publisher-supplied news metadata."""
import re
import unicodedata

# A desk match covers the broad topic. Narrow topics require article evidence.
# Labels are also literal matches. ASCII word boundaries keep "AI" out of "said".
PRESETS = {
    '国际': ('国际', 'diplomacy|diplomatic|外交|diplomacia'),
    '体育': ('体育', 'sports|sport|football|basketball|soccer|tennis|esporte|體育|足球|篮球|籃球|网球|網球'),
    '足球': ('', 'football|soccer|futebol|premier league|world cup|英超|世界杯|世界盃'),
    '篮球': ('', 'basketball|nba|wnba|basquete|籃球'),
    '赛车': ('', 'formula 1|formula one|f1|motorsport|nascar|賽車|fórmula 1'),
    '财经': ('财经', 'economy|economic|economia|inflation|trade|財經|經濟|经济|通胀|通脹'),
    '股票': ('', 'stock|stocks|shares|equities|nasdaq|s&p 500|ipo|沪指|港股|股市|美股|台股|股价|股價|ações|bolsa de valores'),
    '科技': ('科技', 'technology|tecnologia|technologies'),
    '人工智能 AI': ('', 'ai|artificial intelligence|人工智能|人工智慧|大模型|llm|machine learning|openai|deepmind|inteligência artificial'),
    '芯片': ('', 'chip|chips|semiconductor|semiconductors|半导体|半導體|晶片|semicondutores'),
    '机器人': ('', 'robot|robots|robotics|機器人|robótica|robôs'),
    '游戏开发': ('', 'game development|game developer|game developers|game engine|unreal engine|遊戲開發|游戏引擎|desenvolvimento de jogos'),
    '科学': ('科学', 'science|scientists|researchers|科學|ciência'),
    '航天': ('', 'spaceflight|spacecraft|astronaut|astronauts|orbital|nasa|航太|太空|航天|espaço'),
    '健康': ('健康', 'health|medical|medicine|saúde|醫療|医疗'),
    '文化': ('文化', 'culture|cultura|cinema|cinematography|藝術|艺术'),
}


def normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def pattern(terms):
    parts = []
    for term in terms:
        word = re.escape(normalized(term))
        if term.isascii() and term[0].isalnum() and term[-1].isalnum():
            word = r'(?<![a-z0-9])' + word + r'(?![a-z0-9])'
        parts.append(word)
    return re.compile('|'.join(parts))


PATTERNS = {name:pattern([name,*terms.split('|')]) for name,(_,terms) in PRESETS.items()}


def topic_filter(prefs):
    topics = prefs.get('topics', [])
    extra = prefs.get('custom_topics', [])
    if not topics and not extra:
        return None
    desks = {PRESETS[name][0] for name in topics}
    rules = [PATTERNS[name] for name in topics]
    if extra:
        rules.append(pattern(extra))

    def matches(desk, text):
        content = normalized(text)
        return desk in desks or any(rule.search(content) for rule in rules)
    return matches
