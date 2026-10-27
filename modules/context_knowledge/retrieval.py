"""Query ranking over already-authorized facts; no model, network or authority decisions."""
from collections import Counter
import math
import re
import unicodedata

VERSION = 'memory-retrieval-1.1.0'
STOP = {'a','an','the','is','are','what','which','does','do','i','my','me','please','of','to','and','in','it'}
QUERY_STOP = {'how','many','much','there','their','both','did','was','were','have','has','had',
              'can','could','would','should','you','your','they','them','we','our','he','she','his','her',
              'that','this','these','those','for','from','with','at','on','as','be','been','being',
              'when','where','who','why','any','some','about','tell','us','by','an','a'}


def variants(term):
    """Small English inflection fallback, preserving exact codes and other languages.

    The query includes both forms, so existing unicode61 indexes need no migration.
    This is lexical recall, not multilingual semantic understanding.
    """
    result={term}
    if re.fullmatch('[a-z]{5,}',term):
        if term.endswith('ies'):result.add(term[:-3]+'y')
        elif term.endswith('s') and not term.endswith(('ss','us','is')):result.add(term[:-1])
        if term.endswith(('ses','xes','zes','ches','shes')):result.add(term[:-2])
        if term.endswith('ing') and len(term)>6:result.update((term[:-3],term[:-3]+'e'))
        if term.endswith('ed') and len(term)>5:result.update((term[:-2],term[:-1]))
    return result


def query_terms(query):
    return [term for term in tokens(query) if term not in QUERY_STOP]


def query_words(query):
    return sorted({word for term in query_terms(query) for word in variants(term)})[:64]


def normalized(text):
    return unicodedata.normalize('NFKC', text).casefold()


def tokens(text):
    words = []
    for part in re.findall(r'[\u3400-\u9fff]+|[^\W_\u3400-\u9fff]+(?:[._-][^\W_\u3400-\u9fff]+)*', normalized(text)):
        if re.fullmatch(r'[\u3400-\u9fff]+', part):
            words.extend(part[i:i+2] for i in range(len(part)-1))
            if len(part) == 1: words.append(part)
        elif part not in STOP: words.append(part)
    return Counter(words)


def title_matches(title, query):
    key=normalized(title).strip();text=normalized(query)
    if not key:return False
    if re.search(r'[\u3400-\u9fff]',key):return key==text or (len(key)>1 and key in text)
    return bool(re.search(r'(?<![^\W\u3400-\u9fff])'+re.escape(key)+r'(?![^\W\u3400-\u9fff])',text))


def lexical(rows, query):
    terms = query_terms(query); documents = [tokens(r['key']+' '+r['value']) for r in rows]
    forms=[]
    for doc in documents:
        expanded=Counter()
        for word,count in doc.items():
            for form in variants(word):expanded[form]+=count
        forms.append({term:max((expanded[form] for form in variants(term)),default=0) for term in terms})
    frequencies = Counter(t for d in forms for t,count in d.items() if count)
    average = sum(sum(d.values()) for d in documents) / max(1, len(documents)) or 1
    scores = {}
    for row, doc, matches in zip(rows, documents, forms):
        score = 0.0; length = sum(doc.values())
        for term in terms:
            tf = matches[term]
            if tf:
                idf = math.log(1 + (len(rows)-frequencies[term]+.5)/(frequencies[term]+.5))
                score += idf * tf * 2.2 / (tf + 1.2*(.25+.75*length/average))
        if title_matches(row['key'],query): score += 8
        scores[row['id']] = score
    return scores


def rank(rows, query, semantic=None):
    """Keep explicit personal background; unrelated knowledge requires a retrieval hit."""
    if not query.strip():
        return rows, {'version':VERSION,'mode':'background','eligible':len(rows),'semantic':'not_requested'}
    scores = lexical(rows, query)
    ordered = sorted(rows, key=lambda r: (-scores[r['id']], r['key'], r['id']))
    extra = semantic(ordered, query) if semantic and rows else {'status':'unavailable'}
    semantic_scores = {r['id']:r['semantic_score'] for r in rows if 'semantic_score' in r}
    semantic_scores.update(extra.get('scores', {}))
    keyword_order = [r for r in ordered if scores[r['id']] > 0]
    # E5 similarities have a high common baseline. Do not fill every slot with weak neighbors.
    best=max((semantic_scores.get(r['id'],-1) for r in rows),default=-1)
    # Source passages have a different score distribution from short owner facts.
    # This only admits unverified evidence candidates, never asserts answerability.
    semantic_order = sorted((r for r in rows if semantic_scores.get(r['id'], -1) >= max(.70 if r['kind']=='source' else .78,best-.025)),
                            key=lambda r: -semantic_scores[r['id']])[:4]
    fused = {}
    for ranking, weight in ((keyword_order, 1.0), (semantic_order, .8)):
        for i, row in enumerate(ranking): fused[row['id']] = fused.get(row['id'], 0) + weight/(20+i)
    # Exact titles/codes outrank approximate similarity, including cross-language guesses.
    for row in rows:
        if title_matches(row['key'],query): fused[row['id']] = fused.get(row['id'],0)+1
    chosen = [r for r in rows if r['id'] in fused or r['kind'] in {'profile','preference','agreement'}]
    chosen.sort(key=lambda r: (-fused.get(r['id'], 0), r['key'], r['id']))
    return chosen, {'version':VERSION,'mode':'hybrid' if extra.get('status')=='ready' or semantic_scores else 'lexical',
                    'eligible':len(rows),'matched':len(fused),'semantic':extra.get('status','unavailable'),
                    'semantic_candidates':extra.get('count',0),'model':extra.get('model'),
                    'vector_space':extra.get('space')}
